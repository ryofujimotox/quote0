"""custom/jp_quote0_client.py の単体テスト。"""

from __future__ import annotations

import json

import httpx
import pytest
from quote0_client.exceptions import AuthenticationError, Quote0Error, ValidationError

from quote0.custom.jp_quote0_client import JpQuote0Client


def _fake_response(*, status: int) -> httpx.Response:
    request = httpx.Request("POST", "https://dot.mindreset.tech/api/authV2/open/device/x/image")
    return httpx.Response(status, json={}, request=request, content=json.dumps({}).encode("utf-8"))


def test_handle_response_raises_japanese_authentication_error() -> None:
    client = JpQuote0Client(api_key="test-key")
    try:
        with pytest.raises(AuthenticationError, match="Dot 送信失敗: API キーが無効です"):
            client._handle_response(_fake_response(status=401))
    finally:
        client.close()


def test_handle_response_raises_japanese_validation_error() -> None:
    client = JpQuote0Client(api_key="test-key")
    try:
        with pytest.raises(ValidationError, match="Dot 送信失敗: リクエストが不正です"):
            client._handle_response(_fake_response(status=400))
    finally:
        client.close()


def test_request_wraps_network_error_as_quote0_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = JpQuote0Client(api_key="test-key")

    def broken_request(method: str, url: str, **kwargs):
        raise httpx.ConnectError("connection refused", request=httpx.Request("POST", url))

    monkeypatch.setattr(client._client, "request", broken_request)
    try:
        with pytest.raises(Quote0Error, match="Dot 送信失敗 reason="):
            client._request("POST", "/api/authV2/open/device/x/image")
    finally:
        client.close()
