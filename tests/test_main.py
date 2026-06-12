"""main.py の単体テスト。"""

from __future__ import annotations

from quote0 import main as main_module
from quote0.vendor.quote0_client.exceptions import Quote0Error
from quote0.vendor.quote0_client.models import DeviceStatus

from tests.content.ical_image.factories import make_dot_config


def test_main_returns_zero_when_dot_connection_ok(monkeypatch) -> None:
    config = make_dot_config()
    called: list[str] = []

    monkeypatch.setattr(main_module, "load_config", lambda: config)

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            assert api_key == config.dot_api_token

        def get_device_status(self, device_id: str) -> DeviceStatus:
            called.append("get_device_status")
            assert device_id == config.dot_device_id
            return DeviceStatus(
                deviceId=device_id,
                status={
                    "version": "1",
                    "current": "ok",
                    "description": "ok",
                    "battery": "ok",
                    "wifi": "ok",
                },
                renderInfo={
                    "last": "",
                    "current": {"rotated": False, "border": 0, "image": []},
                    "next": {"battery": "", "power": ""},
                },
            )

        def close(self) -> None:
            called.append("close")

    monkeypatch.setattr(main_module, "Quote0Client", FakeClient)

    assert main_module.main() == 0
    assert called == ["get_device_status", "close"]


def test_main_returns_one_when_dot_status_fails(monkeypatch, capsys) -> None:
    monkeypatch.setattr(main_module, "load_config", make_dot_config)

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            pass

        def get_device_status(self, device_id: str) -> DeviceStatus:
            raise Quote0Error("Dot 送信失敗: デバイスが見つかりません")

        def close(self) -> None:
            pass

    monkeypatch.setattr(main_module, "Quote0Client", FakeClient)

    assert main_module.main() == 1
    assert "接続確認失敗: Dot 送信失敗: デバイスが見つかりません" in capsys.readouterr().err
