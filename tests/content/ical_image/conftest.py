"""ical_image テスト用 fixture。"""

from __future__ import annotations

import pytest

from quote0.content.ical_image.render import _load_fonts, _resolve_font_paths


@pytest.fixture(scope="module")
def render_fonts():
    """render 系テスト用の太字/通常フォント。"""
    regular_path, bold_path = _resolve_font_paths()
    return _load_fonts(regular_path, bold_path)
