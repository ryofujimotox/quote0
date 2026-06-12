"""iCal から PNG を生成し Dot 画像リクエストに変換する拡張。"""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar

from quote0.vendor.quote0_client.exceptions import Quote0Error
from quote0.vendor.quote0_client.models import ImageContentRequest

from .ical import fetch_icals, parse_icals
from .ical_models import JST, PngImage
from .render import render_png


T = TypeVar("T")


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
    debug_logs: bool = False

    def to_image_content_request(self) -> ImageContentRequest:
        reference_now = self.reference_now if self.reference_now is not None else datetime.now(JST)

        calendars = _run_stage(
            "iCal取得",
            lambda: fetch_icals(self.ical_urls, debug_logs=self.debug_logs),
            lambda result: f"{len(result)}件",
        )
        calendar = _run_stage(
            "解析",
            lambda: parse_icals(calendars, reference_now=reference_now, debug_logs=self.debug_logs),
            lambda result: (
                f"first_day={len(result.first_day.events)}件, "
                f"next_day={result.next_day.date.isoformat()}({len(result.next_day.events)}件)"
            ),
        )
        image = _run_stage(
            "PNG生成",
            lambda: render_png(calendar, debug_logs=self.debug_logs),
            lambda result: f"{result.width}x{result.height}, bytes={len(result.content)}",
        )
        return png_to_image_content_request(image)


def _run_stage(stage: str, action: Callable[[], T], summary: Callable[[T], str]) -> T:
    """段階ごとの開始・成功・失敗を同じ形式で残す。"""
    print(f"{stage}開始", flush=True)
    try:
        result = action()
    except Exception as exc:
        raise Quote0Error(f"{stage}失敗: {exc}") from exc
    print(f"{stage}成功: {summary(result)}", flush=True)
    return result


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
