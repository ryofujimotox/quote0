"""iCal から PNG を生成し Dot 画像リクエストに変換する拡張。"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime

from quote0.vendor.quote0_client.exceptions import Quote0Error
from quote0.vendor.quote0_client.models import ImageContentRequest

from .ical import fetch_icals, parse_icals
from .ical_models import JST, PngImage
from .render import render_png


@dataclass(frozen=True)
class CustomIcalImageContentRequest:
    """公開 iCal URL から Dot 画像リクエストを組み立てる拡張。

    例: CustomIcalImageContentRequest(
            ical_urls=("https://cal.example/a.ics", "https://cal.example/b.ics"),
            reference_now=datetime(2026, 5, 29, 0, 10, tzinfo=JST),
        )
        content = image_req.to_image_content_request()
        client = Quote0Client(api_key=config.dot_api_token)
        client.send_image(config.dot_device_id, content)
    """

    ical_urls: tuple[str, ...]
    reference_now: datetime | None = None
    debug: bool = False

    def to_image_content_request(self) -> ImageContentRequest:
        reference_now = self.reference_now if self.reference_now is not None else datetime.now(JST)
        calendars = fetch_icals(self.ical_urls)
        calendar = parse_icals(calendars, reference_now=reference_now, debug=self.debug)
        image = render_png(calendar)
        return png_to_image_content_request(image)


def png_to_image_content_request(image: PngImage) -> ImageContentRequest:
    """PngImage を Dot Image API 用リクエストに変換する。"""
    if image.content_type != "image/png":
        raise Quote0Error(f"PNG 変換失敗 reason=invalid_content_type:{image.content_type}")
    if image.width != 296 or image.height != 152:
        raise Quote0Error(f"PNG 変換失敗 reason=invalid_image_size:{image.width}x{image.height}")
    return ImageContentRequest(
        refreshNow=True,
        image=base64.b64encode(image.content).decode("ascii"),
        border=0,
        ditherType="NONE",
    )
