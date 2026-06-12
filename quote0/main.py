"""`.env` の設定確認と Dot API / デバイスへの接続確認。"""

from __future__ import annotations

import sys

from quote0.config import load_config
from quote0.content.jp_quote0_client import JpQuote0Client as Quote0Client
from quote0.vendor.quote0_client.exceptions import Quote0Error


def log_error(message: str) -> None:
    """失敗理由を stderr へ出す。"""
    print(message, file=sys.stderr)


def main() -> int:
    """必須環境変数を検証し、Dot API と DOT_DEVICE_ID へ接続できるか確認する。"""
    client = None
    try:
        # 設定を読み込む
        config = load_config()
        dot_api_token = config.dot_api_token
        dot_device_id = config.dot_device_id

        # Dot API へ接続確認
        client = Quote0Client(api_key=dot_api_token)
        client.get_device_status(dot_device_id)
    except Quote0Error as exc:
        log_error(f"接続確認失敗: {exc}")
        return 1
    except Exception as exc:
        log_error(f"接続確認失敗: 想定外のエラーです: {exc}")
        return 1
    finally:
        if client is not None:
            client.close()

    print(f"接続確認完了: device_id={dot_device_id}", flush=True)
    return 0
