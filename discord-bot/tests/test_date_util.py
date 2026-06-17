"""Tests for the date utility module."""

import pytest
from datetime import date, datetime, timezone

from app.date_util import gmt7_to_utc_range


def test_gmt7_to_utc_range_single_day():
    """Single day range: 00:00 GMT+7 to 23:59:59 GMT+7."""
    start = date(2026, 6, 10)
    end = date(2026, 6, 10)
    utc_start, utc_end = gmt7_to_utc_range(start, end)

    assert utc_start == datetime(2026, 6, 9, 17, 0, 0, tzinfo=timezone.utc)
    assert utc_end == datetime(2026, 6, 10, 16, 59, 59, tzinfo=timezone.utc)


def test_gmt7_to_utc_range_multi_day():
    """Multi-day range converts correctly."""
    start = date(2026, 6, 10)
    end = date(2026, 6, 11)
    utc_start, utc_end = gmt7_to_utc_range(start, end)

    assert utc_start == datetime(2026, 6, 9, 17, 0, 0, tzinfo=timezone.utc)
    assert utc_end == datetime(2026, 6, 11, 16, 59, 59, tzinfo=timezone.utc)


def test_gmt7_to_utc_range_year_boundary():
    """Crossing year boundary should still convert correctly."""
    start = date(2026, 12, 31)
    end = date(2027, 1, 1)
    utc_start, utc_end = gmt7_to_utc_range(start, end)

    # 2026-12-31 00:00 GMT+7 = 2026-12-30 17:00 UTC
    assert utc_start == datetime(2026, 12, 30, 17, 0, 0, tzinfo=timezone.utc)
    # 2027-01-01 23:59:59 GMT+7 = 2027-01-01 16:59:59 UTC
    assert utc_end == datetime(2027, 1, 1, 16, 59, 59, tzinfo=timezone.utc)
