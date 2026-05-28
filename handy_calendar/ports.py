"""処理境界の型定義。"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from .config import AppConfig
from .models import CalendarWindow, DotSendResult, FetchedIcal, PngImage


class IcalFetcher(Protocol):
    """公開 iCal URL を全件取得する境界。"""

    def __call__(self, urls: tuple[str, ...]) -> tuple[FetchedIcal, ...]:
        """URL 列挙順で取得し、1 件でも失敗したら例外を送出する。"""


class IcalParser(Protocol):
    """取得済み ICS から今日・明日の予定を抽出する境界。"""

    def __call__(self, calendars: tuple[FetchedIcal, ...], base_day: date) -> CalendarWindow:
        """JST の今日・明日の半開区間に重なる予定だけを返す。"""


class PngRenderer(Protocol):
    """表示用 PNG を生成する境界。"""

    def __call__(self, calendar: CalendarWindow) -> PngImage:
        """同じ入力なら同じ PNG バイト列を返す。"""


class DotImageSender(Protocol):
    """Dot Image API へ PNG を送信する境界。"""

    def __call__(self, config: AppConfig, image: PngImage) -> DotSendResult:
        """Dot Image API の成功応答以外は例外を送出する。"""
