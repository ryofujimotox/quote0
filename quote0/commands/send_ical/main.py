"""iCal 予定を PNG にして Dot へ送る CLI の本体。"""

from __future__ import annotations

from datetime import datetime

from quote0.config import ConfigError, load_config
from quote0.content.ical_image import CustomIcalImageContentRequest
from quote0.content.ical_image.ical_models import JST
from quote0.content.jp_quote0_client import JpQuote0Client as Quote0Client
from quote0.pipeline_log import log_error, log_info, log_stage_start, log_stage_success
from quote0.vendor.quote0_client.exceptions import Quote0Error


def _batch_start_now() -> datetime:
    """バッチ開始時点の JST 日時。テストでは差し替え可能。"""
    return datetime.now(JST)


def main() -> int:
    """設定読込後、iCal 画像リクエストを組み立てて Dot へ送信する。"""
    client = None
    try:
        # 設定を読み込む
        config = load_config()
        ical_urls = config.ical_urls
        dot_api_token = config.dot_api_token
        dot_device_id = config.dot_device_id

        # iCal 画像リクエストを組み立てる
        reference_now = _batch_start_now()
        content = CustomIcalImageContentRequest(
            ical_urls=ical_urls,
            reference_now=reference_now,
            debug=config.debug,
        ).to_image_content_request()

        log_stage_start("Dot 送信", detail=f"device_id={dot_device_id}, bytes={len(content.image)}")
        client = Quote0Client(api_key=dot_api_token)
        client.send_image(dot_device_id, content)
        log_stage_success("Dot 送信", detail=f"device_id={dot_device_id}")
    except ConfigError as exc:
        log_error(f"設定失敗: {exc}")
        return 1
    except Quote0Error as exc:
        log_error(str(exc))
        return 1
    except Exception as exc:
        log_error(f"想定外のエラー: {exc}")
        return 1
    finally:
        if client is not None:
            client.close()

    log_info(
        "バッチ完了: iCal取得→解析→PNG→Dot送信 "
        f"(ical_urls={len(ical_urls)}件, device_id={dot_device_id})",
    )
    return 0
