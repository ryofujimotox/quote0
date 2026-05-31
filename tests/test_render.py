"""render.py の単体テスト。"""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from handy_calendar.steps.render import (
    DATE_FONT_SIZE,
    TIME_FONT_SIZE,
    TITLE_FONT_SIZE,
    DateHeaderLine,
    DayDividerLine,
    EventLine,
    _bold_font_candidates,
    _build_lines,
    _fit_title_and_time,
    _format_date_header,
    _load_fonts,
    _regular_font_candidates,
    build_display_days,
    render_png,
)

from tests.factories import (
    EVENT_LINE_WIDTH,
    REFERENCE_DAY_PLUS_3,
    REFERENCE_TODAY,
    REFERENCE_TOMORROW,
    all_day_display,
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


def test_format_date_header_includes_section_and_weekday() -> None:
    assert _format_date_header(REFERENCE_TODAY, "today", REFERENCE_TODAY) == "今日（5/29金）"
    assert _format_date_header(REFERENCE_TOMORROW, "secondary", REFERENCE_TODAY) == "明日（5/30土）"
    assert _format_date_header(REFERENCE_DAY_PLUS_3, "secondary", REFERENCE_TODAY) == "3日後（6/1月）"


def test_build_display_days_converts_timed_events() -> None:
    window = make_window_with_timed_events()
    today_event = window.today.events[0]
    next_day_event = window.next_day.events[0]

    assert build_display_days(window) == (
        display_day(
            day=REFERENCE_TODAY,
            header="今日（5/29金）",
            section="today",
            events=(timed_display(today_event, "（10:00~10:30）"),),
        ),
        display_day(
            day=REFERENCE_TOMORROW,
            header="明日（5/30土）",
            section="secondary",
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
            section="secondary",
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
    assert next_block.section == "secondary"


def test_build_display_days_keeps_event_order() -> None:
    first = make_timed_event("first", start=(9, 0), end=(9, 30))
    second = make_timed_event("second", start=(10, 0), end=(10, 30))
    window = make_window(today_events=(first, second))

    today_block, next_day_block = build_display_days(window)

    assert today_block == display_day(
        day=REFERENCE_TODAY,
        header="今日（5/29金）",
        section="today",
        events=(
            timed_display(first, "（09:00~09:30）"),
            timed_display(second, "（10:00~10:30）"),
        ),
    )
    assert next_day_block == empty_next_day_display_day()


def test_build_lines_interleaves_headers_events_and_divider() -> None:
    window = make_window_with_timed_events()
    today_block, next_day_block = build_display_days(window)

    assert _build_lines((today_block, next_day_block)) == [
        DateHeaderLine("今日（5/29金）", "today"),
        EventLine(today_block.events[0], "today"),
        DayDividerLine(),
        DateHeaderLine("明日（5/30土）", "secondary"),
        EventLine(next_day_block.events[0], "secondary"),
    ]


def test_fit_title_and_time_keeps_short_title_and_full_time(render_fonts) -> None:
    event = make_timed_event("short", title="短い", start=(10, 0), end=(10, 30))

    assert _fit_title_and_time(event, render_fonts.today.events, EVENT_LINE_WIDTH) == (
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

    title, suffix = _fit_title_and_time(event, render_fonts.today.events, EVENT_LINE_WIDTH)

    assert title.endswith("…")
    assert suffix.startswith("（10:00")
    assert "10:00" in suffix


def test_fit_title_and_time_truncates_title_and_time_when_width_is_narrow(render_fonts) -> None:
    event = make_timed_event("garbage", title="燃えるゴミテスト", start=(10, 0), end=(10, 30))

    assert _fit_title_and_time(event, render_fonts.today.events, 150) == (
        "燃…",
        "（10:00~",
    )


def test_fit_title_and_time_keeps_full_title_and_start_time_with_regular_font(render_fonts) -> None:
    event = make_timed_event("garbage-full", title="燃えるゴミテスト", start=(10, 0), end=(10, 30))

    assert _fit_title_and_time(event, render_fonts.secondary.events, EVENT_LINE_WIDTH) == (
        "燃えるゴミテスト",
        "（10:00~",
    )


def test_load_fonts_uses_bold_for_today_and_regular_for_secondary() -> None:
    regular_path = next(path for path in _regular_font_candidates() if path.exists())
    bold_path = next(path for path in _bold_font_candidates() if path.exists())
    fonts = _load_fonts(regular_path, bold_path)

    assert fonts.today.date.size == DATE_FONT_SIZE == 20
    assert fonts.today.events.time.size == TIME_FONT_SIZE == 20
    assert fonts.today.events.title.size == TITLE_FONT_SIZE == 20
    assert fonts.secondary.events.time.size == TIME_FONT_SIZE
    assert fonts.secondary.events.title.size == TITLE_FONT_SIZE
    assert fonts.today.events.title != fonts.secondary.events.title


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
        assert rendered.size == (296, 152)
        assert rendered.getbbox() is not None
