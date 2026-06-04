"""iCal 取得・解析。"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from icalendar import Calendar
from recurring_ical_events import of as recurring_events_of

from quote0_client.exceptions import Quote0Error
from ..models import CalendarEvent, CalendarWindow, DateRange, DaySchedule, FetchedIcal, JST


FETCH_TIMEOUT_SECONDS = 20
# RRULE 展開の走査上限（次の予定日探索と整合）
RECURRENCE_EXPANSION_DAYS = 90


def today_in_jst() -> date:
    """バッチ開始時点の JST カレンダー日を返す。"""
    return datetime.now(JST).date()


def day_range(day: date) -> DateRange:
    """JST の 1 日を半開区間にする。

    例: day=2026-05-29 → [2026-05-29 0:00, 2026-05-30 0:00)（JST）
    """
    start = datetime.combine(day, datetime.min.time(), tzinfo=JST)
    return DateRange(start=start, end=start + timedelta(days=1))


def fetch_icals(urls: tuple[str, ...]) -> tuple[FetchedIcal, ...]:
    """公開 ICS URL を URL 列挙順で全件取得する。

    例: ("https://cal.example/a.ics", "https://cal.example/b.ics")
        → (FetchedIcal(0, "https://cal.example/a.ics", "BEGIN:VCALENDAR…"),
           FetchedIcal(1, "https://cal.example/b.ics", "BEGIN:VCALENDAR…"))
    """
    print(f"iCal 取得: {len(urls)}件", flush=True)
    fetched: list[FetchedIcal] = []
    for index, url in enumerate(urls):
        request = Request(url, headers={"User-Agent": "quote0/0"})
        try:
            with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", 200)
                if status < 200 or status >= 300:
                    raise Quote0Error(f"iCal 取得失敗 url={url} status={status}")
                content = response.read()
                text = _decode_ics(content, response.headers)
                print(f"iCal 取得詳細: source={index}, bytes={len(content)}", flush=True)
                fetched.append(FetchedIcal(source_index=index, url=url, text=text))
        except HTTPError as exc:
            raise Quote0Error(f"iCal 取得失敗 url={url} status={exc.code}") from exc
        except URLError as exc:
            raise Quote0Error(f"iCal 取得失敗 url={url} reason={exc.reason}") from exc
        except TimeoutError as exc:
            raise Quote0Error(f"iCal 取得失敗 url={url} reason=timeout") from exc
    return tuple(fetched)


def parse_icals(
    calendars: tuple[FetchedIcal, ...],
    today: date,
    *,
    reference_now: datetime | None = None,
) -> CalendarWindow:
    """取得済み ICS から今日・次の予定日の予定を抽出する。

    2 枠目は today より後で最初に予定がある日。見つからなければ翌日の空枠。
    reference_now はバッチ開始時点（main から渡す）。省略時は解析開始時点。
    reference_now より前に終了した予定は各日枠から除く。

    例: calendars=(FetchedIcal(0, "https://…", "BEGIN:VCALENDAR…"),), today=2026-05-29
        → CalendarWindow(
            today=DaySchedule(2026-05-29, period=29日0時〜30日0時, events=()),
            next_day=DaySchedule(2026-05-31, period=31日0時〜6/1 0時, events=()),
          )
    """
    now = reference_now or datetime.now(JST)
    print(f"iCal 解析: {len(calendars)}件", flush=True)
    today_period = day_range(today)
    events = _sorted_events(
        event for calendar in calendars for event in _parse_calendar_events(calendar, today)
    )
    print(f"iCal 解析詳細: total_events={len(events)}", flush=True)
    for event in events:
        print(
            "iCal 予定: "
            f"source={event.source_index}, uid={event.uid}, title={event.title}, "
            f"start={event.period.start.isoformat()}, end={event.period.end.isoformat()}, "
            f"all_day={event.all_day}",
            flush=True,
        )
    next_day = _find_next_event_day(events, today)
    next_day_period = day_range(next_day)
    # 今日枠は overlap（前日開始の進行中も載せる）。2枠目は開始日のみ（日跨ぎの二重表示を避ける）
    return CalendarWindow(
        today=DaySchedule(
            day=today,
            period=today_period,
            events=_events_still_active(_events_overlapping_day(events, today_period), now),
        ),
        next_day=DaySchedule(
            day=next_day,
            period=next_day_period,
            events=_events_still_active(_events_starting_on_day(events, next_day_period), now),
        ),
    )


def _find_next_event_day(events: tuple[CalendarEvent, ...], today: date) -> date:
    """today より後で最初に予定がある日。なければ翌日（空枠用）。"""
    candidate_days = _days_with_events_after(events, today)
    if candidate_days:
        return candidate_days[0]
    return today + timedelta(days=1)


def _days_with_events_after(events: tuple[CalendarEvent, ...], today: date) -> tuple[date, ...]:
    """today より後に開始する予定があるカレンダー日を昇順で返す。"""
    days = {_event_start_day(event) for event in events if _event_start_day(event) > today}
    return tuple(sorted(days))


def _decode_ics(content: bytes, headers: Message) -> str:
    """HTTPヘッダーの charset があれば使い、なければ UTF-8 として読む。"""
    charset = headers.get_content_charset() or "utf-8"
    return content.decode(charset)


def _parse_calendar_events(calendar: FetchedIcal, today: date) -> tuple[CalendarEvent, ...]:
    try:
        parsed = Calendar.from_ical(calendar.text)
    except ValueError as exc:
        raise Quote0Error(f"iCal 解析失敗 url={calendar.url} reason=invalid_ics") from exc

    window_start = datetime.combine(today, time.min, tzinfo=JST)
    window_end = datetime.combine(
        today + timedelta(days=RECURRENCE_EXPANSION_DAYS),
        time.min,
        tzinfo=JST,
    )
    try:
        events: list[CalendarEvent] = []
        seen: set[tuple[str, date | datetime]] = set()

        def add_component(component) -> None:
            if component.get("DTSTART") is None:
                return
            uid = str(component.get("UID") or "")
            dtstart = component.decoded("DTSTART")
            key = (uid, dtstart)
            if key in seen:
                return
            seen.add(key)
            events.append(_event_from_component(calendar, component))

        # RRULE は90日窓で展開。単発 VEVENT は between の範囲外でも ICS から拾う
        for component in recurring_events_of(parsed).between(window_start, window_end):
            add_component(component)
        for component in parsed.walk("VEVENT"):
            if component.get("RRULE") is not None:
                continue
            # 繰り返しの例外は between 側のみ（90日窓外を単発扱いしない）
            if component.get("RECURRENCE-ID") is not None:
                continue
            add_component(component)
        return tuple(events)
    except Exception as exc:
        # 展開・VEVENT 変換失敗も url 付きで返し、main の想定外エラーに落とさない
        raise Quote0Error(
            f"iCal 解析失敗 url={calendar.url} reason=invalid_recurrence"
        ) from exc


def _event_from_component(calendar: FetchedIcal, component) -> CalendarEvent:
    dtstart = component.decoded("DTSTART")
    dtend = _decoded_end(component, dtstart)
    start = _to_jst_datetime(dtstart)
    end = _to_jst_datetime(dtend)
    uid = str(component.get("UID") or "")
    title = str(component.get("SUMMARY") or "(無題)")
    return CalendarEvent(
        uid=uid,
        title=title,
        period=DateRange(start=start, end=end),
        source_index=calendar.source_index,
        source_url=calendar.url,
        all_day=isinstance(dtstart, date) and not isinstance(dtstart, datetime),
    )


def _decoded_end(component, dtstart: date | datetime) -> date | datetime:
    if component.get("DTEND") is not None:
        return component.decoded("DTEND")
    if component.get("DURATION") is not None:
        return dtstart + component.decoded("DURATION")
    if isinstance(dtstart, datetime):
        return dtstart + timedelta(minutes=1)
    return dtstart + timedelta(days=1)


def _to_jst_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=JST)
        return value.astimezone(JST)
    return datetime.combine(value, time.min, tzinfo=JST)


def _sorted_events(events: Iterable[CalendarEvent]) -> tuple[CalendarEvent, ...]:
    return tuple(sorted(events, key=lambda event: (event.source_index, event.period.start, event.uid)))


def _events_overlapping_day(events: tuple[CalendarEvent, ...], period: DateRange) -> tuple[CalendarEvent, ...]:
    return tuple(event for event in events if period.overlaps(event.period))


def _events_starting_on_day(events: tuple[CalendarEvent, ...], period: DateRange) -> tuple[CalendarEvent, ...]:
    target_day = period.start.astimezone(JST).date()
    return tuple(event for event in events if _event_start_day(event) == target_day)


def _event_start_day(event: CalendarEvent) -> date:
    """2枠目の載せ先・次の予定日探索は、JST の開始日だけで決める。"""
    return event.period.start.astimezone(JST).date()


def _events_still_active(events: tuple[CalendarEvent, ...], now: datetime) -> tuple[CalendarEvent, ...]:
    """終了時刻を過ぎた予定を除く（進行中・未開始は残す）。"""
    return tuple(event for event in events if event.period.end > now)
