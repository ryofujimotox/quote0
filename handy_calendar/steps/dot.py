"""Dot 送信の仮実装。"""

from __future__ import annotations

from ..config import AppConfig
from ..errors import HandyCalendarError
from ..models import DotSendResult, PngImage


def send_dot_image(config: AppConfig, image: PngImage) -> DotSendResult:
    """Dot Image API 送信結果を返す仮の送信。

    例: AppConfig(ical_urls=(…), dot_api_token="…", dot_device_id="quote-0"),
        PngImage(content=b"\\x89PNG\\r\\n…", width=1, height=1)
        → 実送信を実装するまで HandyCalendarError
    """
    print(f"Dot 送信: device_id={config.dot_device_id}, bytes={len(image.content)}")
    raise HandyCalendarError("Dot 送信は未実装です。実送信を行わないため更新しません。")
