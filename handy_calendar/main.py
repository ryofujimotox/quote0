"""アプリケーション起動の骨組み。"""

from __future__ import annotations

import sys

from .config import load_config
from .errors import HandyCalendarError
from .steps.dot import send_dot_image
from .steps.ical import fetch_icals, parse_icals, today_in_jst
from .steps.render import render_png


def log_error(message: str) -> None:
    """cron で追えるように stderr へ日本語の失敗理由を出す。"""
    print(message, file=sys.stderr)


def main() -> int:
    """設定読込後、仮の処理段を順番に実行する。"""
    try:
        config = load_config()
        today = today_in_jst()
        calendars = fetch_icals(config.ical_urls)
        print(f"iCal 取得完了: {len(calendars)}件", flush=True)
        calendar = parse_icals(calendars, today)
        print(
            "iCal 解析完了: "
            f"today={len(calendar.today.events)}件, "
            f"next_day={calendar.next_day.day.isoformat()}({len(calendar.next_day.events)}件)",
            flush=True,
        )
        image = render_png(calendar)
        send_dot_image(config, image)
    except HandyCalendarError as exc:
        log_error(f"起動失敗: {exc}")
        return 1
    except Exception as exc:
        log_error(f"起動失敗: 想定外のエラーです: {exc}")
        return 1

    print(
        "起動確認OK: handy_calendar の仮処理が完了しました "
        f"(ical_urls={len(config.ical_urls)}件, device_id={config.dot_device_id})"
    )
    return 0
