"""Project agent orchestrator: natural language → ReAct agent → SQLite CRUD."""

import json
import logging
from typing import Any

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import create_react_agent

from app.llm import create_llm
from app.mcp_client import sqlite_mcp_session
from app.project_tools import create_project_tools

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Kamu adalah asisten manajemen data proyek untuk bot Discord.
Kamu berbahasa Indonesia (Bahasa Indonesia).

TABEL DATABASE:
Tabel `project_details` memiliki kolom:
- tower_id (TEXT, bagian dari PRIMARY KEY)
- roadway (TEXT, bagian dari PRIMARY KEY)
- tower_type (TEXT)
- region (TEXT)
- project_name (TEXT)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

Catatan: Daftar kolom di atas mungkin tidak selalu mutakhir.
Saat ragu tentang struktur tabel, panggil tool `describe_table`
untuk mendapatkan daftar kolom terbaru sebelum menjalankan query.

Aturan penting:
1. Kombinasi (tower_id, roadway) adalah unik.
2. Saat UPDATE atau DELETE, SELALU gunakan BOTH tower_id AND roadway di WHERE clause.
3. Jika user menyebut hanya tower_id dan ada banyak roadway, tanyakan:
   "Ada X project dengan tower T123. Pilih roadway mana?"
4. Saat CREATE, periksa dulu apakah sudah ada dengan SELECT.
5. Saat user meminta "tarik/tampilkan semua data", gunakan `SELECT *`
   agar semua kolom (termasuk project_name) ikut ditampilkan,
   dan tampilkan semua kolom dalam tabel hasil.
6. Jelaskan hasil dalam bahasa Indonesia yang ramah dan singkat.

Tools yang tersedia:
- read_query: untuk SELECT
- write_query: untuk INSERT, UPDATE, DELETE
- create_table: untuk CREATE TABLE (jika tabel belum ada)
- list_tables: untuk melihat tabel yang ada
- describe_table: untuk melihat struktur tabel
"""


def _extract_text(content: Any) -> str:
    """Normalize LLM message content to a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict):
                texts.append(block.get("text", ""))
            elif isinstance(block, str):
                texts.append(block)
        return " ".join(t for t in texts if t)
    return str(content) if content is not None else ""


def _had_tool_calls(messages: list) -> bool:
    """Check whether any ToolMessage appears in the agent message history."""
    for m in messages:
        if isinstance(m, ToolMessage):
            return True
        if getattr(m, "type", None) == "tool":
            return True
    return False


async def run_project_agent(user_query: str) -> dict:
    """
    Run the project CRUD agent using a LangGraph ReAct agent backed by MCP SQLite.

    Parameters
    ----------
    user_query : str
        User's natural language request (in Indonesian).

    Returns
    -------
    dict
        One of:
        - {"type": "success", "message": "..."}
        - {"type": "error", "message": "..."}
    """
    logger.info("Starting project agent for query: %s", user_query)

    try:
        async with sqlite_mcp_session() as session:
            model = create_llm()
            tools = await create_project_tools(session)
            agent = create_react_agent(model, tools, prompt=_SYSTEM_PROMPT)

            result = await agent.ainvoke({"messages": [("user", user_query)]})
            all_messages = result.get("messages", [])
            final_message = all_messages[-1]
            content = _extract_text(final_message.content)

            logger.info("Project agent final response: %s", content)

            if not _had_tool_calls(all_messages):
                # No tool calls → likely a greeting or unclear request
                return {
                    "type": "success",
                    "message": content or "Silakan sebutkan perintah CRUD yang Anda maksud.",
                }

            return {"type": "success", "message": content}

    except Exception as e:
        logger.exception("Project agent failed: %s", e)
        return {
            "type": "error",
            "message": "Gagal memproses permintaan. Silakan coba lagi nanti.",
        }
