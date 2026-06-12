"""予定処理で受け渡す最小データ構造。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class DateRange:
    """JST の半開区間 [start, end)。

    例: start=01/01 0:00, end=01/05 0:00 なら 01/01〜01/04 は含むが 01/05 は含まない。
    今日・次の予定日の日枠と予定の期間を同じルールで表す。
    """

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("DateRange はタイムゾーン付き datetime を指定してください。")
        if self.start >= self.end:
            raise ValueError("DateRange は start < end で指定してください。")

    def overlaps(self, other: "DateRange") -> bool:
        """予定が日枠にかかっているかを判定する。

        典型: day_schedule.period.overlaps(event.period)

        例: self=[29日0時, 30日0時), other=[29日10時, 29日11時) → True
            self=[29日0時, 30日0時), other=[30日10時, 30日11時) → False
        """
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class CalendarEvent:
    """PNG 表示対象になる予定。

    例: CalendarEvent(
            uid="evt-1", title="打合せ",
            period=[29日10時, 29日11時), source_index=0,
            source_url="https://cal.example/a.ics",
        )
    """

    uid: str
    title: str
    period: DateRange
    source_index: int  # ICAL_URLS の列挙順（0 始まり）。並びの第 1 キー。
    source_url: str
    all_day: bool = False


@dataclass(frozen=True)
class FetchedIcal:
    """取得済み ICS。

    例: FetchedIcal(0, "https://cal.example/a.ics", "BEGIN:VCALENDAR\\n…")
    """

    source_index: int
    url: str
    text: str


@dataclass(frozen=True)
class DaySchedule:
    """1 日分の表示データ。

    例: DaySchedule(
            date=2026-05-29,
            period=[29日0時, 30日0時),
            events=(CalendarEvent(…),),
        )
    """

    date: date
    period: DateRange  # その日 0:00 以上 翌日 0:00 未満（JST）の枠
    events: tuple[CalendarEvent, ...]


@dataclass(frozen=True)
class CalendarWindow:
    """今日・次の予定日の表示データ。

    例: CalendarWindow(first_day=DaySchedule(2026-05-29, …), next_day=DaySchedule(2026-05-31, …))
    """

    first_day: DaySchedule
    next_day: DaySchedule


@dataclass(frozen=True)
class PngImage:
    """Dot へ送る PNG。

    例: PngImage(content=b"\\x89PNG\\r\\n…", width=800, height=480)
    """

    content: bytes
    width: int
    height: int
    content_type: str = "image/png"
