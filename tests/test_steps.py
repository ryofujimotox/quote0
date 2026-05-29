"""steps 配下の仮実装テスト。"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from handy_calendar.config import AppConfig
from handy_calendar.errors import HandyCalendarError
from handy_calendar.models import CalendarWindow, DaySchedule, PngImage
from handy_calendar.steps.dot import send_dot_image
from handy_calendar.steps.ical import day_range, fetch_icals, parse_icals
from handy_calendar.steps.render import render_png


def make_window(today: date) -> CalendarWindow:
    tomorrow = today + timedelta(days=1)
    return CalendarWindow(
        today=DaySchedule(day=today, period=day_range(today), events=()),
        tomorrow=DaySchedule(day=tomorrow, period=day_range(tomorrow), events=()),
    )


def test_fetch_icals_returns_models_in_url_order() -> None:
    urls = ("https://example.com/a.ics", "https://example.com/b.ics")

    fetched = fetch_icals(urls)

    assert tuple(item.source_index for item in fetched) == (0, 1)
    assert tuple(item.url for item in fetched) == urls


def test_parse_icals_returns_today_and_tomorrow_frames() -> None:
    today = date(2026, 5, 29)

    window = parse_icals((), today)

    assert window.today.day == today
    assert window.tomorrow.day == date(2026, 5, 30)
    assert window.today.events == ()
    assert window.tomorrow.events == ()


def test_render_png_is_deterministic() -> None:
    window = make_window(date(2026, 5, 29))

    first = render_png(window)
    second = render_png(window)

    assert first == second
    assert first.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_send_dot_image_fails_until_real_api_is_implemented() -> None:
    config = AppConfig(
        ical_urls=("https://example.com/a.ics",),
        dot_api_token="token",
        dot_device_id="device",
    )

    with pytest.raises(HandyCalendarError, match="Dot 送信は未実装"):
        send_dot_image(config, PngImage(content=b"png", width=1, height=1))
