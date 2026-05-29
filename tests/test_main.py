"""main.py の単体テスト。"""

from __future__ import annotations

from datetime import date, timedelta

from handy_calendar.config import AppConfig
from handy_calendar.errors import HandyCalendarError
from handy_calendar import main as main_module
from handy_calendar.models import CalendarWindow, DaySchedule, DotSendResult, FetchedIcal, PngImage
from handy_calendar.steps.ical import day_range


def make_config() -> AppConfig:
    return AppConfig(
        ical_urls=("https://example.com/a.ics",),
        dot_api_token="token",
        dot_device_id="device",
    )


def make_window(today: date = date(2026, 5, 29)) -> CalendarWindow:
    tomorrow = today + timedelta(days=1)
    return CalendarWindow(
        today=DaySchedule(day=today, period=day_range(today), events=()),
        tomorrow=DaySchedule(day=tomorrow, period=day_range(tomorrow), events=()),
    )


def test_main_runs_steps_in_order(monkeypatch) -> None:
    called: list[str] = []
    fetched = (FetchedIcal(source_index=0, url="https://example.com/a.ics", text="ics"),)
    window = make_window()
    image = PngImage(content=b"png", width=1, height=1)

    monkeypatch.setattr(
        main_module,
        "load_config",
        make_config,
    )
    monkeypatch.setattr(main_module, "today_in_jst", lambda: window.today.day)

    def fetch_icals(urls: tuple[str, ...]) -> tuple[FetchedIcal, ...]:
        called.append("fetch")
        assert urls == make_config().ical_urls
        return fetched

    def parse_icals(calendars: tuple[FetchedIcal, ...], today) -> CalendarWindow:
        called.append("parse")
        assert calendars == fetched
        assert today == window.today.day
        return window

    def render_png(calendar: CalendarWindow) -> PngImage:
        called.append("render")
        assert calendar == window
        return image

    def send_dot_image(config: AppConfig, png: PngImage) -> DotSendResult:
        called.append("send")
        assert config == make_config()
        assert png == image
        return DotSendResult(status_code=200, response_text="ok")

    monkeypatch.setattr(main_module, "fetch_icals", fetch_icals)
    monkeypatch.setattr(main_module, "parse_icals", parse_icals)
    monkeypatch.setattr(main_module, "render_png", render_png)
    monkeypatch.setattr(main_module, "send_dot_image", send_dot_image)

    assert main_module.main() == 0
    assert called == ["fetch", "parse", "render", "send"]


def test_main_returns_non_zero_and_stops_when_step_fails(monkeypatch, capsys) -> None:
    called: list[str] = []
    monkeypatch.setattr(
        main_module,
        "load_config",
        make_config,
    )
    window = make_window()
    monkeypatch.setattr(main_module, "today_in_jst", lambda: window.today.day)

    def fetch_icals(_: tuple[str, ...]) -> tuple[FetchedIcal, ...]:
        called.append("fetch")
        raise HandyCalendarError("iCal 取得失敗 url=https://example.com/a.ics")

    monkeypatch.setattr(main_module, "fetch_icals", fetch_icals)
    monkeypatch.setattr(main_module, "parse_icals", lambda *_: called.append("parse"))
    monkeypatch.setattr(main_module, "render_png", lambda *_: called.append("render"))
    monkeypatch.setattr(main_module, "send_dot_image", lambda *_: called.append("send"))

    assert main_module.main() == 1
    assert called == ["fetch"]
    assert "iCal 取得失敗" in capsys.readouterr().err
