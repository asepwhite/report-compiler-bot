"""Tests for the report extractor module."""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from app.report_extractor import (
    is_valid_report_message,
    parse_report_message,
    group_messages_by_id,
)


# ───────────────────────────────────────────────────────────────
# is_valid_report_message
# ───────────────────────────────────────────────────────────────


def _make_message(content="", attachments=None, created_at=None):
    """Helper to create a mock Discord message."""
    msg = MagicMock()
    msg.content = content
    msg.attachments = attachments or []
    msg.created_at = created_at or datetime(2026, 6, 11, 10, 0, 0, tzinfo=timezone.utc)
    return msg


def _make_attachment(content_type="image/png"):
    """Helper to create a mock attachment."""
    att = MagicMock()
    att.content_type = content_type
    return att


def test_valid_report_message():
    """A message with image attachment and valid content passes."""
    msg = _make_message(
        content="id: tower 123\nsub-id: section A\ntanggal: 2026-06-11",
        attachments=[_make_attachment("image/png")],
    )
    start = date(2026, 6, 10)
    end = date(2026, 6, 11)
    result = is_valid_report_message(msg, start, end)
    assert result is not None
    assert result["id"] == "tower 123"
    assert result["sub_id"] == "section A"
    assert result["tanggal"] == date(2026, 6, 11)


def test_valid_report_message_with_multiple_images():
    """A message with multiple image attachments passes."""
    msg = _make_message(
        content="id: tower 123\nsub-id: section A\ntanggal: 2026-06-11",
        attachments=[_make_attachment("image/png"), _make_attachment("image/jpeg")],
    )
    result = is_valid_report_message(msg, date(2026, 6, 10), date(2026, 6, 11))
    assert result is not None


def test_no_image_attachment():
    """A message without image attachments fails."""
    msg = _make_message(
        content="id: tower 123\nsub-id: section A\ntanggal: 2026-06-11",
        attachments=[],
    )
    assert is_valid_report_message(msg, date(2026, 6, 10), date(2026, 6, 11)) is None


def test_non_image_attachment():
    """A message with non-image attachments fails."""
    msg = _make_message(
        content="id: tower 123\nsub-id: section A\ntanggal: 2026-06-11",
        attachments=[_make_attachment("application/pdf")],
    )
    assert is_valid_report_message(msg, date(2026, 6, 10), date(2026, 6, 11)) is None


def test_invalid_content_format():
    """A message with image but invalid content format fails."""
    msg = _make_message(
        content="Hello world",
        attachments=[_make_attachment("image/png")],
    )
    assert is_valid_report_message(msg, date(2026, 6, 10), date(2026, 6, 11)) is None


def test_tanggal_outside_range():
    """A message with valid content but tanggal outside range fails."""
    msg = _make_message(
        content="id: tower 123\nsub-id: section A\ntanggal: 2026-06-12",
        attachments=[_make_attachment("image/png")],
    )
    assert is_valid_report_message(msg, date(2026, 6, 10), date(2026, 6, 11)) is None


def test_tanggal_at_range_boundary():
    """A message with tanggal exactly at start boundary passes."""
    msg = _make_message(
        content="id: tower 123\nsub-id: section A\ntanggal: 2026-06-10",
        attachments=[_make_attachment("image/png")],
    )
    result = is_valid_report_message(msg, date(2026, 6, 10), date(2026, 6, 11))
    assert result is not None


def test_tanggal_at_end_boundary():
    """A message with tanggal exactly at end boundary passes."""
    msg = _make_message(
        content="id: tower 123\nsub-id: section A\ntanggal: 2026-06-11",
        attachments=[_make_attachment("image/png")],
    )
    result = is_valid_report_message(msg, date(2026, 6, 10), date(2026, 6, 11))
    assert result is not None


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
# group_messages_by_id
# ───────────────────────────────────────────────────────────────


def test_group_messages_by_id_single_group():
    """Messages with the same id are grouped together."""
    messages = [
        {"id": "tower 123", "sub_id": "section A", "tanggal": date(2026, 6, 10), "message_id": 1, "local_images": ["/tmp/img1.png"]},
        {"id": "tower 123", "sub_id": "section A", "tanggal": date(2026, 6, 11), "message_id": 2, "local_images": ["/tmp/img2.png"]},
    ]
    result = group_messages_by_id(messages)
    assert "tower 123" in result
    assert "section A" in result["tower 123"]
    assert len(result["tower 123"]["section A"]) == 2
    assert result["tower 123"]["section A"][0]["message_id"] == 1


def test_group_messages_by_id_multiple_sub_ids():
    """Messages with same id but different sub-ids are grouped separately."""
    messages = [
        {"id": "tower 123", "sub_id": "section A", "tanggal": date(2026, 6, 10), "message_id": 1, "local_images": ["/tmp/img1.png"]},
        {"id": "tower 123", "sub_id": "section B", "tanggal": date(2026, 6, 11), "message_id": 2, "local_images": ["/tmp/img2.png"]},
    ]
    result = group_messages_by_id(messages)
    assert "tower 123" in result
    assert "section A" in result["tower 123"]
    assert "section B" in result["tower 123"]
    assert len(result["tower 123"]["section A"]) == 1
    assert len(result["tower 123"]["section B"]) == 1


def test_group_messages_by_id_multiple_ids():
    """Messages with different ids are grouped into separate top-level keys."""
    messages = [
        {"id": "tower 123", "sub_id": "section A", "tanggal": date(2026, 6, 10), "message_id": 1, "local_images": ["/tmp/img1.png"]},
        {"id": "tower 456", "sub_id": "section A", "tanggal": date(2026, 6, 11), "message_id": 2, "local_images": ["/tmp/img2.png"]},
    ]
    result = group_messages_by_id(messages)
    assert "tower 123" in result
    assert "tower 456" in result
