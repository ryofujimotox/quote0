"""予定処理で受け渡す最小データ構造。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class DateRange:
    """JST の半開区間。"""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("DateRange はタイムゾーン付き datetime を指定してください。")
        if self.start >= self.end:
            raise ValueError("DateRange は start < end で指定してください。")

    def overlaps(self, other: "DateRange") -> bool:
        """2 つの半開区間が重なるかを返す。"""
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class CalendarEvent:
    """PNG 表示対象になる予定。"""

    uid: str
    title: str
    period: DateRange
    source_index: int
    source_url: str
    all_day: bool = False


@dataclass(frozen=True)
class FetchedIcal:
    """取得済み ICS。"""

    source_index: int
    url: str
    text: str


@dataclass(frozen=True)
class DaySchedule:
    """1 日分の表示データ。"""

    day: date
    period: DateRange
    events: tuple[CalendarEvent, ...]


@dataclass(frozen=True)
class CalendarWindow:
    """今日・明日の表示データ。"""

    today: DaySchedule
    tomorrow: DaySchedule


@dataclass(frozen=True)
class PngImage:
    """Dot へ送る PNG。"""

    content: bytes
    width: int
    height: int
    content_type: str = "image/png"


@dataclass(frozen=True)
class DotSendResult:
    """Dot Image API 送信結果。"""

    status_code: int
    response_text: str
