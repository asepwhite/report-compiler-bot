"""Tests for the report agent orchestrator."""

import pytest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from app.intent_classifier import IntentClassification
from app.report_agent import run_report_agent


# ───────────────────────────────────────────────────────────────
# run_report_agent
# ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_report_agent_success(tmp_path):
    """Agent returns .docx paths in its final message."""
    channel = MagicMock()
    docx_paths = [str(tmp_path / "report-Tower-495-2026-06-10-2026-06-10.docx")]

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [
            MagicMock(content="Tool result", type="tool"),
            MagicMock(content=f'["{docx_paths[0]}"]'),
        ]
    }

    ack_called = False
    async def fake_ack():
        nonlocal ack_called
        ack_called = True

    intent = IntentClassification(intent="report_request", confidence=0.95, reasoning="test")
    with patch("app.report_agent.classify_intent", return_value=intent):
        with patch("app.report_agent.create_react_agent", return_value=mock_agent):
            with patch("app.report_agent.create_llm", return_value=MagicMock()):
                with patch("app.report_agent.create_agent_tools", return_value=[]):
                    result = await run_report_agent(
                        channel=channel,
                        user_query="bikin report 10 juni 2026",
                        temp_dir=tmp_path,
                        send_ack=fake_ack,
                    )

    assert result["type"] == "report"
    assert result["docx_paths"] == docx_paths
    assert ack_called is True


@pytest.mark.asyncio
async def test_run_report_agent_docx_paths_in_dict(tmp_path):
    """Agent returns .docx paths inside a JSON dict."""
    channel = MagicMock()
    docx_paths = [str(tmp_path / "report.docx")]

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [
            MagicMock(content="Tool result", type="tool"),
            MagicMock(content='{"docx_paths": ["' + docx_paths[0] + '"]}'),
        ]
    }

    intent = IntentClassification(intent="report_request", confidence=0.95, reasoning="test")
    with patch("app.report_agent.classify_intent", return_value=intent):
        with patch("app.report_agent.create_react_agent", return_value=mock_agent):
            with patch("app.report_agent.create_llm", return_value=MagicMock()):
                with patch("app.report_agent.create_agent_tools", return_value=[]):
                    result = await run_report_agent(
                        channel=channel,
                        user_query="bikin report 10 juni 2026",
                        temp_dir=tmp_path,
                    )

    assert result["type"] == "report"
    assert result["docx_paths"] == docx_paths


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

    intent = IntentClassification(intent="report_request", confidence=0.95, reasoning="test")
    with patch("app.report_agent.classify_intent", return_value=intent):
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

    intent = IntentClassification(intent="report_request", confidence=0.95, reasoning="test")
    with patch("app.report_agent.classify_intent", return_value=intent):
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

    intent = IntentClassification(intent="greeting", confidence=0.92, reasoning="test")
    with patch("app.report_agent.classify_intent", return_value=intent):
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

    intent = IntentClassification(intent="greeting", confidence=0.92, reasoning="test")
    with patch("app.report_agent.classify_intent", return_value=intent):
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


@pytest.mark.asyncio
async def test_run_report_agent_off_topic_blocked(tmp_path):
    """High-confidence off-topic queries are blocked before the agent runs."""
    channel = MagicMock()

    intent = IntentClassification(
        intent="off_topic",
        confidence=0.88,
        reasoning="Pengguna bertanya tentang pemrograman",
    )
    with patch("app.report_agent.classify_intent", return_value=intent):
        # Agent should never be created or invoked
        with patch("app.report_agent.create_react_agent") as mock_create_agent:
            result = await run_report_agent(
                channel=channel,
                user_query="apa itu Python",
                temp_dir=tmp_path,
            )

    assert result["type"] == "off_topic"
    assert "hanya bisa membantu dengan pembuatan laporan" in result["message"]
    mock_create_agent.assert_not_called()


@pytest.mark.asyncio
async def test_run_report_agent_mixed_intent_blocked(tmp_path):
    """Mixed-intent (report + off-topic question) is blocked before the agent runs."""
    channel = MagicMock()

    intent = IntentClassification(
        intent="off_topic",
        confidence=0.85,
        reasoning="Pengguna meminta laporan tetapi juga bertanya jarak antar kota",
    )
    with patch("app.report_agent.classify_intent", return_value=intent):
        with patch("app.report_agent.create_react_agent") as mock_create_agent:
            result = await run_report_agent(
                channel=channel,
                user_query=(
                    "om tolong bantu bikin laporan @reporting-bot , "
                    "tapi gw harus tau dulu jarak dari jakarta ke bandung"
                ),
                temp_dir=tmp_path,
            )

    assert result["type"] == "off_topic"
    assert "hanya bisa membantu dengan pembuatan laporan" in result["message"]
    mock_create_agent.assert_not_called()


@pytest.mark.asyncio
async def test_run_report_agent_low_confidence_off_topic_allowed(tmp_path):
    """Low-confidence off-topic is overridden to report_request and agent runs."""
    channel = MagicMock()
    docx_paths = [str(tmp_path / "report.docx")]

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [
            MagicMock(content="Tool result", type="tool"),
            MagicMock(content=f'["{docx_paths[0]}"]'),
        ]
    }

    # classify_intent returns off_topic but with low confidence → overridden to report_request
    intent = IntentClassification(
        intent="report_request",
        confidence=0.5,
        reasoning="Dianggap report_request karena confidence off_topic (0.50) di bawah threshold (0.6)",
    )
    with patch("app.report_agent.classify_intent", return_value=intent):
        with patch("app.report_agent.create_react_agent", return_value=mock_agent):
            with patch("app.report_agent.create_llm", return_value=MagicMock()):
                with patch("app.report_agent.create_agent_tools", return_value=[]):
                    result = await run_report_agent(
                        channel=channel,
                        user_query="tolong bantu",
                        temp_dir=tmp_path,
                    )

    assert result["type"] == "report"
    assert result["docx_paths"] == docx_paths


@pytest.mark.asyncio
async def test_run_report_agent_ack_not_called_for_greeting(tmp_path):
    """ACK callback is not called for greeting intent."""
    channel = MagicMock()

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [
            MagicMock(content="Halo!"),
        ]
    }

    ack_called = False
    async def fake_ack():
        nonlocal ack_called
        ack_called = True

    intent = IntentClassification(intent="greeting", confidence=0.95, reasoning="test")
    with patch("app.report_agent.classify_intent", return_value=intent):
        with patch("app.report_agent.create_react_agent", return_value=mock_agent):
            with patch("app.report_agent.create_llm", return_value=MagicMock()):
                with patch("app.report_agent.create_agent_tools", return_value=[]):
                    result = await run_report_agent(
                        channel=channel,
                        user_query="halo",
                        temp_dir=tmp_path,
                        send_ack=fake_ack,
                    )

    assert result["type"] == "greeting"
    assert ack_called is False


@pytest.mark.asyncio
async def test_run_report_agent_ack_not_called_for_off_topic(tmp_path):
    """ACK callback is not called for off-topic intent."""
    channel = MagicMock()

    ack_called = False
    async def fake_ack():
        nonlocal ack_called
        ack_called = True

    intent = IntentClassification(
        intent="off_topic",
        confidence=0.88,
        reasoning="Pengguna bertanya tentang pemrograman",
    )
    with patch("app.report_agent.classify_intent", return_value=intent):
        with patch("app.report_agent.create_react_agent") as mock_create_agent:
            result = await run_report_agent(
                channel=channel,
                user_query="apa itu Python",
                temp_dir=tmp_path,
                send_ack=fake_ack,
            )

    assert result["type"] == "off_topic"
    assert ack_called is False
    mock_create_agent.assert_not_called()
