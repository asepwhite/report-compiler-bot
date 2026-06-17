"""Tests for the message filter module."""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, AsyncMock

from app.message_filter import is_valid_report_message, fetch_messages_in_range


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
# fetch_messages_in_range
# ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_messages_in_range():
    """Fetch messages within a UTC datetime range."""
    channel = MagicMock()
    msg1 = MagicMock()
    msg1.created_at = datetime(2026, 6, 10, 10, 0, 0, tzinfo=timezone.utc)
    msg2 = MagicMock()
    msg2.created_at = datetime(2026, 6, 11, 10, 0, 0, tzinfo=timezone.utc)
    msg3 = MagicMock()
    msg3.created_at = datetime(2026, 6, 11, 16, 59, 59, tzinfo=timezone.utc)

    # Simulate history() async generator
    async def mock_history(*, limit=None, before=None, after=None):
        for msg in [msg1, msg2, msg3]:
            yield msg

    channel.history = mock_history

    start = datetime(2026, 6, 9, 17, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 11, 16, 59, 59, tzinfo=timezone.utc)
    result = await fetch_messages_in_range(channel, start, end)

    assert result == [msg1, msg2, msg3]


@pytest.mark.asyncio
async def test_fetch_messages_in_range_empty():
    """Fetch messages returns empty list when no messages."""
    channel = MagicMock()

    async def mock_history(*, limit=None, before=None, after=None):
        return
        yield  # Make it a generator

    channel.history = mock_history

    start = datetime(2026, 6, 9, 17, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 11, 16, 59, 59, tzinfo=timezone.utc)
    result = await fetch_messages_in_range(channel, start, end)

    assert result == []


@pytest.mark.asyncio
async def test_fetch_messages_in_range_filters_outside():
    """Messages outside the UTC range are filtered out."""
    channel = MagicMock()
    msg_in = MagicMock()
    msg_in.created_at = datetime(2026, 6, 10, 10, 0, 0, tzinfo=timezone.utc)
    msg_out = MagicMock()
    msg_out.created_at = datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc)

    async def mock_history(*, limit=None, before=None, after=None):
        for msg in [msg_in, msg_out]:
            yield msg

    channel.history = mock_history

    start = datetime(2026, 6, 9, 17, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 11, 16, 59, 59, tzinfo=timezone.utc)
    result = await fetch_messages_in_range(channel, start, end)

    assert result == [msg_in]
