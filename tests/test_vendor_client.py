"""quote0/vendor/quote0_client の単体テスト。"""

from __future__ import annotations

import json

import httpx

from quote0.vendor.quote0_client.client import Quote0Client, _api_response_from_http


def _fake_response(*, status: int, payload: object) -> httpx.Response:
    content = json.dumps(payload).encode("utf-8") if payload is not None else b""
    request = httpx.Request("POST", "https://dot.mindreset.tech/api/authV2/open/device/x/image")
    return httpx.Response(status, json=payload, request=request, content=content)


def test_api_response_from_http_uses_status_when_code_missing() -> None:
    response = _api_response_from_http(_fake_response(status=200, payload={"message": "ok"}))

    assert response.code == 200
    assert response.message == "ok"
    assert response.success is True


def test_api_response_from_http_keeps_body_code() -> None:
    response = _api_response_from_http(_fake_response(status=200, payload={"code": 400, "message": "bad"}))

    assert response.code == 400
    assert response.success is False


def test_quote0_client_uses_legacy_timeout_and_user_agent() -> None:
    client = Quote0Client(api_key="test-key")
    try:
        assert client.REQUEST_TIMEOUT_SECONDS == 20.0
        assert client._client.timeout.connect == 20.0
        assert client.USER_AGENT == "quote0/0"
    finally:
        client.close()
