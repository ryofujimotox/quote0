"""quote0.commands.get_devices の単体テスト。"""

from __future__ import annotations

import json

import pytest

from quote0.config import ConfigError
from quote0.commands.get_devices import main as get_devices_main
from quote0.commands.get_devices.config import load_dot_api_token
from quote0.vendor.quote0_client.exceptions import Quote0Error
from quote0.vendor.quote0_client.models import Device


def test_load_dot_api_token_fails_when_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("DOT_API_TOKEN", raising=False)

    with pytest.raises(ConfigError, match="DOT_API_TOKEN が未設定"):
        load_dot_api_token(tmp_path / ".env")


def test_load_dot_api_token_strips_whitespace(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("DOT_API_TOKEN", " token ")

    assert load_dot_api_token(tmp_path / ".env") == "token"


def test_format_devices_returns_json_array() -> None:
    devices = [
        Device(series="quote", model="quote_0", edition=1, id="abc123"),
        Device(series="quote", model="quote_0", edition=2, id="def456"),
    ]

    payload = json.loads(get_devices_main.format_devices(devices))

    assert payload == [
        {"series": "quote", "model": "quote_0", "edition": 1, "id": "abc123"},
        {"series": "quote", "model": "quote_0", "edition": 2, "id": "def456"},
    ]


def test_format_devices_includes_alias_and_location_when_set() -> None:
    devices = [
        Device(
            series="quote",
            model="quote_0",
            edition=1,
            id="abc123",
            alias="寝室",
            location="2F",
        ),
    ]

    payload = json.loads(get_devices_main.format_devices(devices))

    assert payload == [
        {
            "series": "quote",
            "model": "quote_0",
            "edition": 1,
            "id": "abc123",
            "alias": "寝室",
            "location": "2F",
        },
    ]


def test_main_prints_devices_as_json_array_and_returns_zero(monkeypatch, capsys) -> None:
    called: list[str] = []
    devices = [
        Device(series="quote", model="quote_0", edition=1, id="device-a"),
        Device(series="quote", model="quote_0", edition=2, id="device-b"),
    ]

    monkeypatch.setattr(get_devices_main, "load_dot_api_token", lambda: "token")

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            assert api_key == "token"

        def get_devices(self) -> list[Device]:
            called.append("get_devices")
            return devices

        def close(self) -> None:
            called.append("close")

    monkeypatch.setattr(get_devices_main, "Quote0Client", FakeClient)

    assert get_devices_main.main() == 0
    assert called == ["get_devices", "close"]
    assert json.loads(capsys.readouterr().out) == [
        {"series": "quote", "model": "quote_0", "edition": 1, "id": "device-a"},
        {"series": "quote", "model": "quote_0", "edition": 2, "id": "device-b"},
    ]


def test_main_returns_one_when_no_devices(monkeypatch, capsys) -> None:
    monkeypatch.setattr(get_devices_main, "load_dot_api_token", lambda: "token")

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            pass

        def get_devices(self) -> list[Device]:
            return []

        def close(self) -> None:
            pass

    monkeypatch.setattr(get_devices_main, "Quote0Client", FakeClient)

    assert get_devices_main.main() == 1
    assert "登録済みデバイスがありません" in capsys.readouterr().err


def test_main_returns_one_on_quote0_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(get_devices_main, "load_dot_api_token", lambda: "token")

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            pass

        def get_devices(self) -> list[Device]:
            raise Quote0Error("API 失敗")

        def close(self) -> None:
            pass

    monkeypatch.setattr(get_devices_main, "Quote0Client", FakeClient)

    assert get_devices_main.main() == 1
    assert "デバイス一覧取得失敗: API 失敗" in capsys.readouterr().err
