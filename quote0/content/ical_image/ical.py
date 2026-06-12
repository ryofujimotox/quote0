"""iCal 取得・解析。"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from icalendar import Calendar
from recurring_ical_events import of as recurring_events_of

from quote0.pipeline_log import log_info, log_stage_start, log_stage_success
from quote0.vendor.quote0_client.exceptions import Quote0Error
from .ical_models import CalendarEvent, CalendarWindow, DateRange, DaySchedule, FetchedIcal, JST


FETCH_TIMEOUT_SECONDS = 20
# RRULE 展開の走査上限（次の予定日探索と整合）
RECURRENCE_EXPANSION_DAYS = 90


def today_in_jst() -> date:
    """バッチ開始時点の JST カレンダー日を返す。"""
    return datetime.now(JST).date()


def normalize_reference_now_jst(reference_now: datetime | None = None) -> datetime:
    """基準日時を JST に揃える。省略時は現在時刻、naive は JST として扱う。"""
    if reference_now is None:
        return datetime.now(JST)
    if reference_now.tzinfo is None:
        return reference_now.replace(tzinfo=JST)
    return reference_now.astimezone(JST)


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
    log_stage_start("iCal 取得", detail=f"{len(urls)}件")
    fetched: list[FetchedIcal] = []
    for index, url in enumerate(urls):
        request = Request(url, headers={"User-Agent": "quote0/0"})
        try:
            with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", 200)
                if status < 200 or status >= 300:
                    raise Quote0Error(f"iCal 取得失敗 url={url} status={status}")
                content = response.read()
                try:
                    text = _decode_ics(content, response.headers)
                except (LookupError, UnicodeDecodeError) as exc:
                    charset = response.headers.get_content_charset() or "utf-8"
                    raise Quote0Error(
                        f"iCal 取得失敗 url={url} reason=decode_failed charset={charset}"
                    ) from exc
                log_info(f"iCal 取得詳細: source={index}, bytes={len(content)}")
                fetched.append(FetchedIcal(source_index=index, url=url, text=text))
        except HTTPError as exc:
            raise Quote0Error(f"iCal 取得失敗 url={url} status={exc.code}") from exc
        except URLError as exc:
            raise Quote0Error(f"iCal 取得失敗 url={url} reason={exc.reason}") from exc
        except TimeoutError as exc:
            raise Quote0Error(f"iCal 取得失敗 url={url} reason=timeout") from exc
    log_stage_success("iCal 取得", detail=f"{len(fetched)}件")
    return tuple(fetched)


def parse_icals(
    calendars: tuple[FetchedIcal, ...],
    *,
    reference_now: datetime | None = None,
    debug: bool = False,
) -> CalendarWindow:
    """取得済み ICS から今日・次の予定日の予定を抽出する。

    基準日は reference_now の JST カレンダー日。省略時は解析開始時点の JST。
    2 枠目はその日より後で最初に予定がある日。見つからなければ翌日の空枠。
    reference_now より前に終了した予定は各日枠から除く。

    例: calendars=(FetchedIcal(0, "https://…", "BEGIN:VCALENDAR…"),),
        reference_now=2026-05-29 0:10 JST
        → CalendarWindow(
            first_day=DaySchedule(date=2026-05-29, period=29日0時〜30日0時, events=()),
            next_day=DaySchedule(date=2026-05-31, period=31日0時〜6/1 0時, events=()),
          )
    """
    reference_now = normalize_reference_now_jst(reference_now)
    first_date = reference_now.date()
    first_period = day_range(first_date)
    log_stage_start("iCal 解析", detail=f"{len(calendars)}件")
    events = _sorted_events(
        event
        for calendar in calendars
        for event in _parse_calendar_events(calendar, first_date)
    )
    if debug:
        for event in events:
            log_info(
                "iCal 予定詳細: "
                f"source={event.source_index}, uid={event.uid}, title={event.title}, "
                f"start={event.period.start.isoformat()}, end={event.period.end.isoformat()}, "
                f"all_day={event.all_day}, url={event.source_url}",
            )
    next_date = _find_next_event_day(events, first_date)
    next_period = day_range(next_date)
    # 今日枠は overlap（前日開始の進行中も載せる）。2枠目は開始日のみ（日跨ぎの二重表示を避ける）
    window = CalendarWindow(
        first_day=DaySchedule(
            date=first_date,
            period=first_period,
            events=_events_still_active(_events_overlapping_day(events, first_period), reference_now),
        ),
        next_day=DaySchedule(
            date=next_date,
            period=next_period,
            events=_events_still_active(_events_starting_on_day(events, next_period), reference_now),
        ),
    )
    log_stage_success(
        "iCal 解析",
        detail=(
            f"total_events={len(events)}, "
            f"first_day={len(window.first_day.events)}件, "
            f"next_day={window.next_day.date.isoformat()}({len(window.next_day.events)}件)"
        ),
    )
    return window


def _find_next_event_day(events: tuple[CalendarEvent, ...], first_date: date) -> date:
    """1枠目の日より後で最初に予定がある日。なければ翌日（空枠用）。"""
    candidate_days = _days_with_events_after(events, first_date)
    if candidate_days:
        return candidate_days[0]
    return first_date + timedelta(days=1)


def _days_with_events_after(events: tuple[CalendarEvent, ...], first_date: date) -> tuple[date, ...]:
    """1枠目の日より後に開始する予定があるカレンダー日を昇順で返す。"""
    days = {_event_start_date(event) for event in events if _event_start_date(event) > first_date}
    return tuple(sorted(days))


def _component_dedup_key(calendar: FetchedIcal, component) -> tuple[object, ...]:
    """展開側と walk の二重取り込み防止。UID 空は SUMMARY も含めて別予定とみなす。"""
    uid = str(component.get("UID") or "")
    dtstart = component.decoded("DTSTART")
    if uid:
        return ("uid", uid, dtstart)
    summary = str(component.get("SUMMARY") or "")
    return ("anon", calendar.source_index, dtstart, summary)


def _decode_ics(content: bytes, headers: Message) -> str:
    """HTTPヘッダーの charset があれば使い、なければ UTF-8 として読む。"""
    charset = headers.get_content_charset() or "utf-8"
    return content.decode(charset)


def _parse_calendar_events(calendar: FetchedIcal, first_date: date) -> tuple[CalendarEvent, ...]:
    try:
        parsed = Calendar.from_ical(calendar.text)
    except ValueError as exc:
        raise Quote0Error(f"iCal 解析失敗 url={calendar.url} reason=invalid_ics") from exc

    window_start = datetime.combine(first_date, time.min, tzinfo=JST)
    window_end = datetime.combine(
        first_date + timedelta(days=RECURRENCE_EXPANSION_DAYS),
        time.min,
        tzinfo=JST,
    )
    try:
        events: list[CalendarEvent] = []
        seen: set[tuple[object, ...]] = set()

        def add_component(component) -> None:
            if component.get("DTSTART") is None:
                return
            if str(component.get("STATUS", "")).upper() == "CANCELLED":
                return
            key = _component_dedup_key(calendar, component)
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
    return tuple(event for event in events if _event_start_date(event) == target_day)


def _event_start_date(event: CalendarEvent) -> date:
    """2枠目の載せ先・次の予定日探索は、JST の開始日だけで決める。"""
    return event.period.start.astimezone(JST).date()


def _events_still_active(
    events: tuple[CalendarEvent, ...],
    reference_now: datetime,
) -> tuple[CalendarEvent, ...]:
    """終了時刻を過ぎた予定を除く（進行中・未開始は残す）。"""
    return tuple(event for event in events if event.period.end > reference_now)
