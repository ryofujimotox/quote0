"""PNG 生成。

描画の流れ（上から）:
  今日（5/29金）
    予定名（10:00~10:30）  … 1行 = 予定 + 括弧付き時刻
  ── 区切り線
  明日（5/30土）
    …

予定行の省略優先度: 開始時刻 → 予定名 → 終了時刻
下端ははみ出してよい（明日の予定が一部見切れても可）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from ..models import CalendarEvent, CalendarWindow, DaySchedule, PngImage

Section = Literal["today", "tomorrow"]


@dataclass(frozen=True)
class DisplayEvent:
    """1 行で描く予定。時刻 suffix は幅省略前のフル表示。"""

    event: CalendarEvent
    time_suffix: str | None


@dataclass(frozen=True)
class DisplayDay:
    """上から順に描く 1 日分。"""

    day: date
    header: str
    section: Section
    events: tuple[DisplayEvent, ...]


# Dot 表示領域（デバイス要件に合わせて固定）
WIDTH = 296
HEIGHT = 152
MARGIN = 6
LINE_GAP = 2
EVENT_INDENT = 6
DIVIDER_TOP_PAD = 4
DIVIDER_BOTTOM_PAD = 4

# サイズは揃え、今日ブロックだけ太字（明日は通常ウェイト）
DATE_FONT_SIZE = 20
TIME_FONT_SIZE = 20
TITLE_FONT_SIZE = 20

BACKGROUND = (250, 250, 247)
INK = (30, 34, 40)
ACCENT = (39, 98, 166)
DIVIDER = (90, 96, 108)
DIVIDER_WIDTH = 2

# macOS / Linux で見つかりやすい順（先頭が使われる）。太字が無い環境は通常ウェイトへフォールバック
BOLD_FONT_PATHS = (
    Path("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"),
    Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
)
REGULAR_FONT_PATHS = (
    Path("/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc"),
    Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)


# --- 描画行（上からこの順で並べる） ---


@dataclass(frozen=True)
class DateHeaderLine:
    """例: 今日（5/29金）"""

    header: str
    section: Section


@dataclass(frozen=True)
class EventLine:
    """例: 打合せ（10:00~11:00）の元データ"""

    display_event: DisplayEvent
    section: Section


@dataclass(frozen=True)
class DayDividerLine:
    """今日ブロックと明日ブロックの間の横線"""


@dataclass(frozen=True)
class EventFonts:
    time: ImageFont.ImageFont
    title: ImageFont.ImageFont


@dataclass(frozen=True)
class DayFonts:
    date: ImageFont.ImageFont
    events: EventFonts


@dataclass(frozen=True)
class RenderFonts:
    today: DayFonts
    tomorrow: DayFonts


RenderLine = DateHeaderLine | EventLine | DayDividerLine


def build_display_days(calendar: CalendarWindow) -> tuple[DisplayDay, ...]:
    """CalendarWindow を上から描く日ブロック列に変換する。

    例: CalendarWindow(today=…, tomorrow=…)
        → (
            DisplayDay(day=2026-05-29, header="今日（5/29金）", section="today", events=(…,)),
            DisplayDay(day=2026-05-30, header="明日（5/30土）", section="tomorrow", events=(…,)),
          )
    """
    return (
        _display_day_from_schedule(calendar.today, "today"),
        _display_day_from_schedule(calendar.tomorrow, "tomorrow"),
    )


def _display_day_from_schedule(schedule: DaySchedule, section: Section) -> DisplayDay:
    return DisplayDay(
        day=schedule.day,
        header=_format_date_header(schedule.day, section),
        section=section,
        events=tuple(_display_event_from_calendar(event) for event in schedule.events),
    )


def _display_event_from_calendar(event: CalendarEvent) -> DisplayEvent:
    if event.all_day:
        return DisplayEvent(event=event, time_suffix=None)
    start_text, end_text = _event_time_parts(event)
    return DisplayEvent(
        event=event,
        time_suffix=_time_suffix_text(start_text, end_text, with_end=True),
    )


def render_png(calendar: CalendarWindow) -> PngImage:
    """CalendarWindow から PNG バイト列を作る。"""
    display_days = build_display_days(calendar)
    print(
        "PNG 生成: "
        f"{display_days[0].day.isoformat()} / {display_days[1].day.isoformat()}"
    )
    lines = _build_lines(display_days)
    regular_path = _find_font_path(_regular_font_candidates())
    bold_path = _find_font_path(_bold_font_candidates())
    fonts = _load_fonts(regular_path, bold_path)
    event_left = MARGIN + EVENT_INDENT
    event_width = WIDTH - MARGIN - event_left
    y_limit = HEIGHT - MARGIN

    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    y = MARGIN
    for line in lines:
        # 高さ超過後も描くと下端が切れるので、次行を描く前に打ち切る
        if y >= y_limit:
            break
        line_height = _line_height_for(line, fonts)
        if isinstance(line, DayDividerLine):
            _draw_day_divider(draw, y)
        elif isinstance(line, DateHeaderLine):
            day_fonts = _fonts_for_section(fonts, line.section)
            draw.text(
                (MARGIN, y),
                line.header,
                fill=ACCENT,
                font=day_fonts.date,
            )
        else:
            day_fonts = _fonts_for_section(fonts, line.section)
            _draw_event_line(draw, y, line.display_event, day_fonts.events, event_left, event_width)
        y += line_height

    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    return PngImage(content=output.getvalue(), width=WIDTH, height=HEIGHT)


def _build_lines(display_days: tuple[DisplayDay, ...]) -> list[RenderLine]:
    """日ブロック列 → 区切り線付きの描画行リスト。"""
    lines: list[RenderLine] = []
    for index, display_day in enumerate(display_days):
        lines.append(DateHeaderLine(display_day.header, display_day.section))
        for display_event in display_day.events:
            lines.append(EventLine(display_event, display_day.section))
        if index < len(display_days) - 1:
            lines.append(DayDividerLine())
    return lines


def _format_date_header(day: date, section: Section) -> str:
    weekdays = ("月", "火", "水", "木", "金", "土", "日")
    date_text = f"{day.month}/{day.day}{weekdays[day.weekday()]}"
    label = "今日" if section == "today" else "明日"
    return f"{label}（{date_text}）"


# --- 予定行: 「予定名」+「（時刻）」を横並び ---


def _event_time_parts(event: CalendarEvent) -> tuple[str, str | None]:
    """表示用の開始・終了時刻文字列。区間が無いとき end は None。"""
    start_text = event.period.start.strftime("%H:%M")
    if not _show_end_time(event.period.start, event.period.end):
        return start_text, None
    return start_text, event.period.end.strftime("%H:%M")


def _time_suffix_text(start_text: str, end_text: str | None, *, with_end: bool) -> str:
    """括弧付き時刻。with_end=False なら開始+`~` まで（終了は後から足す）。"""
    if end_text is None:
        return f"（{start_text}）"
    if with_end:
        return f"（{start_text}~{end_text}）"
    return f"（{start_text}~"


def _show_end_time(start: datetime, end: datetime) -> bool:
    """同日で終了時刻が開始と異なるときだけ `~終了` を付ける。"""
    if end <= start:
        return False
    if end.date() != start.date():
        return False
    return end.strftime("%H:%M") != start.strftime("%H:%M")


def _draw_event_line(
    draw: ImageDraw.ImageDraw,
    y: int,
    display_event: DisplayEvent,
    fonts: EventFonts,
    event_left: int,
    event_width: int,
) -> None:
    event = display_event.event
    # 終日は時刻なし・左詰め
    if event.all_day:
        title = _truncate_to_width(event.title, fonts.title, event_width)
        if title:
            draw.text((event_left, y), title, fill=INK, font=fonts.title)
        return
    title, time_suffix = _fit_title_and_time(event, fonts, event_width)
    draw.text((event_left, y), title, fill=INK, font=fonts.title)
    if time_suffix:
        draw.text((event_left + _text_width(title, fonts.title), y), time_suffix, fill=INK, font=fonts.time)


def _fit_title_and_time(
    event: CalendarEvent,
    fonts: EventFonts,
    event_width: int,
) -> tuple[str, str]:
    """1行に収める予定名と時刻 suffix を決める。

    優先度: 開始時刻 → 予定名 → 終了時刻。
    例: 幅が足りない → `長い予定…（10:00~`（閉じ括弧なし）
    """
    start_text, end_text = _event_time_parts(event)
    full_suffix = _time_suffix_text(start_text, end_text, with_end=True)
    if _text_width(event.title, fonts.title) + _text_width(full_suffix, fonts.time) <= event_width:
        return event.title, full_suffix

    # `（10:00~` 分だけ先に確保してから予定名を最大にし、残り幅で終了時刻を試す
    min_suffix = _time_suffix_text(start_text, end_text, with_end=False)
    allowed_title_width = max(0, event_width - _text_width(min_suffix, fonts.time))
    title = _truncate_to_width(event.title, fonts.title, allowed_title_width)
    remaining = max(0, event_width - _text_width(title, fonts.title))
    suffix = _build_time_suffix(start_text, end_text, fonts.time, remaining)
    return title, suffix


def _build_time_suffix(
    start_text: str,
    end_text: str | None,
    font: ImageFont.ImageFont,
    max_width: int,
) -> str:
    """予定名の右に付ける時刻部分。max_width は予定名描画後の残り幅。"""
    if max_width <= 0:
        return ""
    if end_text is None:
        closed = _time_suffix_text(start_text, None, with_end=False)
        if _text_width(closed, font) <= max_width:
            return closed
        return _truncate_to_width(f"（{start_text}", font, max_width)

    full = _time_suffix_text(start_text, end_text, with_end=True)
    if _text_width(full, font) <= max_width:
        return full

    # 終了時刻を少しずつ足せるか試す
    base = _time_suffix_text(start_text, end_text, with_end=False)
    base_width = _text_width(base, font)
    closing_width = _text_width("）", font)
    end_room = max_width - base_width - closing_width
    if end_room > 0:
        end_part = _truncate_to_width(end_text, font, end_room)
        if end_part and end_part != "…":
            with_end = f"{base}{end_part}）"
            if _text_width(with_end, font) <= max_width:
                return with_end

    # 終了が入らないときは `（10:00~` で終える（閉じ括弧なし）
    if base_width <= max_width:
        return base

    return _truncate_to_width(f"（{start_text}", font, max_width)


def _draw_day_divider(draw: ImageDraw.ImageDraw, y: int) -> None:
    line_y = y + DIVIDER_TOP_PAD
    draw.line((MARGIN, line_y, WIDTH - MARGIN, line_y), fill=DIVIDER, width=DIVIDER_WIDTH)


# --- フォント・計測 ---


def _fonts_for_section(fonts: RenderFonts, section: Section) -> DayFonts:
    return fonts.tomorrow if section == "tomorrow" else fonts.today


def _load_fonts(regular_path: Path | None, bold_path: Path | None) -> RenderFonts:
    if regular_path is None:
        default = ImageFont.load_default()
        events = EventFonts(time=default, title=default)
        day = DayFonts(date=default, events=events)
        return RenderFonts(today=day, tomorrow=day)

    def _day_fonts(path: str) -> DayFonts:
        return DayFonts(
            date=ImageFont.truetype(path, DATE_FONT_SIZE),
            events=EventFonts(
                time=ImageFont.truetype(path, TIME_FONT_SIZE),
                title=ImageFont.truetype(path, TITLE_FONT_SIZE),
            ),
        )

    regular = str(regular_path)
    bold = str(bold_path or regular_path)
    return RenderFonts(today=_day_fonts(bold), tomorrow=_day_fonts(regular))


def _find_font_path(candidates: tuple[Path, ...]) -> Path | None:
    return next((path for path in candidates if path.exists()), None)


def _regular_font_candidates() -> tuple[Path, ...]:
    hiragino = tuple(sorted(Path("/System/Library/Fonts").glob("ヒラ*角*W4.ttc")))
    return (*hiragino, *REGULAR_FONT_PATHS)


def _bold_font_candidates() -> tuple[Path, ...]:
    hiragino = tuple(sorted(Path("/System/Library/Fonts").glob("ヒラ*角*W6.ttc")))
    return (*hiragino, *BOLD_FONT_PATHS)


def _divider_height() -> int:
    return DIVIDER_TOP_PAD + DIVIDER_WIDTH + DIVIDER_BOTTOM_PAD


def _line_height_for(line: RenderLine, fonts: RenderFonts) -> int:
    if isinstance(line, DayDividerLine):
        return _divider_height()
    day_fonts = _fonts_for_section(fonts, line.section)
    if isinstance(line, DateHeaderLine):
        return _line_height(day_fonts.date)
    # 予定行は title / time の大きい方に合わせる
    return max(_line_height(day_fonts.events.time), _line_height(day_fonts.events.title))


def _line_height(font: ImageFont.ImageFont) -> int:
    ascent, descent = font.getmetrics()
    return ascent + descent + LINE_GAP


def _text_width(text: str, font: ImageFont.ImageFont) -> int:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def _truncate_to_width(text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if max_width <= 0:
        return ""
    if _text_width(text, font) <= max_width:
        return text
    ellipsis = "…"
    if _text_width(ellipsis, font) > max_width:
        return ""
    trimmed = text
    while trimmed and _text_width(trimmed + ellipsis, font) > max_width:
        trimmed = trimmed[:-1]
    return trimmed + ellipsis if trimmed else ellipsis
