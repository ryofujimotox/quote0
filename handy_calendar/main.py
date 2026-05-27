"""アプリケーション起動の骨組み。"""

from __future__ import annotations

import sys

from .config import ConfigError, load_config


def main() -> int:
    """設定読込までを行い、起動確認用メッセージを出す。"""
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"設定エラー: {exc}", file=sys.stderr)
        return 1

    # 後続処理（iCal 取得 -> PNG 生成 -> Dot 送信）の入口になる起動ログ。
    print(
        "起動確認OK: handy_calendar を開始します "
        f"(ical_urls={len(config.ical_urls)}件, device_id={config.dot_device_id})"
    )
    return 0
