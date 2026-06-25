"""Tests for the report agent orchestrator."""

import pytest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from app.report_agent import run_report_agent


# ───────────────────────────────────────────────────────────────
# run_report_agent
# ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_report_agent_success(tmp_path):
    """Agent returns PDF paths in its final message."""
    channel = MagicMock()
    pdf_paths = [str(tmp_path / "report-Tower-495-2026-06-10-2026-06-10.pdf")]

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [
            MagicMock(content="Tool result", type="tool"),
            MagicMock(content=f'["{pdf_paths[0]}"]'),
        ]
    }

    with patch("app.report_agent.create_react_agent", return_value=mock_agent):
        with patch("app.report_agent.create_llm", return_value=MagicMock()):
            with patch("app.report_agent.create_agent_tools", return_value=[]):
                result = await run_report_agent(
                    channel=channel,
                    user_query="bikin report 10 juni 2026",
                    temp_dir=tmp_path,
                )

    assert result["type"] == "report"
    assert result["pdf_paths"] == pdf_paths


@pytest.mark.asyncio
async def test_run_report_agent_pdf_paths_in_dict(tmp_path):
    """Agent returns PDF paths inside a JSON dict."""
    channel = MagicMock()
    pdf_paths = [str(tmp_path / "report.pdf")]

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [
            MagicMock(content="Tool result", type="tool"),
            MagicMock(content='{"pdf_paths": ["' + pdf_paths[0] + '"]}'),
        ]
    }

    with patch("app.report_agent.create_react_agent", return_value=mock_agent):
        with patch("app.report_agent.create_llm", return_value=MagicMock()):
            with patch("app.report_agent.create_agent_tools", return_value=[]):
                result = await run_report_agent(
                    channel=channel,
                    user_query="bikin report 10 juni 2026",
                    temp_dir=tmp_path,
                )

    assert result["type"] == "report"
    assert result["pdf_paths"] == pdf_paths


@pytest.mark.asyncio
async def test_run_report_agent_no_paths_returns_error(tmp_path):
    """When tools are called but no PDFs are found, return error dict."""
    channel = MagicMock()

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [
            MagicMock(content="Tool result", type="tool"),
            MagicMock(content="Maaf, tidak ada pesan yang ditemukan di rentang tanggal tersebut."),
        ]
    }

    with patch("app.report_agent.create_react_agent", return_value=mock_agent):
        with patch("app.report_agent.create_llm", return_value=MagicMock()):
            with patch("app.report_agent.create_agent_tools", return_value=[]):
                result = await run_report_agent(
                    channel=channel,
                    user_query="random text",
                    temp_dir=tmp_path,
                )

    assert result["type"] == "error"
    assert "tidak ada pesan" in result["message"]


@pytest.mark.asyncio
async def test_run_report_agent_empty_response_returns_error(tmp_path):
    """When tools are called but response is empty, return error dict."""
    channel = MagicMock()

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [
            MagicMock(content="Tool result", type="tool"),
            MagicMock(content=""),
        ]
    }

    with patch("app.report_agent.create_react_agent", return_value=mock_agent):
        with patch("app.report_agent.create_llm", return_value=MagicMock()):
            with patch("app.report_agent.create_agent_tools", return_value=[]):
                result = await run_report_agent(
                    channel=channel,
                    user_query="test",
                    temp_dir=tmp_path,
                )

    assert result["type"] == "error"
    assert "Gagal membuat laporan" in result["message"]


@pytest.mark.asyncio
async def test_run_report_agent_greeting_no_tools(tmp_path):
    """When no tools are called, return greeting dict."""
    channel = MagicMock()

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [
            MagicMock(content="Halo! Ada yang bisa saya bantu?"),
        ]
    }

    with patch("app.report_agent.create_react_agent", return_value=mock_agent):
        with patch("app.report_agent.create_llm", return_value=MagicMock()):
            with patch("app.report_agent.create_agent_tools", return_value=[]):
                result = await run_report_agent(
                    channel=channel,
                    user_query="halo bot",
                    temp_dir=tmp_path,
                )

    assert result["type"] == "greeting"
    assert "Halo!" in result["message"]


@pytest.mark.asyncio
async def test_run_report_agent_greeting_list_content(tmp_path):
    """Gemini returns content as list of dicts — normalize and treat as greeting."""
    channel = MagicMock()

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [
            MagicMock(content=[{"type": "text", "text": "Selamat sore! Ada yang bisa saya bantu?"}]),
        ]
    }

    with patch("app.report_agent.create_react_agent", return_value=mock_agent):
        with patch("app.report_agent.create_llm", return_value=MagicMock()):
            with patch("app.report_agent.create_agent_tools", return_value=[]):
                result = await run_report_agent(
                    channel=channel,
                    user_query="selamat sore",
                    temp_dir=tmp_path,
                )

    assert result["type"] == "greeting"
    assert "Selamat sore!" in result["message"]
