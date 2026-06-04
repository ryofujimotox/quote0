"""ical_image.py の単体テスト。"""

from __future__ import annotations

import base64
from datetime import datetime

import pytest
from quote0_client.exceptions import Quote0Error

from quote0.content import ical_image as ical_image_module
from quote0.content.ical_image import CustomIcalImageContentRequest, png_to_image_content_request
from quote0.models import FetchedIcal, JST, PngImage

from tests.factories import ICS_URL_A, VALID_PNG, make_empty_window

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

    def fake_fetch(urls: tuple[str, ...]) -> tuple[FetchedIcal, ...]:
        captured["urls"] = urls
        return fetched

    def fake_parse(calendars, today, *, reference_now=None):
        captured["parse"] = (calendars, today, reference_now)
        return window

    def fake_render(calendar) -> PngImage:
        captured["calendar"] = calendar
        return image

    monkeypatch.setattr(ical_image_module, "fetch_icals", fake_fetch)
    monkeypatch.setattr(ical_image_module, "parse_icals", fake_parse)
    monkeypatch.setattr(ical_image_module, "render_png", fake_render)

    request = CustomIcalImageContentRequest(
        ical_urls=(ICS_URL_A,),
        reference_now=BATCH_START,
    ).to_image_content_request()

    assert captured["urls"] == (ICS_URL_A,)
    assert captured["parse"] == (fetched, BATCH_START.date(), BATCH_START)
    assert captured["calendar"] == window
    assert request.image == base64.b64encode(image.content).decode("ascii")
