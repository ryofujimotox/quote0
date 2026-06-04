"""アプリケーション起動の骨組み。"""

from __future__ import annotations

import sys
from datetime import datetime

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

from .config import load_config
from .custom.ical_image import CustomIcalImageContentRequest
from .custom.ical_image.ical_models import JST


def log_error(message: str) -> None:
    """cron で追えるように stderr へ日本語の失敗理由を出す。"""
    print(message, file=sys.stderr)


def _batch_start_now() -> datetime:
    """バッチ開始時点の JST 日時。テストでは差し替え可能。"""
    return datetime.now(JST)


def _send_dot_image(
    client: Quote0Client,
    device_id: str,
    content: ImageContentRequest,
) -> None:
    """Dot 画像送信。失敗時は日本語の Quote0Error に揃える。"""
    try:
        response = client.send_image(device_id, content)
    except httpx.RequestError as exc:
        raise Quote0Error(f"Dot 送信失敗 reason={exc}") from exc
    except AuthenticationError as exc:
        raise Quote0Error("Dot 送信失敗: API キーが無効です") from exc
    except NotFoundError as exc:
        raise Quote0Error(f"Dot 送信失敗: デバイスが見つかりません device_id={device_id}") from exc
    except PermissionError as exc:
        raise Quote0Error("Dot 送信失敗: 権限がありません") from exc
    except ValidationError as exc:
        raise Quote0Error("Dot 送信失敗: リクエストが不正です") from exc
    except RateLimitError as exc:
        raise Quote0Error("Dot 送信失敗: レート制限を超えました") from exc
    except Quote0Error as exc:
        raise Quote0Error(f"Dot 送信失敗: {exc}") from exc
    if not response.success:
        raise Quote0Error(f"Dot 送信失敗 code={response.code}")


def main() -> int:
    """設定読込後、iCal 画像リクエストを組み立てて Dot へ送信する。"""
    try:
        # 設定を読み込む
        config = load_config()
        ical_urls = config.ical_urls
        dot_api_token = config.dot_api_token
        dot_device_id = config.dot_device_id
        
        # iCal 画像リクエストを組み立てる
        reference_now = _batch_start_now()
        content = CustomIcalImageContentRequest(
            ical_urls=ical_urls,
            reference_now=reference_now,
        ).to_image_content_request()
        print(
            f"Dot 送信: device_id={dot_device_id}, bytes={len(content.image)}",
            flush=True,
        )
        
        # Dot API を使用して画像を送信
        client = Quote0Client(api_key=dot_api_token)
        try:
            _send_dot_image(client, dot_device_id, content)
        finally:
            client.close()
    except Quote0Error as exc:
        log_error(f"起動失敗: {exc}")
        return 1
    except Exception as exc:
        log_error(f"起動失敗: 想定外のエラーです: {exc}")
        return 1

    print(
        "バッチ完了: iCal取得→解析→PNG→Dot送信 "
        f"(ical_urls={len(config.ical_urls)}件, device_id={dot_device_id})",
        flush=True,
    )
    return 0
