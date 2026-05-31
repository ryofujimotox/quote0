"""iCal 取得・解析。"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from icalendar import Calendar

from ..errors import HandyCalendarError
from ..models import CalendarEvent, CalendarWindow, DateRange, DaySchedule, FetchedIcal, JST


FETCH_TIMEOUT_SECONDS = 20


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
        request = Request(url, headers={"User-Agent": "handy-calendar/0"})
        try:
            with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", 200)
                if status < 200 or status >= 300:
                    raise HandyCalendarError(f"iCal 取得失敗 url={url} status={status}")
                content = response.read()
                text = _decode_ics(content, response.headers)
                print(f"iCal 取得詳細: source={index}, bytes={len(content)}", flush=True)
                fetched.append(FetchedIcal(source_index=index, url=url, text=text))
        except HTTPError as exc:
            raise HandyCalendarError(f"iCal 取得失敗 url={url} status={exc.code}") from exc
        except URLError as exc:
            raise HandyCalendarError(f"iCal 取得失敗 url={url} reason={exc.reason}") from exc
        except TimeoutError as exc:
            raise HandyCalendarError(f"iCal 取得失敗 url={url} reason=timeout") from exc
    return tuple(fetched)


def parse_icals(calendars: tuple[FetchedIcal, ...], today: date) -> CalendarWindow:
    """取得済み ICS から今日・明日の予定を抽出する。

    例: calendars=(FetchedIcal(0, "https://…", "BEGIN:VCALENDAR…"),), today=2026-05-29
        → CalendarWindow(
            today=DaySchedule(2026-05-29, period=29日0時〜30日0時, events=()),
            tomorrow=DaySchedule(2026-05-30, period=30日0時〜31日0時, events=()),
          )
    """
    print(f"iCal 解析: {len(calendars)}件", flush=True)
    tomorrow = today + timedelta(days=1)
    today_period = day_range(today)
    tomorrow_period = day_range(tomorrow)
    events = _sorted_events(event for calendar in calendars for event in _parse_calendar_events(calendar))
    print(f"iCal 解析詳細: total_events={len(events)}", flush=True)
    for event in events:
        print(
            "iCal 予定: "
            f"source={event.source_index}, uid={event.uid}, title={event.title}, "
            f"start={event.period.start.isoformat()}, end={event.period.end.isoformat()}, "
            f"all_day={event.all_day}",
            flush=True,
        )
    return CalendarWindow(
        today=DaySchedule(day=today, period=today_period, events=_events_for_day(events, today_period)),
        tomorrow=DaySchedule(day=tomorrow, period=tomorrow_period, events=_events_for_day(events, tomorrow_period)),
    )


def _decode_ics(content: bytes, headers: Message) -> str:
    """HTTPヘッダーの charset があれば使い、なければ UTF-8 として読む。"""
    charset = headers.get_content_charset() or "utf-8"
    return content.decode(charset)


def _parse_calendar_events(calendar: FetchedIcal) -> tuple[CalendarEvent, ...]:
    try:
        parsed = Calendar.from_ical(calendar.text)
    except ValueError as exc:
        raise HandyCalendarError(f"iCal 解析失敗 url={calendar.url} reason=invalid_ics") from exc

    events: list[CalendarEvent] = []
    for component in parsed.walk("VEVENT"):
        if component.get("DTSTART") is None:
            continue
        events.append(_event_from_component(calendar, component))
    return tuple(events)


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


def _events_for_day(events: tuple[CalendarEvent, ...], period: DateRange) -> tuple[CalendarEvent, ...]:
    return tuple(event for event in events if period.overlaps(event.period))
