"""Tests for the report agent orchestrator."""

import pytest
from datetime import date
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from app.report_agent import (
    run_report_agent,
    DateParseError,
    NoMessagesError,
    NoValidReportsError,
)
from app.nl_date_parser import ReportDateRequest


# ───────────────────────────────────────────────────────────────
# run_report_agent
# ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_report_agent_success(tmp_path):
    """Full successful pipeline: dates → messages → process → PDFs."""
    channel = MagicMock()
    date_request = ReportDateRequest(
        discord_start_date=date(2026, 6, 10),
        discord_end_date=date(2026, 6, 11),
        report_start_date=date(2026, 6, 10),
        report_end_date=date(2026, 6, 10),
        reasoning="test",
    )
    messages = [{"message_id": 1, "content": "test"}]
    processed = [
        {
            "tower_id": "tower 123",
            "sub_id": "section A",
            "report_date": "2026-06-10",
            "message_id": 1,
            "images": [str(tmp_path / "test.png")],
        }
    ]
    pdf_paths = [str(tmp_path / "report-tower 123-2026-06-10-2026-06-10.pdf")]

    with patch("app.report_agent.parse_report_dates", return_value=date_request):
        with patch("app.report_agent.retrieve_messages", new=AsyncMock(return_value=messages)):
            with patch("app.report_agent.process_messages", new=AsyncMock(return_value=processed)):
                with patch("app.report_agent.generate_pdf_reports", return_value=pdf_paths):
                    result = await run_report_agent(
                        channel=channel,
                        user_query="bikin report 10 juni 2026",
                        temp_dir=tmp_path,
                    )

    assert result == pdf_paths


@pytest.mark.asyncio
async def test_run_report_agent_date_parse_failure():
    """When date parsing fails, DateParseError is raised."""
    channel = MagicMock()

    with patch("app.report_agent.parse_report_dates", return_value=None):
        with pytest.raises(DateParseError) as exc_info:
            await run_report_agent(
                channel=channel,
                user_query="random text",
                temp_dir=Path("/tmp"),
            )

    assert "Gagal membuat laporan secara otomatis" in exc_info.value.message


@pytest.mark.asyncio
async def test_run_report_agent_no_messages():
    """When no Discord messages are found, NoMessagesError is raised."""
    channel = MagicMock()
    date_request = ReportDateRequest(
        discord_start_date=date(2026, 6, 10),
        discord_end_date=date(2026, 6, 10),
        report_start_date=date(2026, 6, 10),
        report_end_date=date(2026, 6, 10),
        reasoning="test",
    )

    with patch("app.report_agent.parse_report_dates", return_value=date_request):
        with patch("app.report_agent.retrieve_messages", new=AsyncMock(return_value=[])):
            with pytest.raises(NoMessagesError) as exc_info:
                await run_report_agent(
                    channel=channel,
                    user_query="bikin report 10 juni 2026",
                    temp_dir=Path("/tmp"),
                )

    assert "Tidak ada pesan yang ditemukan" in exc_info.value.message


@pytest.mark.asyncio
async def test_run_report_agent_no_valid_reports():
    """When no valid report messages exist, NoValidReportsError is raised."""
    channel = MagicMock()
    date_request = ReportDateRequest(
        discord_start_date=date(2026, 6, 10),
        discord_end_date=date(2026, 6, 10),
        report_start_date=date(2026, 6, 10),
        report_end_date=date(2026, 6, 10),
        reasoning="test",
    )
    messages = [{"message_id": 1, "content": "test"}]

    with patch("app.report_agent.parse_report_dates", return_value=date_request):
        with patch("app.report_agent.retrieve_messages", new=AsyncMock(return_value=messages)):
            with patch("app.report_agent.process_messages", new=AsyncMock(return_value=[])):
                with pytest.raises(NoValidReportsError) as exc_info:
                    await run_report_agent(
                        channel=channel,
                        user_query="bikin report 10 juni 2026",
                        temp_dir=Path("/tmp"),
                    )

    assert "Tidak ada pesan laporan yang valid" in exc_info.value.message
