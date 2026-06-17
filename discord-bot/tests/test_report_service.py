"""Tests for the report service module."""

import pytest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from app.report_service import compile_report


# ───────────────────────────────────────────────────────────────
# compile_report
# ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compile_report_no_messages(tmp_path):
    """When no valid messages are found, returns empty list."""
    channel = MagicMock()

    with patch("app.report_service.fetch_messages_in_range", new=AsyncMock(return_value=[])):
        result = await compile_report(channel, date(2026, 6, 10), date(2026, 6, 11), tmp_path)

    assert result == []


@pytest.mark.asyncio
async def test_compile_report_single_id(tmp_path):
    """A single tower id generates one PDF."""
    channel = MagicMock()

    msg = MagicMock()
    msg.id = 1
    msg.attachments = [MagicMock()]
    msg.attachments[0].content_type = "image/png"
    msg.attachments[0].url = "https://cdn.discordapp.com/test.png"
    msg.attachments[0].filename = "test.png"

    with patch("app.report_service.fetch_messages_in_range", new=AsyncMock(return_value=[msg])):
        with patch("app.report_service.is_valid_report_message", return_value={
            "id": "tower 123", "sub_id": "section A", "tanggal": date(2026, 6, 10)
        }):
            with patch("app.report_service.download_message_images", new=AsyncMock(return_value=[str(tmp_path / "test.png")])):
                with patch("app.report_service.generate_pdf") as mock_pdf:
                    result = await compile_report(channel, date(2026, 6, 10), date(2026, 6, 11), tmp_path)

    assert len(result) == 1
    assert mock_pdf.called
    call_kwargs = mock_pdf.call_args.kwargs
    assert call_kwargs["report_id"] == "tower 123"
    assert call_kwargs["start_date"] == date(2026, 6, 10)
    assert call_kwargs["end_date"] == date(2026, 6, 11)


@pytest.mark.asyncio
async def test_compile_report_multiple_ids(tmp_path):
    """Multiple tower ids generate multiple PDFs."""
    channel = MagicMock()

    msg1 = MagicMock()
    msg1.id = 1
    msg1.attachments = [MagicMock()]
    msg1.attachments[0].content_type = "image/png"
    msg1.attachments[0].url = "https://cdn.discordapp.com/test1.png"
    msg1.attachments[0].filename = "test1.png"

    msg2 = MagicMock()
    msg2.id = 2
    msg2.attachments = [MagicMock()]
    msg2.attachments[0].content_type = "image/png"
    msg2.attachments[0].url = "https://cdn.discordapp.com/test2.png"
    msg2.attachments[0].filename = "test2.png"

    def mock_is_valid(msg, start_date, end_date):
        if msg.id == 1:
            return {"id": "tower 123", "sub_id": "section A", "tanggal": date(2026, 6, 10)}
        else:
            return {"id": "tower 456", "sub_id": "section B", "tanggal": date(2026, 6, 11)}

    with patch("app.report_service.fetch_messages_in_range", new=AsyncMock(return_value=[msg1, msg2])):
        with patch("app.report_service.is_valid_report_message", side_effect=mock_is_valid):
            with patch("app.report_service.download_message_images", new=AsyncMock(return_value=[str(tmp_path / "test.png")])):
                with patch("app.report_service.generate_pdf") as mock_pdf:
                    result = await compile_report(channel, date(2026, 6, 10), date(2026, 6, 11), tmp_path)

    assert len(result) == 2
    assert mock_pdf.call_count == 2


@pytest.mark.asyncio
async def test_compile_report_download_failure_skipped(tmp_path):
    """If image download fails, the message is still included but with empty images."""
    channel = MagicMock()

    msg = MagicMock()
    msg.id = 1
    msg.attachments = [MagicMock()]
    msg.attachments[0].content_type = "image/png"
    msg.attachments[0].url = "https://cdn.discordapp.com/test.png"
    msg.attachments[0].filename = "test.png"

    with patch("app.report_service.fetch_messages_in_range", new=AsyncMock(return_value=[msg])):
        with patch("app.report_service.is_valid_report_message", return_value={
            "id": "tower 123", "sub_id": "section A", "tanggal": date(2026, 6, 10)
        }):
            with patch("app.report_service.download_message_images", new=AsyncMock(return_value=[])):
                with patch("app.report_service.generate_pdf") as mock_pdf:
                    result = await compile_report(channel, date(2026, 6, 10), date(2026, 6, 11), tmp_path)

    assert len(result) == 1
    assert mock_pdf.called
    call_kwargs = mock_pdf.call_args.kwargs
    assert call_kwargs["grouped_data"]["section A"][0]["images"] == []
