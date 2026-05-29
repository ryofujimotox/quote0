"""iCal 取得・解析の仮実装。"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..models import CalendarWindow, DateRange, DaySchedule, FetchedIcal, JST


def today_in_jst() -> date:
    """バッチ開始時点の JST カレンダー日を返す。"""
    return datetime.now(JST).date()


def day_range(day: date) -> DateRange:
    """JST の 1 日を半開区間にする。

    例: day=2026-05-29 → [2026-05-29 0:00, 2026-05-30 0:00)（JST）
    """
    start = datetime.combine(day, datetime.min.time(), tzinfo=JST)
    return DateRange(start=start, end=start + timedelta(days=1))


def fetch_icals(urls: tuple[str, ...]) -> tuple[FetchedIcal, ...]:
    """URL 列挙順で取得結果を作る仮の iCal 取得。

    例: ("https://cal.example/a.ics", "https://cal.example/b.ics")
        → (FetchedIcal(0, "https://cal.example/a.ics", "BEGIN:VCALENDAR…"),
           FetchedIcal(1, "https://cal.example/b.ics", "BEGIN:VCALENDAR…"))
    """
    print(f"iCal 取得: {len(urls)}件")
    return tuple(
        FetchedIcal(
            source_index=index,
            url=url,
            text="BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n",
        )
        for index, url in enumerate(urls)
    )


def parse_icals(calendars: tuple[FetchedIcal, ...], today: date) -> CalendarWindow:
    """取得済み ICS から今日・明日枠を作る仮の解析（現状 events は空）。

    例: calendars=(FetchedIcal(0, "https://…", "BEGIN:VCALENDAR…"),), today=2026-05-29
        → CalendarWindow(
            today=DaySchedule(2026-05-29, period=29日0時〜30日0時, events=()),
            tomorrow=DaySchedule(2026-05-30, period=30日0時〜31日0時, events=()),
          )
    """
    print(f"iCal 解析: {len(calendars)}件")
    tomorrow = today + timedelta(days=1)
    return CalendarWindow(
        today=DaySchedule(day=today, period=day_range(today), events=()),
        tomorrow=DaySchedule(day=tomorrow, period=day_range(tomorrow), events=()),
    )
