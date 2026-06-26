"""MCP client wrapper for SQLite server."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = "./data/projects.db"


def get_project_db_path() -> str:
    """Return the SQLite database path from env or default."""
    return os.getenv("PROJECT_DB_PATH", _DEFAULT_DB_PATH)


@asynccontextmanager
async def sqlite_mcp_session(db_path: str | None = None):
    """
    Async context manager that spawns mcp-server-sqlite via stdio,
    initializes the session, and yields a ClientSession.

    The parent directory for the DB file is created automatically.
    Uses the installed `mcp-server-sqlite` CLI command.
    """
    path = db_path or get_project_db_path()
    db_file = Path(path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    server_params = StdioServerParameters(
        command="mcp-server-sqlite",
        args=["--db-path", str(db_file.absolute())],
    )

    logger.info("Starting MCP SQLite server for db: %s", db_file)
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            logger.info("MCP SQLite session initialized")
            yield session
