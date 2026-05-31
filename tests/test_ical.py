"""ical.py の単体テスト。"""

from __future__ import annotations

from urllib.error import HTTPError

import pytest

from handy_calendar.errors import HandyCalendarError
from handy_calendar.steps import ical as ical_module
from handy_calendar.steps.ical import fetch_icals, parse_icals

from tests.factories import (
    FakeResponse,
    ICS_URL_A,
    ICS_URL_B,
    REFERENCE_DAY_PLUS_3,
    REFERENCE_TODAY,
    REFERENCE_TOMORROW,
    assert_window_event_uids,
    make_all_day_event,
    make_empty_window,
    make_fetched_ical,
    make_window,
)

EMPTY_ICS = "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n"

MULTI_SOURCE_ICS_A = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:same-b
SUMMARY:同時刻B
DTSTART;TZID=Asia/Tokyo:20260529T090000
DTEND;TZID=Asia/Tokyo:20260529T100000
END:VEVENT
BEGIN:VEVENT
UID:night
SUMMARY:日跨ぎ
DTSTART;TZID=Asia/Tokyo:20260529T230000
DTEND;TZID=Asia/Tokyo:20260530T010000
END:VEVENT
BEGIN:VEVENT
UID:same-a
SUMMARY:同時刻A
DTSTART;TZID=Asia/Tokyo:20260529T090000
DTEND;TZID=Asia/Tokyo:20260529T093000
END:VEVENT
END:VCALENDAR
"""

MULTI_SOURCE_ICS_B = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:early
SUMMARY:別URLの早い予定
DTSTART;TZID=Asia/Tokyo:20260529T080000
DTEND;TZID=Asia/Tokyo:20260529T083000
END:VEVENT
BEGIN:VEVENT
UID:tomorrow
SUMMARY:明日の予定
DTSTART;TZID=Asia/Tokyo:20260530T100000
DTEND;TZID=Asia/Tokyo:20260530T110000
END:VEVENT
END:VCALENDAR
"""

ALL_DAY_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:all-day
SUMMARY:終日
DTSTART;VALUE=DATE:20260530
DTEND;VALUE=DATE:20260531
END:VEVENT
END:VCALENDAR
"""

SKIP_TOMORROW_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:later
SUMMARY:明後日以降
DTSTART;TZID=Asia/Tokyo:20260601T100000
DTEND;TZID=Asia/Tokyo:20260601T110000
END:VEVENT
END:VCALENDAR
"""


def test_fetch_icals_returns_models_in_url_order(monkeypatch: pytest.MonkeyPatch) -> None:
    urls = (ICS_URL_A, ICS_URL_B)
    responses = {
        ICS_URL_A: FakeResponse(EMPTY_ICS),
        ICS_URL_B: FakeResponse(EMPTY_ICS),
    }

    def urlopen(request, timeout: int):
        assert timeout == 20
        return responses[request.full_url]

    monkeypatch.setattr(ical_module, "urlopen", urlopen)

    fetched = fetch_icals(urls)

    assert fetched == (
        make_fetched_ical(EMPTY_ICS, source_index=0, url=ICS_URL_A),
        make_fetched_ical(EMPTY_ICS, source_index=1, url=ICS_URL_B),
    )


def test_fetch_icals_fails_when_one_url_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    urls = (ICS_URL_A, ICS_URL_B)

    def urlopen(request, timeout: int):
        if request.full_url == ICS_URL_B:
            raise HTTPError(ICS_URL_B, 500, "server error", {}, None)
        return FakeResponse(EMPTY_ICS)

    monkeypatch.setattr(ical_module, "urlopen", urlopen)

    with pytest.raises(HandyCalendarError, match=f"iCal 取得失敗 url={ICS_URL_B} status=500"):
        fetch_icals(urls)


def test_parse_icals_returns_today_and_next_day_frames() -> None:
    assert parse_icals((), REFERENCE_TODAY) == make_empty_window()


def test_parse_icals_extracts_overlapping_events_and_sorts_deterministically() -> None:
    window = parse_icals(
        (
            make_fetched_ical(MULTI_SOURCE_ICS_A, source_index=0, url=ICS_URL_A),
            make_fetched_ical(MULTI_SOURCE_ICS_B, source_index=1, url=ICS_URL_B),
        ),
        REFERENCE_TODAY,
    )

    assert window.next_day.day == REFERENCE_TOMORROW
    assert_window_event_uids(
        window,
        today=("same-a", "same-b", "night", "early"),
        next_day=("night", "tomorrow"),
    )


def test_parse_icals_normalizes_all_day_events_to_jst_day_range() -> None:
    all_day = make_all_day_event("all-day", title="終日")

    window = parse_icals((make_fetched_ical(ALL_DAY_ICS),), REFERENCE_TODAY)

    assert window == make_window(next_day_events=(all_day,))


def test_parse_icals_skips_empty_days_to_next_event_day() -> None:
    window = parse_icals((make_fetched_ical(SKIP_TOMORROW_ICS),), REFERENCE_TODAY)

    assert window.next_day.day == REFERENCE_DAY_PLUS_3
    assert tuple(event.uid for event in window.next_day.events) == ("later",)


def test_parse_icals_falls_back_to_empty_tomorrow_when_no_future_events() -> None:
    today_only_ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:today-only
SUMMARY:今日だけ
DTSTART;TZID=Asia/Tokyo:20260529T100000
DTEND;TZID=Asia/Tokyo:20260529T110000
END:VEVENT
END:VCALENDAR
"""

    window = parse_icals((make_fetched_ical(today_only_ics),), REFERENCE_TODAY)

    assert window.next_day.day == REFERENCE_TOMORROW
    assert window.next_day.events == ()
