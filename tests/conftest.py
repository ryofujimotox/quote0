"""pytest 共通 fixture。"""

from __future__ import annotations

import pytest

from handy_calendar.steps.render import _bold_font_candidates, _load_fonts, _regular_font_candidates


@pytest.fixture(scope="module")
def render_fonts():
    """render 系テスト用の太字/通常フォント。"""
    regular_path = next(path for path in _regular_font_candidates() if path.exists())
    bold_path = next(path for path in _bold_font_candidates() if path.exists())
    return _load_fonts(regular_path, bold_path)
