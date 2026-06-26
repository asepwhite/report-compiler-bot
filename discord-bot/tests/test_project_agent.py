"""Tests for the project agent module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage

from app.project_agent import run_project_agent


# ───────────────────────────────────────────────────────────────
# run_project_agent
# ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_project_agent_create_project():
    """Agent creates a new project via MCP tools."""
    mock_session = AsyncMock()

    with patch("app.project_agent.sqlite_mcp_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.project_agent.create_project_tools", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = []

            with patch("app.project_agent.create_llm") as mock_llm:
                mock_model = MagicMock()
                mock_llm.return_value = mock_model

                with patch("app.project_agent.create_react_agent") as mock_agent_factory:
                    mock_agent = AsyncMock()
                    mock_agent.ainvoke.return_value = {
                        "messages": [
                            AIMessage(content="Project berhasil disimpan!"),
                        ]
                    }
                    mock_agent_factory.return_value = mock_agent

                    result = await run_project_agent("simpan tower T123 di jalur jakarta")

    assert result["type"] == "success"
    assert "berhasil" in result["message"].lower()
    mock_agent_factory.assert_called_once()


@pytest.mark.asyncio
async def test_run_project_agent_read_project():
    """Agent reads a project via MCP tools."""
    mock_session = AsyncMock()

    with patch("app.project_agent.sqlite_mcp_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.project_agent.create_project_tools", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = []

            with patch("app.project_agent.create_llm") as mock_llm:
                mock_model = MagicMock()
                mock_llm.return_value = mock_model

                with patch("app.project_agent.create_react_agent") as mock_agent_factory:
                    mock_agent = AsyncMock()
                    mock_agent.ainvoke.return_value = {
                        "messages": [
                            AIMessage(content="Ditemukan 1 project: Tower T123, Jalur Jakarta"),
                        ]
                    }
                    mock_agent_factory.return_value = mock_agent

                    result = await run_project_agent("cari tower T123")

    assert result["type"] == "success"
    assert "Ditemukan" in result["message"]


@pytest.mark.asyncio
async def test_run_project_agent_no_tool_calls():
    """Agent with no tool calls returns success with the LLM's text."""
    mock_session = AsyncMock()

    with patch("app.project_agent.sqlite_mcp_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.project_agent.create_project_tools", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = []

            with patch("app.project_agent.create_llm") as mock_llm:
                mock_model = MagicMock()
                mock_llm.return_value = mock_model

                with patch("app.project_agent.create_react_agent") as mock_agent_factory:
                    mock_agent = AsyncMock()
                    # No ToolMessage in the history
                    mock_agent.ainvoke.return_value = {
                        "messages": [
                            AIMessage(content="Halo! Ada yang bisa saya bantu?"),
                        ]
                    }
                    mock_agent_factory.return_value = mock_agent

                    result = await run_project_agent("halo")

    assert result["type"] == "success"
    assert "Halo" in result["message"]


@pytest.mark.asyncio
async def test_run_project_agent_error_handling():
    """Agent returns error dict when MCP server fails."""
    with patch("app.project_agent.sqlite_mcp_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(
            side_effect=RuntimeError("MCP server failed")
        )

        result = await run_project_agent("simpan tower T123")

    assert result["type"] == "error"
    assert "gagal" in result["message"].lower()
