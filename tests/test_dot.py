"""dot.py の単体テスト。"""

from __future__ import annotations

import json

import pytest

from handy_calendar.errors import HandyCalendarError
from handy_calendar.models import DotSendResult, PngImage
from handy_calendar.steps import dot as dot_module
from handy_calendar.steps.dot import send_dot_image

from tests.factories import DOT_API_URL, FakeJsonResponse, VALID_PNG, make_dot_config

EXPECTED_DOT_BODY = {
    "refreshNow": True,
    "image": "cG5n",
    "border": 0,
    "ditherType": "NONE",
}


def test_send_dot_image_posts_base64_png(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def urlopen(request, timeout: int):
        captured["timeout"] = timeout
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeJsonResponse({"code": 200, "message": "ok"})

    monkeypatch.setattr(dot_module, "urlopen", urlopen)

    result = send_dot_image(make_dot_config(), VALID_PNG)

    assert result == DotSendResult(status_code=200, response_text='{"code": 200, "message": "ok"}')
    assert {
        "timeout": captured["timeout"],
        "url": captured["url"],
        "authorization": captured["headers"]["Authorization"],
        "body": captured["body"],
    } == {
        "timeout": 20,
        "url": DOT_API_URL,
        "authorization": "Bearer token",
        "body": EXPECTED_DOT_BODY,
    }


def test_send_dot_image_fails_when_api_code_is_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        dot_module,
        "urlopen",
        lambda *_args, **_kwargs: FakeJsonResponse({"code": 400}),
    )

    with pytest.raises(HandyCalendarError, match="Dot 送信失敗 code=400"):
        send_dot_image(make_dot_config(), VALID_PNG)


def test_send_dot_image_fails_when_image_size_is_invalid() -> None:
    invalid = PngImage(content=b"png", width=1, height=1)

    with pytest.raises(HandyCalendarError, match="invalid_image_size"):
        send_dot_image(make_dot_config(), invalid)
