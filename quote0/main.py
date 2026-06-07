"""アプリケーション起動の骨組み。"""

from __future__ import annotations

import sys
from datetime import datetime

from quote0.vendor.quote0_client.exceptions import Quote0Error

from .config import load_config
from .custom.ical_image import CustomIcalImageContentRequest
from .custom.ical_image.ical_models import JST
from .custom.jp_quote0_client import JpQuote0Client as Quote0Client


def log_error(message: str) -> None:
    """cron で追えるように stderr へ日本語の失敗理由を出す。"""
    print(message, file=sys.stderr)


def _batch_start_now() -> datetime:
    """バッチ開始時点の JST 日時。テストでは差し替え可能。"""
    return datetime.now(JST)


def main() -> int:
    """設定読込後、iCal 画像リクエストを組み立てて Dot へ送信する。"""
    client = None
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
        client.send_image(dot_device_id, content)
    except Quote0Error as exc:
        log_error(f"起動失敗: {exc}")
        return 1
    except Exception as exc:
        log_error(f"起動失敗: 想定外のエラーです: {exc}")
        return 1
    finally:
        if client is not None:
            client.close()

    print(
        "バッチ完了: iCal取得→解析→PNG→Dot送信 "
        f"(ical_urls={len(ical_urls)}件, device_id={dot_device_id})",
        flush=True,
    )
    return 0
