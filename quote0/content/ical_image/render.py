"""PNG 生成。

描画の流れ（上から）:
  今日（5/29金）
    予定名（10:00~10:30）  … 1行 = 予定 + 括弧付き時刻
  ── 区切り線
  3日後（6/2月）
    …

予定行の省略優先度: 開始時刻 → 予定名 → 終了時刻
前日開始の持ち越しは `（~終了）` のみ（開始時刻は出さない）
2 枠目も描画行に含め、上から順に描く。下端はみ出して見切れてもよい。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from quote0.vendor.quote0_client.exceptions import Quote0Error
from .ical_models import CalendarEvent, CalendarWindow, DaySchedule, JST, PngImage


@dataclass(frozen=True)
class DisplayEvent:
    """1 行で描く予定。時刻 suffix は幅省略前のフル表示。"""

    event: CalendarEvent
    time_suffix: str | None


@dataclass(frozen=True)
class DisplayDay:
    """上から順に描く 1 日分。"""

    date: date
    header: str
    events: tuple[DisplayEvent, ...]


# --- 描画サイズ ---
# 調整は *_PT を変える。Pillow 描画は RENDER_DPI で px に換算する。
# キャンバスだけ Dot デバイス要件の px 固定。

RENDER_DPI = 96.0


def _px(pt: float) -> int:
    """pt → Pillow 描画用 px（四捨五入）。"""
    return round(pt * RENDER_DPI / 72.0)


# キャンバス（px 固定）
CANVAS_WIDTH = 296
CANVAS_HEIGHT = 152

# 余白・行間（pt）
EVENT_INDENT_PT = 4.5  # 予定行の左インデント（日付見出しより右）
DIVIDER_PAD_PT = 1.5  # 区切り線の上下余白
DIVIDER_WIDTH_PT = 1.5  # 区切り線の太さ

# フォント（pt）。太字/通常は字体ファイル（Regular / Bold）で切り替え
DATE_FONT_PT = 15.0
TIME_FONT_PT = 15.0
TITLE_FONT_PT = 15.0

# px 換算（描画コードはこちらを参照）
WIDTH = CANVAS_WIDTH
HEIGHT = CANVAS_HEIGHT
EVENT_INDENT = _px(EVENT_INDENT_PT)
DIVIDER_PAD = _px(DIVIDER_PAD_PT)
DIVIDER_WIDTH = _px(DIVIDER_WIDTH_PT)
DATE_FONT_SIZE = _px(DATE_FONT_PT)
TIME_FONT_SIZE = _px(TIME_FONT_PT)
TITLE_FONT_SIZE = _px(TITLE_FONT_PT)
# 予定行の描画幅 = キャンバス幅 − 左インデント
EVENT_LINE_WIDTH = WIDTH - EVENT_INDENT

BACKGROUND = (250, 250, 247)
INK = (30, 34, 40)
ACCENT = (39, 98, 166)
DIVIDER = (90, 96, 108)

# 環境差を避けるため、同梱の Noto Sans JP のみ使う（ical_image/fonts/）
_FONTS_DIR = Path(__file__).resolve().parent / "fonts"
REGULAR_FONT_PATH = _FONTS_DIR / "NotoSansJP-Regular.otf"
BOLD_FONT_PATH = _FONTS_DIR / "NotoSansJP-Bold.otf"


# --- 描画行（上からこの順で並べる） ---


@dataclass(frozen=True)
class DateHeaderLine:
    """例: 今日（5/29金）"""

    header: str
    emphasized: bool


@dataclass(frozen=True)
class EventLine:
    """例: 打合せ（10:00~11:00）の元データ"""

    display_event: DisplayEvent
    emphasized: bool


@dataclass(frozen=True)
class DayDividerLine:
    """1 枠目と 2 枠目の間の横線"""


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
    emphasis: DayFonts
    regular: DayFonts


RenderLine = DateHeaderLine | EventLine | DayDividerLine


def build_display_days(calendar: CalendarWindow) -> tuple[DisplayDay, ...]:
    """CalendarWindow を上から描く日ブロック列に変換する。

    例: CalendarWindow(first_day=…, next_day=…)
        → (
            DisplayDay(date=2026-05-29, header="今日（5/29金）", events=(…,)),
            DisplayDay(date=2026-06-02, header="3日後（6/2月）", events=(…,)),
          )
    """
    first_date = calendar.first_day.date
    return (
        _display_day_from_schedule(calendar.first_day, first_date),
        _display_day_from_schedule(calendar.next_day, first_date),
    )


def _display_day_from_schedule(schedule: DaySchedule, first_date: date) -> DisplayDay:
    return DisplayDay(
        date=schedule.date,
        header=_format_date_header(schedule.date, first_date),
        events=tuple(_display_event_from_calendar(event, schedule.date) for event in schedule.events),
    )


def _display_event_from_calendar(event: CalendarEvent, display_date: date) -> DisplayEvent:
    if event.all_day:
        return DisplayEvent(event=event, time_suffix=None)
    if _is_carry_over_on_day(event, display_date):
        return DisplayEvent(event=event, time_suffix=_carry_over_time_suffix(event))
    start_text, end_text = _event_time_parts(event)
    return DisplayEvent(
        event=event,
        time_suffix=_time_suffix_text(start_text, end_text, with_end=True),
    )


def render_png(calendar: CalendarWindow, *, debug_logs: bool = False) -> PngImage:
    """CalendarWindow から PNG バイト列を作る。"""
    display_days = build_display_days(calendar)
    if debug_logs:
        print(
            "PNG 生成詳細: "
            f"{display_days[0].date.isoformat()} / {display_days[1].date.isoformat()}",
            flush=True,
        )
    regular_path, bold_path = _resolve_font_paths()
    fonts = _load_fonts(regular_path, bold_path)
    lines = _build_lines(display_days)
    event_left = EVENT_INDENT
    event_width = EVENT_LINE_WIDTH
    y_limit = HEIGHT

    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    y = 0
    for line in lines:
        # 高さ超過後も描くと下端が切れるので、次行を描く前に打ち切る
        if y >= y_limit:
            break
        line_height = _line_height_for(line, fonts)
        if isinstance(line, DayDividerLine):
            _draw_day_divider(draw, y)
        elif isinstance(line, DateHeaderLine):
            day_fonts = _fonts_for_emphasis(fonts, line.emphasized)
            draw.text(
                (0, y),
                line.header,
                fill=ACCENT,
                font=day_fonts.date,
            )
        else:
            day_fonts = _fonts_for_emphasis(fonts, line.emphasized)
            _draw_event_line(draw, y, line.display_event, day_fonts.events, event_left, event_width)
        y += line_height

    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    return PngImage(content=output.getvalue(), width=WIDTH, height=HEIGHT)


def _build_lines(display_days: tuple[DisplayDay, ...]) -> list[RenderLine]:
    """日ブロック列 → 区切り線付きの描画行リスト。"""
    lines: list[RenderLine] = []
    for index, display_day in enumerate(display_days):
        emphasized = index == 0
        lines.append(DateHeaderLine(display_day.header, emphasized))
        for display_event in display_day.events:
            lines.append(EventLine(display_event, emphasized))
        if index < len(display_days) - 1:
            lines.append(DayDividerLine())
    return lines


def _format_date_header(day: date, first_date: date) -> str:
    weekdays = ("月", "火", "水", "木", "金", "土", "日")
    date_text = f"{day.month}/{day.day}{weekdays[day.weekday()]}"
    if day == first_date:
        return f"今日（{date_text}）"
    delta_days = (day - first_date).days
    if delta_days == 1:
        return f"明日（{date_text}）"
    return f"{delta_days}日後（{date_text}）"


# --- 予定行: 「予定名」+「（時刻）」を横並び ---


def _event_start_date(event: CalendarEvent) -> date:
    return event.period.start.astimezone(JST).date()


def _is_carry_over_on_day(event: CalendarEvent, display_date: date) -> bool:
    """表示日より前に開始した timed 予定（今日枠の持ち越し）。"""
    return not event.all_day and _event_start_date(event) < display_date


def _carry_over_time_suffix(event: CalendarEvent) -> str:
    """持ち越し行は終了時刻だけ `（~HH:MM）`。"""
    end_text = event.period.end.astimezone(JST).strftime("%H:%M")
    return f"（~{end_text}）"


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
    """終了時刻を付けるか。同日差分があるとき、または翌日にまたがるとき True。"""
    if end <= start:
        return False
    if end.date() != start.date():
        return True
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
    title, time_suffix = _fit_title_and_time(event, fonts, event_width, time_suffix=display_event.time_suffix)
    draw.text((event_left, y), title, fill=INK, font=fonts.title)
    if time_suffix:
        draw.text((event_left + _text_width(title, fonts.title), y), time_suffix, fill=INK, font=fonts.time)


def _fit_title_and_time(
    event: CalendarEvent,
    fonts: EventFonts,
    event_width: int,
    *,
    time_suffix: str | None,
) -> tuple[str, str]:
    """1行に収める予定名と時刻 suffix を決める。

    time_suffix は build_display_days と同じルールで渡す（持ち越しは `（~HH:MM）`）。
    優先度: 開始時刻 → 予定名 → 終了時刻。
    例: 幅が足りない → `長い予定…（10:00~`（閉じ括弧なし）
    """
    if time_suffix is None:
        return event.title, ""
    if time_suffix.startswith("（~"):
        return _fit_title_and_carry_over_time(event, fonts, event_width, time_suffix)

    start_text, end_text = _event_time_parts(event)
    full_suffix = time_suffix
    if _text_width(event.title, fonts.title) + _text_width(full_suffix, fonts.time) <= event_width:
        return event.title, full_suffix

    # `（10:00~` 分だけ先に確保してから予定名を最大にし、残り幅で終了時刻を試す
    min_suffix = _time_suffix_text(start_text, end_text, with_end=False)
    allowed_title_width = max(0, event_width - _text_width(min_suffix, fonts.time))
    title = _truncate_to_width(event.title, fonts.title, allowed_title_width)
    remaining = max(0, event_width - _text_width(title, fonts.title))
    suffix = _build_time_suffix(start_text, end_text, fonts.time, remaining)
    return title, suffix


def _fit_title_and_carry_over_time(
    event: CalendarEvent,
    fonts: EventFonts,
    event_width: int,
    full_suffix: str,
) -> tuple[str, str]:
    """持ち越し行: 予定名 + `（~終了）` を幅に収める。"""
    if _text_width(event.title, fonts.title) + _text_width(full_suffix, fonts.time) <= event_width:
        return event.title, full_suffix

    min_suffix = "（~"
    allowed_title_width = max(0, event_width - _text_width(min_suffix, fonts.time))
    title = _truncate_to_width(event.title, fonts.title, allowed_title_width)
    remaining = max(0, event_width - _text_width(title, fonts.title))
    suffix = _build_carry_over_time_suffix(full_suffix, fonts.time, remaining)
    return title, suffix


def _build_carry_over_time_suffix(full_suffix: str, font: ImageFont.ImageFont, max_width: int) -> str:
    """持ち越しの `（~HH:MM）` を残り幅に収める。"""
    if max_width <= 0 or not full_suffix.startswith("（~") or not full_suffix.endswith("）"):
        return ""
    if _text_width(full_suffix, font) <= max_width:
        return full_suffix

    end_text = full_suffix[2:-1]
    base = "（~"
    closing_width = _text_width("）", font)
    end_room = max_width - _text_width(base, font) - closing_width
    if end_room > 0:
        end_part = _truncate_to_width(end_text, font, end_room)
        if end_part and end_part != "…":
            with_end = f"{base}{end_part}）"
            if _text_width(with_end, font) <= max_width:
                return with_end

    if _text_width(base, font) <= max_width:
        return base
    return _truncate_to_width(base, font, max_width)


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
    line_y = y + DIVIDER_PAD
    draw.line((0, line_y, WIDTH, line_y), fill=DIVIDER, width=DIVIDER_WIDTH)


# --- フォント・計測 ---


def _fonts_for_emphasis(fonts: RenderFonts, emphasized: bool) -> DayFonts:
    return fonts.emphasis if emphasized else fonts.regular


def _load_fonts(regular_path: Path, bold_path: Path) -> RenderFonts:
    def _day_fonts(path: str) -> DayFonts:
        return DayFonts(
            date=ImageFont.truetype(path, DATE_FONT_SIZE),
            events=EventFonts(
                time=ImageFont.truetype(path, TIME_FONT_SIZE),
                title=ImageFont.truetype(path, TITLE_FONT_SIZE),
            ),
        )

    regular = str(regular_path)
    bold = str(bold_path)
    return RenderFonts(emphasis=_day_fonts(bold), regular=_day_fonts(regular))


def _resolve_font_paths() -> tuple[Path, Path]:
    """同梱フォントの存在を確認し、Regular / Bold のパスを返す。"""
    missing = [path for path in (REGULAR_FONT_PATH, BOLD_FONT_PATH) if not path.exists()]
    if missing:
        raise Quote0Error(
            "PNG 生成失敗 reason=bundled_font_missing "
            + " ".join(f"path={path}" for path in missing)
        )
    return REGULAR_FONT_PATH, BOLD_FONT_PATH


def _divider_height() -> int:
    return DIVIDER_PAD + DIVIDER_WIDTH + DIVIDER_PAD


def _line_height_for(line: RenderLine, fonts: RenderFonts) -> int:
    if isinstance(line, DayDividerLine):
        return _divider_height()
    day_fonts = _fonts_for_emphasis(fonts, line.emphasized)
    if isinstance(line, DateHeaderLine):
        return _line_height(day_fonts.date)
    # 予定行は title / time の大きい方に合わせる
    return max(_line_height(day_fonts.events.time), _line_height(day_fonts.events.title))


def _line_height(font: ImageFont.ImageFont) -> int:
    ascent, descent = font.getmetrics()
    return ascent + descent


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
