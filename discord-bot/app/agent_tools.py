"""LangChain tools for the report agent."""

import asyncio
import json
import logging
from datetime import date
from pathlib import Path

from langchain_core.tools import StructuredTool

from app.date_util import gmt7_to_utc_range
from app.discord_util import fetch_messages_in_range, download_message_images
from app.report_extractor import is_valid_report_message, group_messages_by_id
from app.image_metadata_extractor import extract_image_metadata
from app.document_generator import generate_pdf


logger = logging.getLogger(__name__)


async def retrieve_messages(
    discord_start_date: date,
    discord_end_date: date,
    channel,
) -> list[dict]:
    """
    Retrieve Discord messages from a channel within a date range.

    Fetches messages from the given channel within the inclusive date range.
    """
    logger.info("Retrieving messages from %s to %s", discord_start_date, discord_end_date)
    start_utc, end_utc = gmt7_to_utc_range(discord_start_date, discord_end_date)
    raw_messages = await fetch_messages_in_range(channel, start_utc, end_utc)

    messages = []
    for msg in raw_messages:
        messages.append({
            "message_id": msg.id,
            "content": msg.content,
            "timestamp": msg.created_at.isoformat() if msg.created_at else None,
            "author": {
                "id": msg.author.id,
                "username": msg.author.name,
            },
            "attachments": [
                {
                    "id": att.id,
                    "filename": att.filename,
                    "url": att.url,
                    "content_type": att.content_type,
                }
                for att in msg.attachments
            ],
        })

    logger.info("Retrieved %d messages", len(messages))
    return messages


async def process_messages(
    messages: list[dict],
    report_start_date: date,
    report_end_date: date,
    temp_dir: Path,
) -> list[dict]:
    """
    Process Discord messages to extract valid report entries.

    Validates messages have image attachments, downloads images,
    extracts metadata from each image, filters by report date range,
    and returns minimal structured data.
    """
    logger.info("Processing %d messages for report range %s to %s",
                len(messages), report_start_date, report_end_date)

    class MockAttachment:
        def __init__(self, att_dict: dict):
            self.id = att_dict["id"]
            self.filename = att_dict["filename"]
            self.url = att_dict["url"]
            self.content_type = att_dict["content_type"]

    class MockMessage:
        def __init__(self, msg_dict: dict):
            self.id = msg_dict["message_id"]
            self.content = msg_dict["content"]
            self.attachments = [MockAttachment(a) for a in msg_dict.get("attachments", [])]

    valid_entries = []
    for msg_dict in messages:
        mock_msg = MockMessage(msg_dict)

        # 1. Lightweight validation: has images?
        if not is_valid_report_message(mock_msg):
            continue

        # 2. Download all image attachments
        local_images = await download_message_images(mock_msg, temp_dir)

        # 3. Extract metadata from EACH image individually
        for img_path in local_images:
            metadata = await extract_image_metadata(Path(img_path))

            if metadata is None:
                logger.warning(
                    "Image skipped: metadata extraction failed",
                    extra={
                        "message_id": mock_msg.id,
                        "image": img_path,
                    },
                )
                continue

            # 4. Check report date range
            if not (report_start_date <= metadata.report_date <= report_end_date):
                logger.info(
                    "Image skipped: date out of range",
                    extra={
                        "message_id": mock_msg.id,
                        "image": img_path,
                        "extracted_date": metadata.report_date.isoformat(),
                    },
                )
                continue

            # 5. Create one entry per valid image
            valid_entries.append({
                "tower_id": metadata.tower_id,
                "sub_id": metadata.sub_id,
                "report_date": metadata.report_date.isoformat(),
                "message_id": mock_msg.id,
                "images": [img_path],
            })

    logger.info("Found %d valid report entries", len(valid_entries))
    return valid_entries


def generate_pdf_reports(
    processed_data: list[dict],
    temp_dir: Path,
    report_start_date: date,
    report_end_date: date,
) -> list[str]:
    """
    Generate PDF reports from processed message data.

    Groups data by tower_id and sub_id, then generates one PDF per tower_id.
    """
    logger.info("Generating PDFs for %d processed entries", len(processed_data))

    # Group by tower_id -> sub_id -> list of {message_id, images}
    grouped = {}
    for entry in processed_data:
        tower_id = entry["tower_id"]
        sub_id = entry["sub_id"]
        if tower_id not in grouped:
            grouped[tower_id] = {}
        if sub_id not in grouped[tower_id]:
            grouped[tower_id][sub_id] = []
        grouped[tower_id][sub_id].append({
            "message_id": entry["message_id"],
            "images": entry.get("images", []),
        })

    pdf_paths = []
    for tower_id, sub_data in grouped.items():
        output_path = temp_dir / f"report-{tower_id}-{report_start_date}-{report_end_date}.pdf"
        generate_pdf(
            report_id=tower_id,
            start_date=report_start_date,
            end_date=report_end_date,
            grouped_data=sub_data,
            output_path=str(output_path),
        )
        pdf_paths.append(str(output_path))

    logger.info("Generated %d PDFs: %s", len(pdf_paths), pdf_paths)
    return pdf_paths


def create_agent_tools(channel, temp_dir: Path) -> list[StructuredTool]:
    """
    Create LangChain StructuredTool instances bound to request context.

    Parameters
    ----------
    channel : discord.TextChannel
        The Discord channel to fetch messages from.
    temp_dir : Path
        Temporary directory for downloaded images and output PDFs.

    Returns
    -------
    list[StructuredTool]
        List of tools the agent can invoke.
    """
    tools: list[StructuredTool] = []

    async def _parse_dates(user_query: str) -> str:
        """Extract date ranges from a natural language query."""
        from app.nl_date_parser import parse_report_dates
        result = await asyncio.to_thread(parse_report_dates, user_query)
        if result is None:
            return json.dumps({"error": "Failed to parse dates from query"})
        return json.dumps({
            "discord_start_date": result.discord_start_date.isoformat(),
            "discord_end_date": result.discord_end_date.isoformat(),
            "report_start_date": result.report_start_date.isoformat(),
            "report_end_date": result.report_end_date.isoformat(),
            "reasoning": result.reasoning,
        })

    tools.append(StructuredTool.from_function(
        coroutine=_parse_dates,
        name="parse_dates",
        description=(
            "Extract date ranges from a natural language query. "
            "Input: user_query (str). "
            "Output: JSON with discord_start_date, discord_end_date, "
            "report_start_date, report_end_date, and reasoning."
        ),
    ))

    async def _retrieve(discord_start_date: str, discord_end_date: str) -> str:
        """Retrieve Discord messages from the bound channel within a date range."""
        start = date.fromisoformat(discord_start_date)
        end = date.fromisoformat(discord_end_date)
        messages = await retrieve_messages(start, end, channel)
        return json.dumps(messages)

    tools.append(StructuredTool.from_function(
        coroutine=_retrieve,
        name="retrieve_messages",
        description=(
            "Retrieve all Discord messages from a channel within a date range. "
            "Input: discord_start_date (YYYY-MM-DD), discord_end_date (YYYY-MM-DD). "
            "Output: JSON string of message dicts with keys: "
            "message_id, content, timestamp, author, attachments."
        ),
    ))

    async def _process(
        messages_json: str,
        report_start_date: str,
        report_end_date: str,
    ) -> str:
        """Process Discord messages to extract valid report entries."""
        messages = json.loads(messages_json)
        start = date.fromisoformat(report_start_date)
        end = date.fromisoformat(report_end_date)
        entries = await process_messages(messages, start, end, temp_dir)
        return json.dumps(entries)

    tools.append(StructuredTool.from_function(
        coroutine=_process,
        name="process_messages",
        description=(
            "Process Discord messages to extract valid report entries. "
            "Validates messages have image attachments, downloads images, "
            "extracts metadata from each image using Gemini vision, "
            "filters by report date range. "
            "Input: messages_json (str), report_start_date (YYYY-MM-DD), report_end_date (YYYY-MM-DD). "
            "Output: JSON string of list of objects with keys: tower_id, sub_id, report_date."
        ),
    ))

    async def _generate(
        processed_data_json: str,
        report_start_date: str,
        report_end_date: str,
    ) -> str:
        """Generate PDF reports from processed message data."""
        def _sync() -> str:
            data = json.loads(processed_data_json)
            start = date.fromisoformat(report_start_date)
            end = date.fromisoformat(report_end_date)
            paths = generate_pdf_reports(data, temp_dir, start, end)
            return json.dumps(paths)
        return await asyncio.to_thread(_sync)

    tools.append(StructuredTool.from_function(
        coroutine=_generate,
        name="generate_pdf_reports",
        description=(
            "Generate PDF reports from processed message data. "
            "Groups data by tower_id and sub_id, then generates one PDF per tower_id. "
            "Input: processed_data_json (str), report_start_date (YYYY-MM-DD), report_end_date (YYYY-MM-DD). "
            "Output: JSON string of list of generated PDF file paths."
        ),
    ))

    return tools
