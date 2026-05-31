"""steps テスト共通の入力データ・フェイク HTTP。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from email.message import Message

from handy_calendar.config import AppConfig
from handy_calendar.models import CalendarEvent, CalendarWindow, DateRange, DaySchedule, FetchedIcal, JST, PngImage
from handy_calendar.steps.ical import day_range
from handy_calendar.steps.render import DisplayDay, DisplayEvent

# テスト全体で基準日を揃える（2026-05-29 = 金曜）
REFERENCE_TODAY = date(2026, 5, 29)
REFERENCE_TOMORROW = date(2026, 5, 30)
REFERENCE_DAY_PLUS_3 = date(2026, 6, 1)

ICS_URL_A = "https://example.com/a.ics"
ICS_URL_B = "https://example.com/b.ics"

# render.py の予定行描画幅（WIDTH - 左右 MARGIN - EVENT_INDENT）
EVENT_LINE_WIDTH = 296 - 12 - 6

DOT_API_URL = "https://dot.mindreset.tech/api/authV2/open/device/device/image"
VALID_PNG = PngImage(content=b"png", width=296, height=152)


def make_dot_config() -> AppConfig:
    return AppConfig(
        ical_urls=(ICS_URL_A,),
        dot_api_token="token",
        dot_device_id="device",
    )


def _datetime_on(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=JST)


def make_timed_event(
    uid: str,
    *,
    day: date = REFERENCE_TODAY,
    start: tuple[int, int] = (10, 0),
    end: tuple[int, int] = (11, 0),
    end_day: date | None = None,
    title: str | None = None,
    source_index: int = 0,
    source_url: str = ICS_URL_A,
) -> CalendarEvent:
    start_dt = _datetime_on(day, *start)
    end_dt = _datetime_on(end_day or day, *end)
    return CalendarEvent(
        uid=uid,
        title=title or uid,
        period=DateRange(start_dt, end_dt),
        source_index=source_index,
        source_url=source_url,
    )


def make_all_day_event(
    uid: str,
    *,
    day: date = REFERENCE_TOMORROW,
    title: str | None = None,
    source_index: int = 0,
    source_url: str = ICS_URL_A,
) -> CalendarEvent:
    start = _datetime_on(day, 0, 0)
    end = _datetime_on(day + timedelta(days=1), 0, 0)
    return CalendarEvent(
        uid=uid,
        title=title or uid,
        period=DateRange(start, end),
        source_index=source_index,
        source_url=source_url,
        all_day=True,
    )


def make_empty_window(
    base_day: date = REFERENCE_TODAY,
    *,
    next_day: date | None = None,
) -> CalendarWindow:
    second_day = next_day or (base_day + timedelta(days=1))
    return CalendarWindow(
        today=DaySchedule(day=base_day, period=day_range(base_day), events=()),
        next_day=DaySchedule(day=second_day, period=day_range(second_day), events=()),
    )


def make_window(
    *,
    base_day: date = REFERENCE_TODAY,
    today_events: tuple[CalendarEvent, ...] = (),
    next_day: date | None = None,
    next_day_events: tuple[CalendarEvent, ...] = (),
) -> CalendarWindow:
    second_day = next_day or (base_day + timedelta(days=1))
    return CalendarWindow(
        today=DaySchedule(day=base_day, period=day_range(base_day), events=today_events),
        next_day=DaySchedule(day=second_day, period=day_range(second_day), events=next_day_events),
    )


def make_fetched_ical(
    text: str,
    *,
    source_index: int = 0,
    url: str = ICS_URL_A,
) -> FetchedIcal:
    return FetchedIcal(source_index=source_index, url=url, text=text)


def make_window_with_timed_events() -> CalendarWindow:
    """build_display_days / _build_lines で使う代表例（今日・次の予定日に 1 件ずつ）。"""
    return make_window(
        today_events=(make_timed_event("today", start=(10, 0), end=(10, 30)),),
        next_day_events=(
            make_timed_event("tomorrow", day=REFERENCE_TOMORROW, start=(15, 0), end=(16, 0)),
        ),
    )


def display_day(
    *,
    day: date,
    header: str,
    events: tuple[DisplayEvent, ...] = (),
) -> DisplayDay:
    return DisplayDay(day=day, header=header, events=events)


def timed_display(event: CalendarEvent, time_suffix: str) -> DisplayEvent:
    return DisplayEvent(event=event, time_suffix=time_suffix)


def all_day_display(event: CalendarEvent) -> DisplayEvent:
    return DisplayEvent(event=event, time_suffix=None)


def empty_today_display_day() -> DisplayDay:
    return display_day(day=REFERENCE_TODAY, header="今日（5/29金）")


def empty_next_day_display_day(
    *,
    day: date = REFERENCE_TOMORROW,
    header: str = "明日（5/30土）",
) -> DisplayDay:
    return display_day(day=day, header=header)


def assert_window_event_uids(
    window: CalendarWindow,
    *,
    today: tuple[str, ...],
    next_day: tuple[str, ...],
) -> None:
    assert tuple(event.uid for event in window.today.events) == today
    assert tuple(event.uid for event in window.next_day.events) == next_day


class FakeResponse:
    """urlopen が返す ICS レスポンスの最小フェイク。"""

    def __init__(self, content: str, status: int = 200) -> None:
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = "text/calendar; charset=utf-8"
        self._content = content.encode("utf-8")

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._content


class FakeJsonResponse:
    """urlopen が返す Dot API JSON レスポンスの最小フェイク。"""

    status = 200

    def __init__(self, payload: dict[str, object]) -> None:
        self._content = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> FakeJsonResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._content
