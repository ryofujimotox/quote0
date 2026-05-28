"""アプリケーション起動の骨組み。"""

from __future__ import annotations

import sys

from .config import load_config
from .errors import HandyCalendarError


def log_error(message: str) -> None:
    """cron で追えるように stderr へ日本語の失敗理由を出す。"""
    print(message, file=sys.stderr)


def main() -> int:
    """設定読込までを行い、失敗時は非 0 を返す。"""
    try:
        config = load_config()
    except HandyCalendarError as exc:
        log_error(f"起動失敗: {exc}")
        return 1
    except Exception as exc:
        log_error(f"起動失敗: 想定外のエラーです: {exc}")
        return 1

    # 後続処理（iCal 取得 -> PNG 生成 -> Dot 送信）の入口になる起動確認。
    print(
        "起動確認OK: handy_calendar を開始します "
        f"(ical_urls={len(config.ical_urls)}件, device_id={config.dot_device_id})"
    )
    return 0
