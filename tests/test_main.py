"""main.py の単体テスト。"""

from __future__ import annotations

from datetime import datetime

from quote0.vendor.quote0_client.exceptions import Quote0Error
from quote0.vendor.quote0_client.models import APIResponse, ImageContentRequest

from quote0 import main as main_module
from quote0.custom.ical_image import CustomIcalImageContentRequest
from quote0.custom.ical_image.ical_models import JST

from tests.custom.ical_image.factories import ICS_URL_A, make_dot_config

BATCH_START = datetime(2026, 5, 29, 8, 0, tzinfo=JST)
DOT_IMAGE_REQUEST = ImageContentRequest(
    refreshNow=True,
    image="aW1n",
    border=0,
    ditherType="NONE",
)


def test_main_runs_client_send_image_with_image_content_request(monkeypatch) -> None:
    called: list[str] = []
    config = make_dot_config()
    captured: dict[str, object] = {}

    monkeypatch.setattr(main_module, "_batch_start_now", lambda: BATCH_START)
    monkeypatch.setattr(main_module, "load_config", lambda: config)

    def fake_to_image_content_request(self: CustomIcalImageContentRequest) -> ImageContentRequest:
        captured["ical_urls"] = self.ical_urls
        captured["reference_now"] = self.reference_now
        return DOT_IMAGE_REQUEST

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key

        def send_image(self, device_id: str, content: ImageContentRequest) -> APIResponse:
            called.append("send_image")
            captured["device_id"] = device_id
            captured["content"] = content
            return APIResponse(code=200, message="ok")

        def close(self) -> None:
            called.append("close")

    monkeypatch.setattr(
        CustomIcalImageContentRequest,
        "to_image_content_request",
        fake_to_image_content_request,
    )
    monkeypatch.setattr(main_module, "Quote0Client", FakeClient)

    assert main_module.main() == 0
    assert called == ["send_image", "close"]
    assert captured["api_key"] == config.dot_api_token
    assert captured["device_id"] == config.dot_device_id
    assert captured["content"] is DOT_IMAGE_REQUEST
    assert captured["ical_urls"] == config.ical_urls
    assert captured["reference_now"] == BATCH_START


def test_main_passes_batch_start_in_custom_request(monkeypatch) -> None:
    """取得前に固定した reference_now を CustomIcalImageContentRequest に渡す。"""
    captured: dict[str, object] = {}

    monkeypatch.setattr(main_module, "_batch_start_now", lambda: BATCH_START)
    monkeypatch.setattr(main_module, "load_config", make_dot_config)

    def fake_to_image_content_request(self: CustomIcalImageContentRequest) -> ImageContentRequest:
        captured["reference_now"] = self.reference_now
        return DOT_IMAGE_REQUEST

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            pass

        def send_image(self, device_id: str, content: ImageContentRequest) -> APIResponse:
            return APIResponse(code=200, message="ok")

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        CustomIcalImageContentRequest,
        "to_image_content_request",
        fake_to_image_content_request,
    )
    monkeypatch.setattr(main_module, "Quote0Client", FakeClient)

    assert main_module.main() == 0
    assert captured == {"reference_now": BATCH_START}


def test_main_returns_non_zero_and_stops_when_step_fails(monkeypatch, capsys) -> None:
    called: list[str] = []

    monkeypatch.setattr(main_module, "_batch_start_now", lambda: BATCH_START)
    monkeypatch.setattr(main_module, "load_config", make_dot_config)

    def broken_to_image_content_request(self: CustomIcalImageContentRequest) -> ImageContentRequest:
        raise Quote0Error(f"iCal 取得失敗 url={ICS_URL_A}")

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            pass

        def send_image(self, device_id: str, content: ImageContentRequest) -> APIResponse:
            called.append("send_image")
            return APIResponse(code=200, message="ok")

        def close(self) -> None:
            called.append("close")

    monkeypatch.setattr(
        CustomIcalImageContentRequest,
        "to_image_content_request",
        broken_to_image_content_request,
    )
    monkeypatch.setattr(main_module, "Quote0Client", FakeClient)

    assert main_module.main() == 1
    assert called == []
    assert "iCal 取得失敗" in capsys.readouterr().err


def test_main_returns_non_zero_when_dot_send_fails(monkeypatch, capsys) -> None:
    monkeypatch.setattr(main_module, "_batch_start_now", lambda: BATCH_START)
    monkeypatch.setattr(main_module, "load_config", make_dot_config)
    monkeypatch.setattr(
        CustomIcalImageContentRequest,
        "to_image_content_request",
        lambda _self: DOT_IMAGE_REQUEST,
    )

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            pass

        def send_image(self, device_id: str, content: ImageContentRequest) -> APIResponse:
            raise Quote0Error("Dot 送信失敗 code=400")

        def close(self) -> None:
            pass

    monkeypatch.setattr(main_module, "Quote0Client", FakeClient)

    assert main_module.main() == 1
    assert "Dot 送信失敗 code=400" in capsys.readouterr().err


def test_main_returns_non_zero_when_dot_network_fails(monkeypatch, capsys) -> None:
    monkeypatch.setattr(main_module, "_batch_start_now", lambda: BATCH_START)
    monkeypatch.setattr(main_module, "load_config", make_dot_config)
    monkeypatch.setattr(
        CustomIcalImageContentRequest,
        "to_image_content_request",
        lambda _self: DOT_IMAGE_REQUEST,
    )

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            pass

        def send_image(self, device_id: str, content: ImageContentRequest) -> APIResponse:
            raise Quote0Error("Dot 送信失敗 reason=connection refused")

        def close(self) -> None:
            pass

    monkeypatch.setattr(main_module, "Quote0Client", FakeClient)

    assert main_module.main() == 1
    assert "Dot 送信失敗 reason=" in capsys.readouterr().err


def test_main_returns_non_zero_when_dot_auth_fails(monkeypatch, capsys) -> None:
    monkeypatch.setattr(main_module, "_batch_start_now", lambda: BATCH_START)
    monkeypatch.setattr(main_module, "load_config", make_dot_config)
    monkeypatch.setattr(
        CustomIcalImageContentRequest,
        "to_image_content_request",
        lambda _self: DOT_IMAGE_REQUEST,
    )

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            pass

        def send_image(self, device_id: str, content: ImageContentRequest) -> APIResponse:
            raise Quote0Error("Dot 送信失敗: API キーが無効です")

        def close(self) -> None:
            pass

    monkeypatch.setattr(main_module, "Quote0Client", FakeClient)

    assert main_module.main() == 1
    assert "Dot 送信失敗: API キーが無効です" in capsys.readouterr().err
