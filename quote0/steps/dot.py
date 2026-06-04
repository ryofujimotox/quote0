"""Dot Image API 送信。"""

from __future__ import annotations

import json

from quote0_client import Quote0Client
from quote0_client.exceptions import Quote0Error
from quote0_client.models import APIResponse

from ..config import AppConfig
from ..content.ical_image import png_to_image_content_request
from ..models import DotSendResult, PngImage


def send_dot_image(config: AppConfig, image: PngImage) -> DotSendResult:
    """PNGをDot Image APIへ送信し、成功応答だけを返す。"""
    print(f"Dot 送信: device_id={config.dot_device_id}, bytes={len(image.content)}")
    request = png_to_image_content_request(image)
    client = Quote0Client(api_key=config.dot_api_token)
    try:
        response = client.send_image(config.dot_device_id, request)
        return _to_dot_send_result(response)
    except Quote0Error as exc:
        raise Quote0Error(f"Dot 送信失敗 reason={exc}") from exc
    finally:
        client.close()


def _to_dot_send_result(response: APIResponse) -> DotSendResult:
    response_text = json.dumps(response.model_dump(exclude_none=True), separators=(",", ":"))
    status_code = int(response.code) if str(response.code).isdigit() else 200
    if not response.success:
        raise Quote0Error(f"Dot 送信失敗 code={response.code} body={response_text}")
    return DotSendResult(status_code=status_code, response_text=response_text)
