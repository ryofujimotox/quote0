"""dot.py の単体テスト。"""

from __future__ import annotations

import base64

import pytest
from quote0_client.exceptions import Quote0Error
from quote0_client.models import APIResponse

from quote0.models import PngImage
from quote0.steps import dot as dot_module
from quote0.steps.dot import send_dot_image

from tests.factories import VALID_PNG, make_dot_config


def test_send_dot_image_posts_base64_png(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key

        def send_image(self, device_id: str, content) -> APIResponse:
            captured["device_id"] = device_id
            captured["content"] = content.model_dump(exclude_none=True)
            return APIResponse(code=200, message="ok")

        def close(self) -> None:
            captured["closed"] = True

    monkeypatch.setattr(dot_module, "Quote0Client", FakeClient)

    result = send_dot_image(make_dot_config(), VALID_PNG)

    assert result.status_code == 200
    assert captured["api_key"] == "token"
    assert captured["device_id"] == "device"
    assert captured["closed"] is True
    assert captured["content"]["refreshNow"] is True
    assert captured["content"]["image"] == base64.b64encode(VALID_PNG.content).decode("ascii")
    assert captured["content"]["border"] == 0
    assert captured["content"]["ditherType"] == "NONE"


def test_send_dot_image_fails_when_api_code_is_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __init__(self, api_key: str) -> None:
            pass

        def send_image(self, device_id: str, content) -> APIResponse:
            return APIResponse(code=400, message="bad")

        def close(self) -> None:
            pass

    monkeypatch.setattr(dot_module, "Quote0Client", FakeClient)

    with pytest.raises(Quote0Error, match="Dot 送信失敗 code=400"):
        send_dot_image(make_dot_config(), VALID_PNG)


def test_send_dot_image_fails_when_image_size_is_invalid() -> None:
    invalid = PngImage(content=b"png", width=1, height=1)

    with pytest.raises(Quote0Error, match="invalid_image_size"):
        send_dot_image(make_dot_config(), invalid)
