"""アプリケーション起動の骨組み。"""

from __future__ import annotations

import sys
from datetime import datetime

from .config import load_config
from .errors import HandyCalendarError
from .models import JST
from .steps.dot import send_dot_image
from .steps.ical import fetch_icals, parse_icals
from .steps.render import render_png


def log_error(message: str) -> None:
    """cron で追えるように stderr へ日本語の失敗理由を出す。"""
    print(message, file=sys.stderr)


def _batch_start_now() -> datetime:
    """バッチ開始時点の JST 日時。テストでは差し替え可能。"""
    return datetime.now(JST)


def main() -> int:
    """設定読込後、仮の処理段を順番に実行する。"""
    try:
        config = load_config()
        # 基準日・終了済み判定は取得前の同一時刻を使う（取得中の経過で判定がずれない）
        started_at = _batch_start_now()
        today = started_at.date()
        calendars = fetch_icals(config.ical_urls)
        print(f"iCal 取得完了: {len(calendars)}件", flush=True)
        calendar = parse_icals(calendars, today, reference_now=started_at)
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
