"""ical_image テスト共通の入力データ・フェイク HTTP。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from email.message import Message

from quote0.config import AppConfig
from quote0.custom.ical_image.ical_models import (
    CalendarEvent,
    CalendarWindow,
    DateRange,
    DaySchedule,
    FetchedIcal,
    JST,
    PngImage,
)
from quote0.custom.ical_image.ical import day_range
from quote0.custom.ical_image.render import DisplayDay, DisplayEvent, EVENT_LINE_WIDTH

# テスト全体で基準日を揃える（2026-05-29 = 金曜）
REFERENCE_TODAY = date(2026, 5, 29)
REFERENCE_TOMORROW = date(2026, 5, 30)
REFERENCE_DAY_PLUS_3 = date(2026, 6, 1)

ICS_URL_A = "https://example.com/a.ics"
ICS_URL_B = "https://example.com/b.ics"

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
    first_date: date = REFERENCE_TODAY,
    *,
    next_date: date | None = None,
) -> CalendarWindow:
    second_frame_date = next_date or (first_date + timedelta(days=1))
    return CalendarWindow(
        first_day=DaySchedule(date=first_date, period=day_range(first_date), events=()),
        next_day=DaySchedule(
            date=second_frame_date,
            period=day_range(second_frame_date),
            events=(),
        ),
    )


def make_window(
    *,
    first_date: date = REFERENCE_TODAY,
    first_day_events: tuple[CalendarEvent, ...] = (),
    next_date: date | None = None,
    next_day_events: tuple[CalendarEvent, ...] = (),
) -> CalendarWindow:
    second_frame_date = next_date or (first_date + timedelta(days=1))
    return CalendarWindow(
        first_day=DaySchedule(date=first_date, period=day_range(first_date), events=first_day_events),
        next_day=DaySchedule(
            date=second_frame_date,
            period=day_range(second_frame_date),
            events=next_day_events,
        ),
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
        first_day_events=(make_timed_event("today", start=(10, 0), end=(10, 30)),),
        next_day_events=(
            make_timed_event("tomorrow", day=REFERENCE_TOMORROW, start=(15, 0), end=(16, 0)),
        ),
    )


def display_day(
    *,
    date: date,
    header: str,
    events: tuple[DisplayEvent, ...] = (),
) -> DisplayDay:
    return DisplayDay(date=date, header=header, events=events)


def timed_display(event: CalendarEvent, time_suffix: str) -> DisplayEvent:
    return DisplayEvent(event=event, time_suffix=time_suffix)


def all_day_display(event: CalendarEvent) -> DisplayEvent:
    return DisplayEvent(event=event, time_suffix=None)


def empty_today_display_day() -> DisplayDay:
    return display_day(date=REFERENCE_TODAY, header="今日（5/29金）")


def empty_next_day_display_day(
    *,
    date: date = REFERENCE_TOMORROW,
    header: str = "明日（5/30土）",
) -> DisplayDay:
    return display_day(date=date, header=header)


def assert_window_event_uids(
    window: CalendarWindow,
    *,
    first_day: tuple[str, ...],
    next: tuple[str, ...],
) -> None:
    assert tuple(event.uid for event in window.first_day.events) == first_day
    assert tuple(event.uid for event in window.next_day.events) == next


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
