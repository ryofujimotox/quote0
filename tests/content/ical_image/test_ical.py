"""ical.py の単体テスト。"""

from __future__ import annotations

from datetime import date, datetime
from email.message import Message
from urllib.error import HTTPError

import pytest

from quote0.vendor.quote0_client.exceptions import Quote0Error
from quote0.content.ical_image.ical_models import JST
from quote0.content.ical_image import ical as ical_module
from quote0.content.ical_image.ical import fetch_icals, parse_icals

from tests.content.ical_image.factories import (
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

# テスト用の基準時刻（REFERENCE_TODAY の朝。timed 予定より前）
REFERENCE_NOW = datetime(2026, 5, 29, 7, 0, tzinfo=JST)

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

    with pytest.raises(Quote0Error, match=f"iCal 取得失敗 url={ICS_URL_B} status=500"):
        fetch_icals(urls)


def test_parse_icals_returns_today_and_next_day_frames() -> None:
    assert parse_icals((), reference_now=REFERENCE_NOW) == make_empty_window()


def test_parse_icals_extracts_events_by_frame_rule_and_sorts_deterministically() -> None:
    window = parse_icals(
        (
            make_fetched_ical(MULTI_SOURCE_ICS_A, source_index=0, url=ICS_URL_A),
            make_fetched_ical(MULTI_SOURCE_ICS_B, source_index=1, url=ICS_URL_B),
        ),
        reference_now=REFERENCE_NOW,
    )

    assert window.next_day.date == REFERENCE_TOMORROW
    assert_window_event_uids(
        window,
        first_day=("same-a", "same-b", "night", "early"),
        next=("tomorrow",),
    )


def test_parse_icals_keeps_active_carry_over_event_on_today() -> None:
    carry_over_ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:carry-over
SUMMARY:前日開始の日跨ぎ
DTSTART;TZID=Asia/Tokyo:20260529T230000
DTEND;TZID=Asia/Tokyo:20260530T010000
END:VEVENT
END:VCALENDAR
"""
    just_after_midnight = datetime(2026, 5, 30, 0, 10, tzinfo=JST)

    window = parse_icals(
        (make_fetched_ical(carry_over_ics),),
        reference_now=just_after_midnight,
    )

    assert tuple(event.uid for event in window.first_day.events) == ("carry-over",)
    assert window.next_day.events == ()


def test_parse_icals_normalizes_all_day_events_to_jst_day_range() -> None:
    all_day = make_all_day_event("all-day", title="終日")

    window = parse_icals((make_fetched_ical(ALL_DAY_ICS),), reference_now=REFERENCE_NOW)

    assert window == make_window(next_day_events=(all_day,))


def test_parse_icals_skips_empty_days_to_next_event_day() -> None:
    window = parse_icals((make_fetched_ical(SKIP_TOMORROW_ICS),), reference_now=REFERENCE_NOW)

    assert window.next_day.date == REFERENCE_DAY_PLUS_3
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

    window = parse_icals(
        (make_fetched_ical(today_only_ics),),
        reference_now=REFERENCE_NOW,
    )

    assert window.next_day.date == REFERENCE_TOMORROW
    assert window.next_day.events == ()


RECURRING_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:weekly
SUMMARY:定例
DTSTART;TZID=Asia/Tokyo:20260501T100000
DTEND;TZID=Asia/Tokyo:20260501T110000
RRULE:FREQ=WEEKLY;BYDAY=FR
END:VEVENT
END:VCALENDAR
"""


def test_parse_icals_expands_recurring_events_for_today() -> None:
    window = parse_icals((make_fetched_ical(RECURRING_ICS),), reference_now=REFERENCE_NOW)

    assert len(window.first_day.events) == 1
    assert window.first_day.events[0].uid == "weekly"
    assert window.first_day.events[0].title == "定例"


INVALID_RECURRENCE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:bad-rule
SUMMARY:不正RRULE
DTSTART;TZID=Asia/Tokyo:20260501T100000
DTEND;TZID=Asia/Tokyo:20260501T110000
RRULE:FREQ=INVALID
END:VEVENT
END:VCALENDAR
"""


def test_parse_icals_fails_on_invalid_recurrence_with_url() -> None:
    with pytest.raises(
        Quote0Error,
        match=f"iCal 解析失敗 url={ICS_URL_A} reason=invalid_recurrence",
    ):
        parse_icals(
            (make_fetched_ical(INVALID_RECURRENCE_ICS, url=ICS_URL_A),),
            reference_now=REFERENCE_NOW,
        )


FAR_ONE_OFF_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:far-future
SUMMARY:90日超の予定
DTSTART;TZID=Asia/Tokyo:20260901T100000
DTEND;TZID=Asia/Tokyo:20260901T110000
END:VEVENT
END:VCALENDAR
"""


def test_parse_icals_includes_one_off_events_beyond_recurrence_window() -> None:
    window = parse_icals((make_fetched_ical(FAR_ONE_OFF_ICS),), reference_now=REFERENCE_NOW)

    assert window.first_day.events == ()
    assert window.next_day.date == date(2026, 9, 1)
    assert tuple(event.uid for event in window.next_day.events) == ("far-future",)


RECURRENCE_OVERRIDE_FAR_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:series
SUMMARY:定例
DTSTART;TZID=Asia/Tokyo:20260501T100000
DTEND;TZID=Asia/Tokyo:20260501T110000
RRULE:FREQ=WEEKLY;BYDAY=FR
END:VEVENT
BEGIN:VEVENT
UID:series
SUMMARY:90日超の例外
RECURRENCE-ID;TZID=Asia/Tokyo:20260901T100000
DTSTART;TZID=Asia/Tokyo:20260901T100000
DTEND;TZID=Asia/Tokyo:20260901T110000
END:VEVENT
END:VCALENDAR
"""


def test_parse_icals_skips_recurrence_id_outside_expansion_window() -> None:
    window = parse_icals(
        (make_fetched_ical(RECURRENCE_OVERRIDE_FAR_ICS),),
        reference_now=REFERENCE_NOW,
    )

    assert window.next_day.date == date(2026, 6, 5)
    assert tuple(event.uid for event in window.next_day.events) == ("series",)


def test_parse_icals_omits_ended_events_for_today() -> None:
    today_only_ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:ended
SUMMARY:終了済み
DTSTART;TZID=Asia/Tokyo:20260529T100000
DTEND;TZID=Asia/Tokyo:20260529T110000
END:VEVENT
BEGIN:VEVENT
UID:upcoming
SUMMARY:これから
DTSTART;TZID=Asia/Tokyo:20260529T150000
DTEND;TZID=Asia/Tokyo:20260529T160000
END:VEVENT
END:VCALENDAR
"""
    noon = datetime(2026, 5, 29, 12, 0, tzinfo=JST)

    window = parse_icals((make_fetched_ical(today_only_ics),), reference_now=noon)

    assert tuple(event.uid for event in window.first_day.events) == ("upcoming",)


ALL_DAY_TODAY_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:all-day-today
SUMMARY:今日終日
DTSTART;VALUE=DATE:20260529
DTEND;VALUE=DATE:20260530
END:VEVENT
END:VCALENDAR
"""


def test_fetch_icals_fails_on_unicode_decode_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class BadBytesResponse:
        status = 200

        def __init__(self) -> None:
            self.headers = Message()
            self.headers["Content-Type"] = "text/calendar; charset=utf-8"

        def read(self) -> bytes:
            return b"\xff\xfe\xfd"

        def __enter__(self) -> BadBytesResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def urlopen(request, timeout: int):
        return BadBytesResponse()

    monkeypatch.setattr(ical_module, "urlopen", urlopen)

    with pytest.raises(
        Quote0Error,
        match=f"iCal 取得失敗 url={ICS_URL_A} reason=decode_failed charset=utf-8",
    ):
        fetch_icals((ICS_URL_A,))


def test_fetch_icals_fails_on_unknown_charset(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnknownCharsetResponse:
        status = 200

        def __init__(self) -> None:
            self.headers = Message()
            self.headers["Content-Type"] = "text/calendar; charset=x-unknown-999"

        def read(self) -> bytes:
            return EMPTY_ICS.encode("utf-8")

        def __enter__(self) -> UnknownCharsetResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def urlopen(request, timeout: int):
        return UnknownCharsetResponse()

    monkeypatch.setattr(ical_module, "urlopen", urlopen)

    with pytest.raises(
        Quote0Error,
        match=f"iCal 取得失敗 url={ICS_URL_A} reason=decode_failed charset=x-unknown-999",
    ):
        fetch_icals((ICS_URL_A,))


def test_parse_icals_omits_cancelled_single_event() -> None:
    cancelled_ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:cancelled-one
SUMMARY:キャンセル済み
STATUS:CANCELLED
DTSTART;TZID=Asia/Tokyo:20260529T100000
DTEND;TZID=Asia/Tokyo:20260529T110000
END:VEVENT
END:VCALENDAR
"""

    window = parse_icals((make_fetched_ical(cancelled_ics),), reference_now=REFERENCE_NOW)

    assert window.first_day.events == ()
    assert window.next_day.events == ()


def test_parse_icals_omits_cancelled_recurrence_exception() -> None:
    cancelled_exception_ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:series
SUMMARY:定例
DTSTART;TZID=Asia/Tokyo:20260501T100000
DTEND;TZID=Asia/Tokyo:20260501T110000
RRULE:FREQ=WEEKLY;BYDAY=FR
END:VEVENT
BEGIN:VEVENT
UID:series
SUMMARY:キャンセルされた回
STATUS:CANCELLED
RECURRENCE-ID;TZID=Asia/Tokyo:20260529T100000
DTSTART;TZID=Asia/Tokyo:20260529T100000
DTEND;TZID=Asia/Tokyo:20260529T110000
END:VEVENT
END:VCALENDAR
"""

    window = parse_icals((make_fetched_ical(cancelled_exception_ics),), reference_now=REFERENCE_NOW)

    assert window.first_day.events == ()


def test_parse_icals_keeps_distinct_events_with_empty_uid_and_same_start() -> None:
    empty_uid_ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:予定A
DTSTART;TZID=Asia/Tokyo:20260529T100000
DTEND;TZID=Asia/Tokyo:20260529T110000
END:VEVENT
BEGIN:VEVENT
SUMMARY:予定B
DTSTART;TZID=Asia/Tokyo:20260529T100000
DTEND;TZID=Asia/Tokyo:20260529T110000
END:VEVENT
END:VCALENDAR
"""

    window = parse_icals((make_fetched_ical(empty_uid_ics),), reference_now=REFERENCE_NOW)

    assert tuple(event.title for event in window.first_day.events) == ("予定A", "予定B")


def test_parse_icals_omits_event_titles_from_stdout_by_default(capsys) -> None:
    today_only_ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:visible
SUMMARY:ログに出さない予定
DTSTART;TZID=Asia/Tokyo:20260529T100000
DTEND;TZID=Asia/Tokyo:20260529T110000
END:VEVENT
END:VCALENDAR
"""

    parse_icals((make_fetched_ical(today_only_ics),), reference_now=REFERENCE_NOW)

    output = capsys.readouterr().out
    assert "ログに出さない予定" not in output
    assert "iCal 解析 成功" in output


def test_parse_icals_logs_event_details_when_debug(capsys) -> None:
    today_only_ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:visible
SUMMARY:デバッグで見える予定
DTSTART;TZID=Asia/Tokyo:20260529T100000
DTEND;TZID=Asia/Tokyo:20260529T110000
END:VEVENT
END:VCALENDAR
"""

    parse_icals(
        (make_fetched_ical(today_only_ics),),
        reference_now=REFERENCE_NOW,
        debug=True,
    )

    output = capsys.readouterr().out
    assert "デバッグで見える予定" in output
    assert "iCal 予定詳細:" in output


def test_parse_icals_keeps_all_day_events_on_today_until_day_end() -> None:
    evening = datetime(2026, 5, 29, 20, 0, tzinfo=JST)

    window = parse_icals((make_fetched_ical(ALL_DAY_TODAY_ICS),), reference_now=evening)

    assert tuple(event.uid for event in window.first_day.events) == ("all-day-today",)
