"""登録済みデバイス一覧を JSON で表示する CLI。"""

from __future__ import annotations

import json
import sys

from quote0.content.jp_quote0_client import JpQuote0Client as Quote0Client
from quote0.vendor.quote0_client.exceptions import Quote0Error
from quote0.vendor.quote0_client.models import Device

from .config import load_dot_api_token


def log_error(message: str) -> None:
    """失敗理由を stderr へ出す。"""
    print(message, file=sys.stderr)


def format_devices(devices: list[Device]) -> str:
    """get_devices の各 Device を JSON 配列へ整形する。"""
    return json.dumps(
        [device.model_dump(exclude_none=True) for device in devices],
        ensure_ascii=False,
        indent=2,
    )


def main() -> int:
    """DOT_API_TOKEN で Dot API を呼び、登録済みデバイス一覧を stdout へ出す。"""
    client = None
    try:
        # API キーを読み込む
        dot_api_token = load_dot_api_token()
        # 登録済みデバイスを取得
        client = Quote0Client(api_key=dot_api_token)
        devices = client.get_devices()
        if not devices:
            log_error("登録済みデバイスがありません。")
            return 1

        # JSON 配列を stdout へ出す
        print(format_devices(devices))
    except Quote0Error as exc:
        log_error(f"デバイス一覧取得失敗: {exc}")
        return 1
    except Exception as exc:
        log_error(f"デバイス一覧取得失敗: 想定外のエラーです: {exc}")
        return 1
    finally:
        if client is not None:
            client.close()

    return 0
