"""Tests for the parser module."""

import pytest
from datetime import date, datetime, timezone

from app.parser import (
    parse_compile_command,
    parse_report_message,
    gmt7_to_utc_range,
)


# ───────────────────────────────────────────────────────────────
# parse_compile_command
# ───────────────────────────────────────────────────────────────


def test_parse_compile_command_valid():
    """Parse a valid compile command with two dates."""
    result = parse_compile_command("<@123> compile 2026-06-10 2026-06-11")
    assert result is not None
    start, end = result
    assert start == date(2026, 6, 10)
    assert end == date(2026, 6, 11)


def test_parse_compile_command_without_mention():
    """Command without mention should still parse if 'compile' keyword is present."""
    result = parse_compile_command("compile 2026-06-10 2026-06-11")
    assert result is not None
    start, end = result
    assert start == date(2026, 6, 10)
    assert end == date(2026, 6, 11)


def test_parse_compile_command_with_extra_spaces():
    """Extra spaces around the command should be tolerated."""
    result = parse_compile_command("<@123>   compile   2026-06-10   2026-06-11")
    assert result is not None
    start, end = result
    assert start == date(2026, 6, 10)
    assert end == date(2026, 6, 11)


def test_parse_compile_command_invalid_format():
    """Invalid date format should return None."""
    assert parse_compile_command("<@123> compile 10-06-2026 11-06-2026") is None


def test_parse_compile_command_missing_dates():
    """Missing one or both dates should return None."""
    assert parse_compile_command("<@123> compile 2026-06-10") is None
    assert parse_compile_command("<@123> compile") is None


def test_parse_compile_command_start_after_end():
    """Start date after end date should return None."""
    assert parse_compile_command("<@123> compile 2026-06-11 2026-06-10") is None


def test_parse_compile_command_same_day():
    """Same day for start and end is valid (inclusive)."""
    result = parse_compile_command("<@123> compile 2026-06-10 2026-06-10")
    assert result is not None
    start, end = result
    assert start == date(2026, 6, 10)
    assert end == date(2026, 6, 10)


# ───────────────────────────────────────────────────────────────
# parse_report_message
# ───────────────────────────────────────────────────────────────


def test_parse_report_message_valid():
    """Parse a valid report message with all three fields."""
    content = """id: tower 123
sub-id: section A
tanggal: 2026-06-11"""
    result = parse_report_message(content)
    assert result is not None
    assert result["id"] == "tower 123"
    assert result["sub_id"] == "section A"
    assert result["tanggal"] == date(2026, 6, 11)


def test_parse_report_message_with_extra_whitespace():
    """Extra spaces around colons should be tolerated."""
    content = "id :  tower 123\nsub-id : section A\ntanggal:2026-06-11"
    result = parse_report_message(content)
    assert result is not None
    assert result["id"] == "tower 123"
    assert result["sub_id"] == "section A"
    assert result["tanggal"] == date(2026, 6, 11)


def test_parse_report_message_missing_id():
    """Missing id field should return None."""
    content = "sub-id: section A\ntanggal: 2026-06-11"
    assert parse_report_message(content) is None


def test_parse_report_message_missing_sub_id():
    """Missing sub-id field should return None."""
    content = "id: tower 123\ntanggal: 2026-06-11"
    assert parse_report_message(content) is None


def test_parse_report_message_missing_tanggal():
    """Missing tanggal field should return None."""
    content = "id: tower 123\nsub-id: section A"
    assert parse_report_message(content) is None


def test_parse_report_message_invalid_tanggal():
    """Invalid tanggal format should return None."""
    content = "id: tower 123\nsub-id: section A\ntanggal: 11-06-2026"
    assert parse_report_message(content) is None


def test_parse_report_message_empty_content():
    """Empty content should return None."""
    assert parse_report_message("") is None


# ───────────────────────────────────────────────────────────────
# gmt7_to_utc_range
# ───────────────────────────────────────────────────────────────


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
