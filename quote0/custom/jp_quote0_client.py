"""Dot API クライアントの日本語エラー拡張。"""

from __future__ import annotations

import httpx
from quote0_client import Quote0Client
from quote0_client.exceptions import (
    AuthenticationError,
    NotFoundError,
    PermissionError,
    Quote0Error,
    RateLimitError,
    ValidationError,
)
from quote0_client.models import ImageContentRequest


class JpQuote0Client(Quote0Client):
    """Quote0Client の HTTP エラーを日本語 Quote0Error に揃える拡張。"""

    def _request(self, method: str, path: str, **kwargs):
        try:
            return super()._request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise Quote0Error(f"Dot 送信失敗 reason={exc}") from exc

    def _handle_response(self, response: httpx.Response) -> None:
        """HTTP ステータスを日本語例外に変換する（vendor の型分けは維持）。"""
        status_code = response.status_code

        if status_code == 200:
            return
        if status_code == 400:
            raise ValidationError("Dot 送信失敗: リクエストが不正です")
        if status_code == 401:
            raise AuthenticationError("Dot 送信失敗: API キーが無効です")
        if status_code == 403:
            raise PermissionError("Dot 送信失敗: 権限がありません")
        if status_code == 404:
            raise NotFoundError("Dot 送信失敗: デバイスが見つかりません")
        if status_code == 429:
            raise RateLimitError("Dot 送信失敗: レート制限を超えました")
        if 500 <= status_code < 600:
            raise Quote0Error(f"Dot 送信失敗: サーバーエラー status={status_code}")
        raise Quote0Error(f"Dot 送信失敗: 想定外のステータス status={status_code}")

    def send_image(self, device_id: str, content: ImageContentRequest):
        response = super().send_image(device_id, content)
        if not response.success:
            raise Quote0Error(f"Dot 送信失敗 code={response.code}")
        return response
