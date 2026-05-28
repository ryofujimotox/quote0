"""環境変数から設定を読み込む。"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

from .errors import HandyCalendarError


class ConfigError(HandyCalendarError, ValueError):
    """設定不備を表す例外。"""


@dataclass(frozen=True)
class AppConfig:
    """アプリ全体で使う設定値。"""

    ical_urls: tuple[str, ...]
    dot_api_token: str
    dot_device_id: str


def load_config(env_file: str | Path | None = None) -> AppConfig:
    """`.env` を読み込み、必須環境変数を検証した設定を返す。"""
    load_dotenv(dotenv_path=env_file)

    ical_urls_raw = os.getenv("ICAL_URLS", "")
    dot_api_token = os.getenv("DOT_API_TOKEN", "").strip()
    dot_device_id = os.getenv("DOT_DEVICE_ID", "").strip()

    ical_urls = tuple(url.strip() for url in ical_urls_raw.split(",") if url.strip())
    if not ical_urls:
        raise ConfigError("環境変数 ICAL_URLS が未設定です。1 件以上の URL を指定してください。")
    if not dot_api_token:
        raise ConfigError("環境変数 DOT_API_TOKEN が未設定です。")
    if not dot_device_id:
        raise ConfigError("環境変数 DOT_DEVICE_ID が未設定です。")

    return AppConfig(
        ical_urls=ical_urls,
        dot_api_token=dot_api_token,
        dot_device_id=dot_device_id,
    )
