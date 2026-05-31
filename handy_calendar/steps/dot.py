"""Dot Image API 送信。"""

from __future__ import annotations

import base64
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import AppConfig
from ..errors import HandyCalendarError
from ..models import DotSendResult, PngImage


API_BASE_URL = "https://dot.mindreset.tech"
SEND_TIMEOUT_SECONDS = 20


def send_dot_image(config: AppConfig, image: PngImage) -> DotSendResult:
    """PNGをDot Image APIへ送信し、成功応答だけを返す。"""
    _validate_image(image)
    print(f"Dot 送信: device_id={config.dot_device_id}, bytes={len(image.content)}")
    body = json.dumps(_request_body(image), separators=(",", ":")).encode("utf-8")
    request = Request(
        f"{API_BASE_URL}/api/authV2/open/device/{config.dot_device_id}/image",
        data=body,
        headers={
            "Authorization": f"Bearer {config.dot_api_token}",
            "Content-Type": "application/json",
            "User-Agent": "handy-calendar/0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=SEND_TIMEOUT_SECONDS) as response:
            response_text = response.read().decode("utf-8")
            status = getattr(response, "status", 200)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HandyCalendarError(f"Dot 送信失敗 status={exc.code} body={detail}") from exc
    except URLError as exc:
        raise HandyCalendarError(f"Dot 送信失敗 reason={exc.reason}") from exc
    except TimeoutError as exc:
        raise HandyCalendarError("Dot 送信失敗 reason=timeout") from exc

    result = _parse_response(status, response_text)
    if result.status_code != 200:
        raise HandyCalendarError(f"Dot 送信失敗 code={result.status_code} body={response_text}")
    return result


def _validate_image(image: PngImage) -> None:
    if image.content_type != "image/png":
        raise HandyCalendarError(f"Dot 送信失敗 reason=invalid_content_type:{image.content_type}")
    if image.width != 296 or image.height != 152:
        raise HandyCalendarError(f"Dot 送信失敗 reason=invalid_image_size:{image.width}x{image.height}")


def _request_body(image: PngImage) -> dict[str, object]:
    return {
        "refreshNow": True,
        "image": base64.b64encode(image.content).decode("ascii"),
        "border": 0,
        "ditherType": "NONE",
    }


def _parse_response(http_status: int, response_text: str) -> DotSendResult:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise HandyCalendarError(f"Dot 送信失敗 status={http_status} reason=invalid_json") from exc
    return DotSendResult(status_code=int(payload.get("code", http_status)), response_text=response_text)
