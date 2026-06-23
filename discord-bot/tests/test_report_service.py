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
async def test_compile_report_single_image_metadata(tmp_path):
    """A single image with valid metadata generates one PDF."""
    channel = MagicMock()

    msg = MagicMock()
    msg.id = 1
    msg.attachments = [MagicMock()]
    msg.attachments[0].content_type = "image/png"
    msg.attachments[0].url = "https://cdn.discordapp.com/test.png"
    msg.attachments[0].filename = "test.png"

    mock_metadata = MagicMock()
    mock_metadata.tower_id = "Tower 495"
    mock_metadata.sub_id = "Section mid"
    mock_metadata.report_date = date(2026, 6, 10)
    mock_metadata.raw_text = "date: Sabtu, 23 Mei 2026, tower: T.495, section: Section: Mid"

    with patch("app.report_service.fetch_messages_in_range", new=AsyncMock(return_value=[msg])):
        with patch("app.report_service.is_valid_report_message", return_value=True):
            with patch("app.report_service.download_message_images", new=AsyncMock(return_value=[str(tmp_path / "test.png")])):
                with patch("app.report_service.extract_image_metadata", new=AsyncMock(return_value=mock_metadata)):
                    with patch("app.report_service.generate_pdf") as mock_pdf:
                        result = await compile_report(channel, date(2026, 6, 10), date(2026, 6, 11), tmp_path)

    assert len(result) == 1
    assert mock_pdf.called
    call_kwargs = mock_pdf.call_args.kwargs
    assert call_kwargs["report_id"] == "Tower 495"
    assert call_kwargs["start_date"] == date(2026, 6, 10)
    assert call_kwargs["end_date"] == date(2026, 6, 11)


@pytest.mark.asyncio
async def test_compile_report_multiple_images_different_towers(tmp_path):
    """Multiple images for different towers generate multiple PDFs."""
    channel = MagicMock()

    msg = MagicMock()
    msg.id = 1
    msg.attachments = [MagicMock(), MagicMock()]
    for att in msg.attachments:
        att.content_type = "image/png"
        att.url = "https://cdn.discordapp.com/test.png"
        att.filename = "test.png"

    meta1 = MagicMock()
    meta1.tower_id = "Tower 495"
    meta1.sub_id = "Section mid"
    meta1.report_date = date(2026, 6, 10)
    meta1.raw_text = "raw1"

    meta2 = MagicMock()
    meta2.tower_id = "Tower 500"
    meta2.sub_id = "Section top"
    meta2.report_date = date(2026, 6, 11)
    meta2.raw_text = "raw2"

    with patch("app.report_service.fetch_messages_in_range", new=AsyncMock(return_value=[msg])):
        with patch("app.report_service.is_valid_report_message", return_value=True):
            with patch("app.report_service.download_message_images", new=AsyncMock(return_value=[str(tmp_path / "img1.png"), str(tmp_path / "img2.png")])):
                with patch("app.report_service.extract_image_metadata", new=AsyncMock(side_effect=[meta1, meta2])):
                    with patch("app.report_service.generate_pdf") as mock_pdf:
                        result = await compile_report(channel, date(2026, 6, 10), date(2026, 6, 11), tmp_path)

    assert len(result) == 2
    assert mock_pdf.call_count == 2


@pytest.mark.asyncio
async def test_compile_report_skips_invalid_metadata(tmp_path):
    """Images with failed metadata extraction are skipped."""
    channel = MagicMock()

    msg = MagicMock()
    msg.id = 1
    msg.attachments = [MagicMock()]
    msg.attachments[0].content_type = "image/png"
    msg.attachments[0].url = "https://cdn.discordapp.com/test.png"
    msg.attachments[0].filename = "test.png"

    with patch("app.report_service.fetch_messages_in_range", new=AsyncMock(return_value=[msg])):
        with patch("app.report_service.is_valid_report_message", return_value=True):
            with patch("app.report_service.download_message_images", new=AsyncMock(return_value=[str(tmp_path / "test.png")])):
                with patch("app.report_service.extract_image_metadata", new=AsyncMock(return_value=None)):
                    with patch("app.report_service.generate_pdf") as mock_pdf:
                        result = await compile_report(channel, date(2026, 6, 10), date(2026, 6, 11), tmp_path)

    assert result == []
    assert not mock_pdf.called


@pytest.mark.asyncio
async def test_compile_report_skips_out_of_range_date(tmp_path):
    """Images with report date outside range are skipped."""
    channel = MagicMock()

    msg = MagicMock()
    msg.id = 1
    msg.attachments = [MagicMock()]
    msg.attachments[0].content_type = "image/png"
    msg.attachments[0].url = "https://cdn.discordapp.com/test.png"
    msg.attachments[0].filename = "test.png"

    mock_metadata = MagicMock()
    mock_metadata.tower_id = "Tower 495"
    mock_metadata.sub_id = "Section mid"
    mock_metadata.report_date = date(2026, 6, 15)  # Outside range
    mock_metadata.raw_text = "raw"

    with patch("app.report_service.fetch_messages_in_range", new=AsyncMock(return_value=[msg])):
        with patch("app.report_service.is_valid_report_message", return_value=True):
            with patch("app.report_service.download_message_images", new=AsyncMock(return_value=[str(tmp_path / "test.png")])):
                with patch("app.report_service.extract_image_metadata", new=AsyncMock(return_value=mock_metadata)):
                    with patch("app.report_service.generate_pdf") as mock_pdf:
                        result = await compile_report(channel, date(2026, 6, 10), date(2026, 6, 11), tmp_path)

    assert result == []
    assert not mock_pdf.called


@pytest.mark.asyncio
async def test_compile_report_no_images_in_message(tmp_path):
    """Messages without image attachments are skipped."""
    channel = MagicMock()

    msg = MagicMock()
    msg.id = 1
    msg.attachments = []

    with patch("app.report_service.fetch_messages_in_range", new=AsyncMock(return_value=[msg])):
        with patch("app.report_service.is_valid_report_message", return_value=False):
            with patch("app.report_service.generate_pdf") as mock_pdf:
                result = await compile_report(channel, date(2026, 6, 10), date(2026, 6, 11), tmp_path)

    assert result == []
    assert not mock_pdf.called
