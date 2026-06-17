"""Tests for the Discord utility module."""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from app.discord_util import (
    parse_compile_command,
    fetch_messages_in_range,
    download_message_images,
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


# ───────────────────────────────────────────────────────────────
# download_message_images
# ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_download_message_images_no_attachments(tmp_path):
    """Message with no image attachments returns empty list."""
    msg = MagicMock()
    msg.attachments = []
    result = await download_message_images(msg, tmp_path)
    assert result == []


@pytest.mark.asyncio
async def test_download_message_images_non_image_attachments(tmp_path):
    """Message with non-image attachments returns empty list."""
    msg = MagicMock()
    msg.attachments = [MagicMock()]
    msg.attachments[0].content_type = "application/pdf"
    result = await download_message_images(msg, tmp_path)
    assert result == []
