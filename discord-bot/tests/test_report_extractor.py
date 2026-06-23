"""Tests for the report extractor module."""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from app.report_extractor import (
    is_valid_report_message,
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


def test_valid_report_message_with_image():
    """A message with an image attachment is valid."""
    msg = _make_message(
        content="",
        attachments=[_make_attachment("image/png")],
    )
    assert is_valid_report_message(msg) is True


def test_valid_report_message_with_multiple_images():
    """A message with multiple image attachments is valid."""
    msg = _make_message(
        content="",
        attachments=[_make_attachment("image/png"), _make_attachment("image/jpeg")],
    )
    assert is_valid_report_message(msg) is True


def test_valid_report_message_with_text_and_image():
    """A message with text content and image is valid (text no longer matters)."""
    msg = _make_message(
        content="some random text",
        attachments=[_make_attachment("image/png")],
    )
    assert is_valid_report_message(msg) is True


def test_no_image_attachment():
    """A message without image attachments is not valid."""
    msg = _make_message(
        content="",
        attachments=[],
    )
    assert is_valid_report_message(msg) is False


def test_non_image_attachment():
    """A message with non-image attachments is not valid."""
    msg = _make_message(
        content="",
        attachments=[_make_attachment("application/pdf")],
    )
    assert is_valid_report_message(msg) is False


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
