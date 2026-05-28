"""models.py の単体テスト。"""

from __future__ import annotations

from datetime import datetime

import pytest

from handy_calendar.models import JST, DateRange


def test_date_range_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="タイムゾーン付き"):
        DateRange(datetime(2026, 5, 28, 0, 0), datetime(2026, 5, 29, 0, 0))


def test_date_range_rejects_empty_range() -> None:
    start = datetime(2026, 5, 28, 0, 0, tzinfo=JST)

    with pytest.raises(ValueError, match="start < end"):
        DateRange(start, start)


def test_date_range_overlaps_half_open_range() -> None:
    today = DateRange(
        datetime(2026, 5, 28, 0, 0, tzinfo=JST),
        datetime(2026, 5, 29, 0, 0, tzinfo=JST),
    )
    event = DateRange(
        datetime(2026, 5, 28, 23, 0, tzinfo=JST),
        datetime(2026, 5, 29, 1, 0, tzinfo=JST),
    )

    assert today.overlaps(event)


def test_date_range_does_not_overlap_adjacent_half_open_range() -> None:
    today = DateRange(
        datetime(2026, 5, 28, 0, 0, tzinfo=JST),
        datetime(2026, 5, 29, 0, 0, tzinfo=JST),
    )
    tomorrow = DateRange(
        datetime(2026, 5, 29, 0, 0, tzinfo=JST),
        datetime(2026, 5, 30, 0, 0, tzinfo=JST),
    )

    assert not today.overlaps(tomorrow)
