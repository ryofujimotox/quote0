"""main.py の単体テスト。"""

from __future__ import annotations

from datetime import datetime

from quote0_client.exceptions import Quote0Error

from quote0 import main as main_module
from quote0.models import CalendarWindow, DotSendResult, FetchedIcal, JST, PngImage

from tests.factories import ICS_URL_A, make_dot_config, make_empty_window

BATCH_START = datetime(2026, 5, 29, 8, 0, tzinfo=JST)


def test_main_runs_steps_in_order(monkeypatch) -> None:
    called: list[str] = []
    fetched = (FetchedIcal(source_index=0, url=ICS_URL_A, text="ics"),)
    window = make_empty_window()
    image = PngImage(content=b"png", width=1, height=1)
    config = make_dot_config()

    monkeypatch.setattr(main_module, "_batch_start_now", lambda: BATCH_START)
    monkeypatch.setattr(main_module, "load_config", lambda: config)

    def fetch_icals(urls: tuple[str, ...]) -> tuple[FetchedIcal, ...]:
        called.append("fetch")
        assert urls == config.ical_urls
        return fetched

    def parse_icals(
        calendars: tuple[FetchedIcal, ...],
        today,
        *,
        reference_now=None,
    ) -> CalendarWindow:
        called.append("parse")
        assert calendars == fetched
        assert today == window.today.day
        assert reference_now == BATCH_START
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


def test_main_passes_batch_start_before_fetch(monkeypatch) -> None:
    """取得前に固定した started_at を today と reference_now の両方に使う。"""
    captured: dict[str, object] = {}

    monkeypatch.setattr(main_module, "_batch_start_now", lambda: BATCH_START)
    monkeypatch.setattr(main_module, "load_config", make_dot_config)
    monkeypatch.setattr(
        main_module,
        "fetch_icals",
        lambda _: (FetchedIcal(source_index=0, url=ICS_URL_A, text="ics"),),
    )
    monkeypatch.setattr(main_module, "render_png", lambda _: PngImage(content=b"png", width=296, height=152))
    monkeypatch.setattr(
        main_module,
        "send_dot_image",
        lambda *_: DotSendResult(status_code=200, response_text="ok"),
    )

    def parse_icals(_calendars, today, *, reference_now=None) -> CalendarWindow:
        captured["today"] = today
        captured["reference_now"] = reference_now
        return make_empty_window()

    monkeypatch.setattr(main_module, "parse_icals", parse_icals)

    assert main_module.main() == 0
    assert captured == {
        "today": BATCH_START.date(),
        "reference_now": BATCH_START,
    }


def test_main_returns_non_zero_and_stops_when_step_fails(monkeypatch, capsys) -> None:
    called: list[str] = []

    monkeypatch.setattr(main_module, "_batch_start_now", lambda: BATCH_START)
    monkeypatch.setattr(main_module, "load_config", make_dot_config)

    def fetch_icals(_: tuple[str, ...]) -> tuple[FetchedIcal, ...]:
        called.append("fetch")
        raise Quote0Error(f"iCal 取得失敗 url={ICS_URL_A}")

    monkeypatch.setattr(main_module, "fetch_icals", fetch_icals)
    monkeypatch.setattr(main_module, "parse_icals", lambda *_: called.append("parse"))
    monkeypatch.setattr(main_module, "render_png", lambda *_: called.append("render"))
    monkeypatch.setattr(main_module, "send_dot_image", lambda *_: called.append("send"))

    assert main_module.main() == 1
    assert called == ["fetch"]
    assert "iCal 取得失敗" in capsys.readouterr().err


def test_main_returns_non_zero_when_dot_send_fails(monkeypatch, capsys) -> None:
    window = make_empty_window()

    monkeypatch.setattr(main_module, "_batch_start_now", lambda: BATCH_START)
    monkeypatch.setattr(main_module, "load_config", make_dot_config)
    monkeypatch.setattr(
        main_module,
        "fetch_icals",
        lambda _: (FetchedIcal(source_index=0, url=ICS_URL_A, text="ics"),),
    )
    monkeypatch.setattr(main_module, "parse_icals", lambda *_args, **_kwargs: window)
    monkeypatch.setattr(main_module, "render_png", lambda _: PngImage(content=b"png", width=296, height=152))
    monkeypatch.setattr(
        main_module,
        "send_dot_image",
        lambda *_: (_ for _ in ()).throw(Quote0Error("Dot 送信失敗 code=400")),
    )

    assert main_module.main() == 1
    assert "Dot 送信失敗 code=400" in capsys.readouterr().err
