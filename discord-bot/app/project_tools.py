"""Project tools loader from MCP SQLite server."""

import logging

from langchain_mcp_adapters.tools import load_mcp_tools

logger = logging.getLogger(__name__)


async def create_project_tools(session) -> list:
    """
    Load LangChain tools from an active MCP SQLite session.

    Parameters
    ----------
    session : mcp.ClientSession
        An initialized MCP client session connected to mcp-server-sqlite.

    Returns
    -------
    list[StructuredTool]
        List of LangChain tools (read_query, write_query, create_table,
        list_tables, describe_table, append_insight).
    """
    tools = await load_mcp_tools(session)
    logger.info("Loaded %d MCP tools from SQLite server", len(tools))
    return tools
