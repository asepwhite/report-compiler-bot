"""Report agent orchestrator: natural language → ReAct agent → PDFs."""

import json
import logging
import re
from pathlib import Path
from typing import Callable

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import create_react_agent

from app.agent_tools import create_agent_tools
from app.intent_classifier import classify_intent
from app.llm import create_llm


logger = logging.getLogger(__name__)

_OFF_TOPIC_REFUSAL = (
    "Maaf, saya hanya bisa membantu dengan pembuatan laporan. "
    "Ada yang bisa saya bantu terkait laporan?"
)


_SYSTEM_PROMPT = """\
You are a helpful report-generation assistant for a Discord bot.
You speak Indonesian (Bahasa Indonesia) to users.

GREETINGS AND SMALL TALK:
If the user greets you (e.g. 'selamat sore', 'halo', 'hi') or says thanks,
respond politely in Indonesian WITHOUT calling any tools.
Examples:
- 'selamat sore' → 'Selamat sore! Ada yang bisa saya bantu?'
- 'terima kasih' → 'Sama-sama! Senang bisa membantu.'

REPORT GENERATION:
When the user asks for a report, use the available tools in order:
1. parse_report_query – extracts tower numbers, Discord date ranges, and roadways.
2. retrieve_messages – fetches Discord messages for each date range and writes them to a temporary file.
   Returns {file_path: str, message_count: int}. Store the file_path for the next step.
   Call this tool once for EACH date range returned by parse_report_query.
   Collect all file_paths into a JSON list.
3. process_and_filter_messages – takes a JSON list of file paths, reads the messages in batches,
   downloads images, extracts metadata with Gemini vision, and filters by tower number and roadway.
4. generate_pdf_reports – creates PDF files grouped by report_date, tower_id, and roadway.

When report generation finishes, return the final result as a JSON array
of PDF file paths, e.g. ["/tmp/report-tower-123-jalur-purwakarta-banyuwangi-2024-01-01.pdf"].

If no PDFs could be generated, explain why in Indonesian.
"""


def _extract_text(content) -> str:
    """
    Normalize LLM message content to a plain string.

    Handles Gemini/LangGraph output formats:
    - str → returned as-is
    - list[dict] with 'text' keys → joined
    - list[str] → joined
    - empty / unknown → empty string
    """
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


def _extract_pdf_paths(text: str) -> list[str] | None:
    """Try to extract PDF file paths from agent final text."""
    # 1. Try full JSON parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ("pdf_paths", "paths", "pdfs", "files"):
                if key in parsed and isinstance(parsed[key], list):
                    return parsed[key]
    except json.JSONDecodeError:
        pass

    # 2. Heuristic: look for path-like strings
    path_pattern = re.compile(r'(["\'])(/[^"\']+\.pdf)\1')
    matches = path_pattern.findall(text)
    if matches:
        return [m[1] for m in matches]

    return None


def _had_tool_calls(messages) -> bool:
    """Check whether any ToolMessage appears in the agent message history."""
    for m in messages:
        if isinstance(m, ToolMessage):
            return True
        # Fallback for mocked messages or non-standard message types
        if getattr(m, "type", None) == "tool":
            return True
    return False


async def run_report_agent(
    channel,
    user_query: str,
    temp_dir: Path,
    send_ack: Callable | None = None,
) -> dict:
    """
    Run the full report agent using a LangGraph ReAct agent.

    Parameters
    ----------
    channel : discord.TextChannel
        The Discord channel to fetch messages from.
    user_query : str
        User's natural language request.
    temp_dir : Path
        Temporary directory for downloaded images and output PDFs.
    send_ack : callable | None
        Optional async callback to send an ACK message to the user
        right after intent classification confirms a report request.

    Returns
    -------
    dict
        One of:
        - {"type": "off_topic", "message": "..."}
        - {"type": "greeting", "message": "..."}
        - {"type": "report",   "pdf_paths": [...]}
        - {"type": "error",    "message": "..."}
    """
    logger.info("Starting report agent for query: %s", user_query)

    # ── Guardrail: model-based intent classification ──
    intent_result = classify_intent(user_query)
    if intent_result.intent == "off_topic":
        logger.info("Guardrail blocked off-topic query (confidence=%.2f)", intent_result.confidence)
        return {"type": "off_topic", "message": _OFF_TOPIC_REFUSAL}

    # Send ACK immediately for report requests
    if intent_result.intent == "report_request" and send_ack is not None:
        try:
            await send_ack()
            logger.info("ACK sent to user")
        except Exception:
            logger.exception("Failed to send ACK message")

    model = create_llm()
    tools = create_agent_tools(channel, temp_dir)
    agent = create_react_agent(model, tools, prompt=_SYSTEM_PROMPT)

    result = await agent.ainvoke({"messages": [("user", user_query)]})
    all_messages = result.get("messages", [])
    final_message = all_messages[-1]
    content = _extract_text(final_message.content)

    logger.info("Agent final response: %s", content)

    # No tool calls → greeting / small talk
    if not _had_tool_calls(all_messages):
        return {"type": "greeting", "message": content}

    # Tool calls happened → try to extract PDF paths
    pdf_paths = _extract_pdf_paths(content)
    if pdf_paths:
        return {"type": "report", "pdf_paths": pdf_paths}

    # Tool calls but no PDFs → error explanation
    return {"type": "error", "message": content or "Gagal membuat laporan secara otomatis, silakan buat laporan secara manual."}
