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
    print(message, file=sys.stderr, flush=True)


def log_info(message: str) -> None:
    """成功系の段ログは stdout へ出す。"""
    print(message, flush=True)


def _batch_start_now() -> datetime:
    """バッチ開始時点の JST 日時。テストでは差し替え可能。"""
    return datetime.now(JST)


def main() -> int:
    """設定読込後、iCal 取得 → 解析 → PNG 生成 → Dot 送信を順に実行する。"""
    try:
        config = load_config()
        # 基準日・終了済み判定は取得前の同一時刻を使う（取得中の経過で判定がずれない）
        started_at = _batch_start_now()
        today = started_at.date()
        log_info(f"iCal 取得開始: urls={len(config.ical_urls)}件")
        calendars = fetch_icals(config.ical_urls, debug=config.debug_logs)
        log_info(f"iCal 取得成功: calendars={len(calendars)}件")

        log_info(f"iCal 解析開始: calendars={len(calendars)}件 today={today.isoformat()}")
        calendar = parse_icals(calendars, today, reference_now=started_at, debug=config.debug_logs)
        log_info(
            "iCal 解析成功: "
            f"today_events={len(calendar.today.events)}件 "
            f"next_day={calendar.next_day.day.isoformat()} "
            f"next_day_events={len(calendar.next_day.events)}件"
        )

        log_info("PNG 生成開始")
        image = render_png(calendar)
        log_info(f"PNG 生成成功: bytes={len(image.content)} size={image.width}x{image.height}")

        log_info(f"Dot 送信開始: device_id={config.dot_device_id} bytes={len(image.content)}")
        send_dot_image(config, image, debug=config.debug_logs)
        log_info(f"Dot 送信成功: device_id={config.dot_device_id}")
    except HandyCalendarError as exc:
        log_error(f"起動失敗: stage_error reason={exc}")
        return 1
    except Exception as exc:
        log_error(f"起動失敗: 想定外のエラーです: {exc}")
        return 1

    log_info(
        "バッチ完了: iCal取得→解析→PNG→Dot送信 "
        f"(ical_urls={len(config.ical_urls)}件, device_id={config.dot_device_id})"
    )
    return 0
