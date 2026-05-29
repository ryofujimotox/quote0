"""PNG 生成の仮実装。"""

from __future__ import annotations

from ..models import CalendarWindow, PngImage


DUMMY_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
    b"\xf6\x178U"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def render_png(calendar: CalendarWindow) -> PngImage:
    """今日・明日の枠を受け取り、固定 PNG を返す仮の描画。

    例: CalendarWindow(
            today=DaySchedule(2026-05-29, period=29日0時〜30日0時, events=()),
            tomorrow=DaySchedule(2026-05-30, …),
        )
        → PngImage(content=b"\\x89PNG\\r\\n…", width=1, height=1)
    """
    print(f"PNG 生成: {calendar.today.day.isoformat()} / {calendar.tomorrow.day.isoformat()}")
    return PngImage(content=DUMMY_PNG, width=1, height=1)
