"""ical_image/request.py の単体テスト。"""

from __future__ import annotations

import base64
from datetime import date, datetime, timezone

import pytest
from quote0.vendor.quote0_client.exceptions import Quote0Error

from quote0.content.ical_image import CustomIcalImageContentRequest, png_to_image_content_request
from quote0.content.ical_image import request as request_module
from quote0.content.ical_image.ical import normalize_reference_now_jst, parse_icals
from quote0.content.ical_image.ical_models import FetchedIcal, JST, PngImage

from tests.content.ical_image.factories import ICS_URL_A, VALID_PNG, make_empty_window

BATCH_START = datetime(2026, 5, 29, 8, 0, tzinfo=JST)


def test_png_to_image_content_request_encodes_valid_png() -> None:
    request = png_to_image_content_request(VALID_PNG)

    assert request.refreshNow is True
    assert request.border == 0
    assert request.ditherType == "NONE"
    assert request.image == base64.b64encode(VALID_PNG.content).decode("ascii")


def test_png_to_image_content_request_rejects_invalid_size() -> None:
    invalid = PngImage(content=b"png", width=1, height=1)

    with pytest.raises(Quote0Error, match="invalid_image_size"):
        png_to_image_content_request(invalid)


def test_custom_ical_image_content_request_builds_image_request(monkeypatch: pytest.MonkeyPatch) -> None:
    fetched = (FetchedIcal(source_index=0, url=ICS_URL_A, text="ics"),)
    window = make_empty_window()
    image = VALID_PNG
    captured: dict[str, object] = {}

    def fake_fetch(urls: tuple[str, ...], *, debug_logs: bool = False) -> tuple[FetchedIcal, ...]:
        captured["urls"] = urls
        captured["fetch_debug_logs"] = debug_logs
        return fetched

    def fake_parse(calendars, *, reference_now=None, debug_logs: bool = False):
        captured["reference_now"] = reference_now
        captured["parse_debug_logs"] = debug_logs
        return window

    def fake_render(calendar, *, debug_logs: bool = False) -> PngImage:
        captured["calendar"] = calendar
        captured["render_debug_logs"] = debug_logs
        return image

    monkeypatch.setattr(request_module, "fetch_icals", fake_fetch)
    monkeypatch.setattr(request_module, "parse_icals", fake_parse)
    monkeypatch.setattr(request_module, "render_png", fake_render)

    request = CustomIcalImageContentRequest(
        ical_urls=(ICS_URL_A,),
        reference_now=BATCH_START,
    ).to_image_content_request()

    assert captured["urls"] == (ICS_URL_A,)
    assert captured["reference_now"] == BATCH_START
    assert captured["calendar"] == window
    assert captured["fetch_debug_logs"] is False
    assert captured["parse_debug_logs"] is False
    assert captured["render_debug_logs"] is False
    assert request.image == base64.b64encode(image.content).decode("ascii")


def test_parse_icals_uses_jst_calendar_day_from_utc_reference_now() -> None:
    reference_utc = datetime(2026, 5, 29, 20, 0, tzinfo=timezone.utc)

    window = parse_icals((), reference_now=reference_utc)

    assert window.first_day.date == date(2026, 5, 30)


def test_normalize_reference_now_jst_treats_naive_as_jst() -> None:
    naive = datetime(2026, 5, 30, 5, 0)

    normalized = normalize_reference_now_jst(naive)

    assert normalized == naive.replace(tzinfo=JST)
    assert normalized.date() == date(2026, 5, 30)
