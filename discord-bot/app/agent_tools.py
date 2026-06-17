"""LangChain tools for the report agent."""

import json
import logging
from datetime import date
from pathlib import Path

from langchain.tools import tool

from app.date_util import gmt7_to_utc_range
from app.discord_util import fetch_messages_in_range, download_message_images
from app.report_extractor import is_valid_report_message, group_messages_by_id
from app.document_generator import generate_pdf


logger = logging.getLogger(__name__)


@tool
def retrieve_messages_tool(
    discord_start_date: str,
    discord_end_date: str,
    channel,
) -> str:
    """
    Retrieve all Discord messages from a channel within a date range.

    Parameters
    ----------
    discord_start_date : str
        Start date in ISO format (YYYY-MM-DD), inclusive.
    discord_end_date : str
        End date in ISO format (YYYY-MM-DD), inclusive.
    channel : discord.TextChannel
        The Discord channel to fetch messages from.

    Returns
    -------
    str
        JSON string containing a list of message dicts with keys:
        message_id, content, timestamp, author, attachments.
    """
    raise NotImplementedError("This tool must be called via its async counterpart.")


async def retrieve_messages(
    discord_start_date: date,
    discord_end_date: date,
    channel,
) -> list[dict]:
    """
    Async implementation of retrieve_messages_tool.

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


@tool
def process_messages_tool(
    messages_json: str,
    report_start_date: str,
    report_end_date: str,
    temp_dir_path: str,
) -> str:
    """
    Process Discord messages to extract valid report entries.

    Filters messages by report date range, validates report format,
    downloads images, and returns structured data.

    Parameters
    ----------
    messages_json : str
        JSON string of Discord messages (output from retrieve_messages_tool).
    report_start_date : str
        Report start date in ISO format (YYYY-MM-DD), inclusive.
    report_end_date : str
        Report end date in ISO format (YYYY-MM-DD), inclusive.
    temp_dir_path : str
        Path to temporary directory for downloading images.

    Returns
    -------
    str
        JSON string of list of objects with keys: tower_id, sub_id, report_date.
    """
    raise NotImplementedError("This tool must be called via its async counterpart.")


async def process_messages(
    messages: list[dict],
    report_start_date: date,
    report_end_date: date,
    temp_dir: Path,
) -> list[dict]:
    """
    Async implementation of process_messages_tool.

    Validates messages, filters by report date range, downloads images,
    and returns minimal structured data.
    """
    logger.info("Processing %d messages for report range %s to %s",
                len(messages), report_start_date, report_end_date)

    # We need to reconstruct mock-like message objects for the existing functions
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
        parsed = is_valid_report_message(mock_msg, report_start_date, report_end_date)
        if parsed:
            local_images = await download_message_images(mock_msg, temp_dir)
            valid_entries.append({
                "tower_id": parsed["id"],
                "sub_id": parsed["sub_id"],
                "report_date": parsed["tanggal"].isoformat(),
                "message_id": mock_msg.id,
                "images": local_images,
            })

    logger.info("Found %d valid report entries", len(valid_entries))
    return valid_entries


@tool
def generate_pdf_reports_tool(
    processed_data_json: str,
    temp_dir_path: str,
    report_start_date: str,
    report_end_date: str,
) -> str:
    """
    Generate PDF reports from processed message data.

    Parameters
    ----------
    processed_data_json : str
        JSON string of processed data (output from process_messages_tool).
    temp_dir_path : str
        Path to temporary directory for output PDFs.
    report_start_date : str
        Report start date in ISO format (YYYY-MM-DD), for PDF title.
    report_end_date : str
        Report end date in ISO format (YYYY-MM-DD), for PDF title.

    Returns
    -------
    str
        JSON string of list of generated PDF file paths.
    """
    raise NotImplementedError("This tool must be called via its sync counterpart.")


def generate_pdf_reports(
    processed_data: list[dict],
    temp_dir: Path,
    report_start_date: date,
    report_end_date: date,
) -> list[str]:
    """
    Sync implementation of generate_pdf_reports_tool.

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
