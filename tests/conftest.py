"""pytest 共通 fixture。"""

from __future__ import annotations

import pytest

from handy_calendar.steps.render import _load_fonts, _resolve_font_paths


@pytest.fixture(scope="module")
def render_fonts():
    """render 系テスト用の太字/通常フォント。"""
    regular_path, bold_path = _resolve_font_paths()
    return _load_fonts(regular_path, bold_path)
