"""render.py の単体テスト。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

import pytest

from datetime import datetime

from handy_calendar.errors import HandyCalendarError
from handy_calendar.models import JST
from handy_calendar.steps.ical import parse_icals
from handy_calendar.steps.render import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    DATE_FONT_PT,
    DATE_FONT_SIZE,
    TIME_FONT_PT,
    TIME_FONT_SIZE,
    TITLE_FONT_PT,
    TITLE_FONT_SIZE,
    DateHeaderLine,
    DayDividerLine,
    EventLine,
    EmptyDayLine,
    EVENT_LINE_WIDTH,
    _build_lines,
    _fit_title_and_time,
    _format_date_header,
    _load_fonts,
    _px,
    _resolve_font_paths,
    build_display_days,
    render_png,
)

from tests.factories import (
    REFERENCE_DAY_PLUS_3,
    REFERENCE_TODAY,
    REFERENCE_TOMORROW,
    all_day_display,
    make_fetched_ical,
    display_day,
    empty_next_day_display_day,
    empty_today_display_day,
    make_all_day_event,
    make_empty_window,
    make_timed_event,
    make_window,
    make_window_with_timed_events,
    timed_display,
)


def test_format_date_header_uses_reference_today_and_weekday() -> None:
    assert _format_date_header(REFERENCE_TODAY, REFERENCE_TODAY) == "今日（5/29金）"
    assert _format_date_header(REFERENCE_TOMORROW, REFERENCE_TODAY) == "明日（5/30土）"
    assert _format_date_header(REFERENCE_DAY_PLUS_3, REFERENCE_TODAY) == "3日後（6/1月）"


def test_build_display_days_converts_timed_events() -> None:
    window = make_window_with_timed_events()
    today_event = window.today.events[0]
    next_day_event = window.next_day.events[0]

    assert build_display_days(window) == (
        display_day(
            day=REFERENCE_TODAY,
            header="今日（5/29金）",
            events=(timed_display(today_event, "（10:00~10:30）"),),
        ),
        display_day(
            day=REFERENCE_TOMORROW,
            header="明日（5/30土）",
            events=(timed_display(next_day_event, "（15:00~16:00）"),),
        ),
    )


def test_build_display_days_omits_time_suffix_for_all_day_event() -> None:
    all_day = make_all_day_event("all-day", title="終日")
    window = make_window(next_day_events=(all_day,))

    assert build_display_days(window) == (
        empty_today_display_day(),
        display_day(
            day=REFERENCE_TOMORROW,
            header="明日（5/30土）",
            events=(all_day_display(all_day),),
        ),
    )


def test_build_display_days_leaves_empty_days_without_events() -> None:
    assert build_display_days(make_empty_window()) == (
        empty_today_display_day(),
        empty_next_day_display_day(),
    )


def test_build_display_days_uses_days_after_label_for_skipped_days() -> None:
    event = make_timed_event("later", day=REFERENCE_DAY_PLUS_3, start=(10, 0), end=(11, 0))
    window = make_window(next_day=REFERENCE_DAY_PLUS_3, next_day_events=(event,))

    _, next_block = build_display_days(window)

    assert next_block.header == "3日後（6/1月）"


def test_build_display_days_keeps_event_order() -> None:
    first = make_timed_event("first", start=(9, 0), end=(9, 30))
    second = make_timed_event("second", start=(10, 0), end=(10, 30))
    window = make_window(today_events=(first, second))

    today_block, next_day_block = build_display_days(window)

    assert today_block == display_day(
        day=REFERENCE_TODAY,
        header="今日（5/29金）",
        events=(
            timed_display(first, "（09:00~09:30）"),
            timed_display(second, "（10:00~10:30）"),
        ),
    )
    assert next_day_block == empty_next_day_display_day()


def test_build_display_days_shows_end_time_for_overnight_event() -> None:
    overnight = make_timed_event(
        "overnight",
        title="日跨ぎ",
        start=(23, 15),
        end=(1, 15),
        end_day=REFERENCE_TOMORROW,
    )
    window = make_window(today_events=(overnight,))

    today_block, _ = build_display_days(window)

    assert today_block.events[0].time_suffix == "（23:15~01:15）"


def test_build_display_days_shows_carry_over_end_time_only_on_today() -> None:
    carry_over = make_timed_event(
        "carry-over",
        title="前日開始の日跨ぎ",
        day=REFERENCE_TODAY,
        start=(23, 0),
        end=(1, 0),
        end_day=REFERENCE_TOMORROW,
    )
    window = make_window(base_day=REFERENCE_TOMORROW, today_events=(carry_over,))

    today_block, _ = build_display_days(window)

    assert today_block.events[0].time_suffix == "（~01:00）"


def test_build_display_days_shows_carry_over_after_parse_icals() -> None:
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
    window = parse_icals(
        (make_fetched_ical(carry_over_ics),),
        REFERENCE_TOMORROW,
        reference_now=datetime(2026, 5, 30, 0, 10, tzinfo=JST),
    )

    today_block, _ = build_display_days(window)

    assert today_block.events[0].time_suffix == "（~01:00）"


def test_build_lines_always_includes_second_day_block_even_when_today_is_full() -> None:
    events = tuple(
        make_timed_event(
            f"event-{index}",
            start=(8 + index // 12, (index * 5) % 60),
            end=(9 + index // 12, (index * 5) % 60),
        )
        for index in range(24)
    )
    window = make_window(today_events=events)
    lines = _build_lines(build_display_days(window))

    divider_idx = next(i for i, line in enumerate(lines) if isinstance(line, DayDividerLine))
    assert isinstance(lines[divider_idx + 1], DateHeaderLine)
    assert not lines[divider_idx + 1].emphasized


def test_build_lines_interleaves_headers_events_and_divider() -> None:
    window = make_window_with_timed_events()
    today_block, next_day_block = build_display_days(window)

    assert _build_lines((today_block, next_day_block)) == [
        DateHeaderLine("今日（5/29金）", emphasized=True),
        EventLine(today_block.events[0], emphasized=True),
        DayDividerLine(),
        DateHeaderLine("明日（5/30土）", emphasized=False),
        EventLine(next_day_block.events[0], emphasized=False),
    ]


def test_build_lines_adds_empty_day_text_line() -> None:
    today_block, next_day_block = build_display_days(make_empty_window())

    assert _build_lines((today_block, next_day_block)) == [
        DateHeaderLine("今日（5/29金）", emphasized=True),
        EmptyDayLine(emphasized=True),
        DayDividerLine(),
        DateHeaderLine("明日（5/30土）", emphasized=False),
        EmptyDayLine(emphasized=False),
    ]


def test_fit_title_and_time_keeps_short_title_and_full_time(render_fonts) -> None:
    event = make_timed_event("short", title="短い", start=(10, 0), end=(10, 30))

    assert _fit_title_and_time(
        event, render_fonts.emphasis.events, EVENT_LINE_WIDTH, time_suffix="（10:00~10:30）"
    ) == (
        "短い",
        "（10:00~10:30）",
    )


def test_fit_title_and_time_truncates_long_title_but_keeps_start_time(render_fonts) -> None:
    event = make_timed_event(
        "long",
        title="とても長い予定タイトルが入っている場合の表示確認用テスト",
        start=(10, 0),
        end=(10, 30),
    )

    title, suffix = _fit_title_and_time(
        event, render_fonts.emphasis.events, EVENT_LINE_WIDTH, time_suffix="（10:00~10:30）"
    )

    assert title.endswith("…")
    assert suffix.startswith("（10:00")
    assert "10:00" in suffix


def test_fit_title_and_time_truncates_title_and_time_when_width_is_narrow(render_fonts) -> None:
    event = make_timed_event("garbage", title="燃えるゴミテスト", start=(10, 0), end=(10, 30))

    assert _fit_title_and_time(event, render_fonts.emphasis.events, 140, time_suffix="（10:00~10:30）") == (
        "燃…",
        "（10:00~",
    )


def test_fit_title_and_time_keeps_full_title_and_start_time_with_regular_font(render_fonts) -> None:
    event = make_timed_event("garbage-full", title="燃えるゴミテスト", start=(10, 0), end=(10, 30))

    assert _fit_title_and_time(
        event, render_fonts.regular.events, EVENT_LINE_WIDTH, time_suffix="（10:00~10:30）"
    ) == (
        "燃えるゴミテスト",
        "（10:00~",
    )


def test_load_fonts_uses_bold_for_emphasis_and_regular_for_second_block() -> None:
    regular_path, bold_path = _resolve_font_paths()
    fonts = _load_fonts(regular_path, bold_path)

    assert fonts.emphasis.date.size == DATE_FONT_SIZE == _px(DATE_FONT_PT)
    assert fonts.emphasis.events.time.size == TIME_FONT_SIZE == _px(TIME_FONT_PT)
    assert fonts.emphasis.events.title.size == TITLE_FONT_SIZE == _px(TITLE_FONT_PT)
    assert fonts.regular.events.time.size == TIME_FONT_SIZE
    assert fonts.regular.events.title.size == TITLE_FONT_SIZE
    assert fonts.emphasis.events.title != fonts.regular.events.title


def test_render_png_is_deterministic() -> None:
    window = make_empty_window()

    first = render_png(window)
    second = render_png(window)

    assert first == second
    assert first.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_png_outputs_fixed_canvas_size() -> None:
    window = make_window(
        today_events=(make_timed_event("event-1", title="打合せ", start=(10, 0), end=(11, 0)),),
    )

    image = render_png(window)

    with Image.open(BytesIO(image.content)) as rendered:
        assert rendered.size == (CANVAS_WIDTH, CANVAS_HEIGHT)
        assert rendered.getbbox() is not None


def test_resolve_font_paths_raises_when_bundled_font_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from handy_calendar.steps import render as render_module

    monkeypatch.setattr(render_module, "REGULAR_FONT_PATH", Path("/tmp/handy-calendar-missing-font.ttf"))

    with pytest.raises(HandyCalendarError, match="bundled_font_missing"):
        _resolve_font_paths()
