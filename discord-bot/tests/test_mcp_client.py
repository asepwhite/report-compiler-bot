"""Tests for the MCP SQLite client wrapper."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from app.mcp_client import sqlite_mcp_session, get_project_db_path


# ───────────────────────────────────────────────────────────────
# get_project_db_path
# ───────────────────────────────────────────────────────────────


def test_get_project_db_path_default():
    """Default DB path is inside the project."""
    path = get_project_db_path()
    assert isinstance(path, str)
    assert "data/projects.db" in path


# ───────────────────────────────────────────────────────────────
# sqlite_mcp_session
# ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sqlite_mcp_session_initializes_and_yields_session():
    """The context manager initializes the MCP session and yields it."""
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_stdio = MagicMock()
    mock_stdio.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
    mock_stdio.__aexit__ = AsyncMock(return_value=False)

    with patch("app.mcp_client.stdio_client", return_value=mock_stdio):
        with patch("app.mcp_client.ClientSession", return_value=mock_session):
            async with sqlite_mcp_session("/tmp/test.db") as session:
                assert session is mock_session
                mock_session.initialize.assert_awaited_once()


@pytest.mark.asyncio
async def test_sqlite_mcp_session_creates_data_dir():
    """The parent directory for the DB is created if missing."""
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()

    mock_stdio = MagicMock()
    mock_stdio.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
    mock_stdio.__aexit__ = AsyncMock(return_value=False)

    tmp_dir = Path("/tmp/mcp_test_data")
    db_path = str(tmp_dir / "projects.db")

    with patch("app.mcp_client.stdio_client", return_value=mock_stdio):
        with patch("app.mcp_client.ClientSession", return_value=mock_session):
            async with sqlite_mcp_session(db_path):
                pass

    assert tmp_dir.exists()
    # Cleanup
    if tmp_dir.exists():
        tmp_dir.rmdir()


@pytest.mark.asyncio
async def test_sqlite_mcp_session_cleanup_on_error():
    """If initialization fails, the context manager still exits cleanly."""
    mock_stdio = MagicMock()
    mock_stdio.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
    mock_stdio.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock(side_effect=RuntimeError("init failed"))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("app.mcp_client.stdio_client", return_value=mock_stdio):
        with patch("app.mcp_client.ClientSession", return_value=mock_session):
            with pytest.raises(RuntimeError, match="init failed"):
                async with sqlite_mcp_session("/tmp/test.db"):
                    pass

    mock_stdio.__aexit__.assert_awaited()
