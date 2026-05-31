"""main.py の単体テスト。"""

from __future__ import annotations

from handy_calendar.errors import HandyCalendarError
from handy_calendar import main as main_module
from handy_calendar.models import CalendarWindow, DotSendResult, FetchedIcal, PngImage

from tests.factories import ICS_URL_A, make_dot_config, make_empty_window


def test_main_runs_steps_in_order(monkeypatch) -> None:
    called: list[str] = []
    fetched = (FetchedIcal(source_index=0, url=ICS_URL_A, text="ics"),)
    window = make_empty_window()
    image = PngImage(content=b"png", width=1, height=1)
    config = make_dot_config()

    monkeypatch.setattr(main_module, "load_config", lambda: config)
    monkeypatch.setattr(main_module, "today_in_jst", lambda: window.today.day)

    def fetch_icals(urls: tuple[str, ...]) -> tuple[FetchedIcal, ...]:
        called.append("fetch")
        assert urls == config.ical_urls
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

    def send_dot_image(cfg, png: PngImage) -> DotSendResult:
        called.append("send")
        assert cfg == config
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
    window = make_empty_window()

    monkeypatch.setattr(main_module, "load_config", make_dot_config)
    monkeypatch.setattr(main_module, "today_in_jst", lambda: window.today.day)

    def fetch_icals(_: tuple[str, ...]) -> tuple[FetchedIcal, ...]:
        called.append("fetch")
        raise HandyCalendarError(f"iCal 取得失敗 url={ICS_URL_A}")

    monkeypatch.setattr(main_module, "fetch_icals", fetch_icals)
    monkeypatch.setattr(main_module, "parse_icals", lambda *_: called.append("parse"))
    monkeypatch.setattr(main_module, "render_png", lambda *_: called.append("render"))
    monkeypatch.setattr(main_module, "send_dot_image", lambda *_: called.append("send"))

    assert main_module.main() == 1
    assert called == ["fetch"]
    assert "iCal 取得失敗" in capsys.readouterr().err


def test_main_returns_non_zero_when_dot_send_fails(monkeypatch, capsys) -> None:
    window = make_empty_window()

    monkeypatch.setattr(main_module, "load_config", make_dot_config)
    monkeypatch.setattr(main_module, "today_in_jst", lambda: window.today.day)
    monkeypatch.setattr(
        main_module,
        "fetch_icals",
        lambda _: (FetchedIcal(source_index=0, url=ICS_URL_A, text="ics"),),
    )
    monkeypatch.setattr(main_module, "parse_icals", lambda *_: window)
    monkeypatch.setattr(main_module, "render_png", lambda _: PngImage(content=b"png", width=296, height=152))
    monkeypatch.setattr(
        main_module,
        "send_dot_image",
        lambda *_: (_ for _ in ()).throw(HandyCalendarError("Dot 送信失敗 code=400")),
    )

    assert main_module.main() == 1
    assert "Dot 送信失敗 code=400" in capsys.readouterr().err
