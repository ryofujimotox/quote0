"""iCal から PNG を生成し Dot 画像リクエストに変換する拡張。"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime

from quote0_client.exceptions import Quote0Error
from quote0_client.models import ImageContentRequest

from ..models import PngImage
from ..steps.ical import fetch_icals, parse_icals
from ..steps.render import render_png


@dataclass(frozen=True)
class CustomIcalImageContentRequest:
    """公開 iCal URL から Dot 画像リクエストを組み立てる拡張。

    例: CustomIcalImageContentRequest(
            ical_urls=("https://cal.example/a.ics",),
            reference_now=datetime(2026, 5, 29, 0, 10, tzinfo=JST),
        ).to_image_content_request()
    """

    ical_urls: tuple[str, ...]
    reference_now: datetime

    def to_image_content_request(self) -> ImageContentRequest:
        today = self.reference_now.date()
        calendars = fetch_icals(self.ical_urls)
        calendar = parse_icals(calendars, today, reference_now=self.reference_now)
        return png_to_image_content_request(render_png(calendar))


def png_to_image_content_request(image: PngImage) -> ImageContentRequest:
    """PngImage を Dot Image API 用リクエストに変換する。"""
    if image.content_type != "image/png":
        raise Quote0Error(f"Dot 送信失敗 reason=invalid_content_type:{image.content_type}")
    if image.width != 296 or image.height != 152:
        raise Quote0Error(f"Dot 送信失敗 reason=invalid_image_size:{image.width}x{image.height}")
    return ImageContentRequest(
        refreshNow=True,
        image=base64.b64encode(image.content).decode("ascii"),
        border=0,
        ditherType="NONE",
    )
