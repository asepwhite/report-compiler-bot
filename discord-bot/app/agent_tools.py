"""LangChain tools for the report agent."""

import asyncio
import json
import logging
import os
import re
from datetime import date
from pathlib import Path

from langchain_core.tools import StructuredTool

from app.date_util import gmt7_to_utc_range
from app.discord_util import fetch_messages_in_range, download_message_images
from app.report_extractor import is_valid_report_message
from app.image_metadata_extractor import extract_image_metadata
from app.document_generator import generate_pdf


logger = logging.getLogger(__name__)

# Configurable concurrency limit for Gemini vision API calls.
_GEMINI_MAX_CONCURRENT = int(os.getenv("GEMINI_MAX_CONCURRENT", "5"))
_GEMINI_SEMAPHORE = asyncio.Semaphore(_GEMINI_MAX_CONCURRENT)
logger.info("Gemini concurrent limit set to %d", _GEMINI_MAX_CONCURRENT)


async def _extract_image_metadata_with_limit(image_path: Path) -> dict | None:
    """Extract image metadata with a concurrency limit on Gemini calls."""
    async with _GEMINI_SEMAPHORE:
        return await extract_image_metadata(image_path)


async def retrieve_messages(
    discord_start_date: date,
    discord_end_date: date,
    channel,
    temp_dir: Path,
) -> dict:
    """
    Retrieve Discord messages from a channel within a date range.

    Fetches messages from the given channel within the inclusive date range,
    strips non-essential fields, writes them to a temporary JSON file,
    and returns the file path and message count.
    """
    logger.info("Retrieving messages from %s to %s", discord_start_date, discord_end_date)
    start_utc, end_utc = gmt7_to_utc_range(discord_start_date, discord_end_date)
    raw_messages = await fetch_messages_in_range(channel, start_utc, end_utc)

    messages = []
    for msg in raw_messages:
        messages.append({
            "message_id": msg.id,
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

    # Write stripped messages to a temporary file
    filename = f"messages_{discord_start_date}_{discord_end_date}.json"
    file_path = temp_dir / filename
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(messages, f)

    logger.info("Wrote %d messages to %s", len(messages), file_path)

    return {
        "file_path": filename,
        "message_count": len(messages),
    }


class _MockAttachment:
    def __init__(self, att_dict: dict):
        self.id = att_dict["id"]
        self.filename = att_dict["filename"]
        self.url = att_dict["url"]
        self.content_type = att_dict["content_type"]


class _MockMessage:
    def __init__(self, msg_dict: dict):
        self.id = msg_dict["message_id"]
        self.content = ""
        self.attachments = [_MockAttachment(a) for a in msg_dict.get("attachments", [])]


async def _process_single_message(
    msg_dict: dict,
    tower_numbers: list[str] | None,
    roadways: list[str] | None,
    temp_dir: Path,
) -> list[dict]:
    """Process a single Discord message: validate, download images, extract metadata, filter."""
    mock_msg = _MockMessage(msg_dict)

    # 1. Lightweight validation: has images?
    if not is_valid_report_message(mock_msg):
        return []

    # 2. Download all image attachments (runs freely, no limit)
    local_images = await download_message_images(mock_msg, temp_dir)

    # 3. Extract metadata from each image in parallel, gated by Gemini semaphore
    metadata_tasks = [
        _extract_image_metadata_with_limit(Path(img_path))
        for img_path in local_images
    ]
    metadatas = await asyncio.gather(*metadata_tasks)

    valid_entries = []
    for img_path, metadata in zip(local_images, metadatas):
        if metadata is None:
            logger.warning(
                "Image skipped: metadata extraction failed",
                extra={
                    "message_id": mock_msg.id,
                    "image": img_path,
                },
            )
            continue

        # 4. Filter by tower numbers
        if tower_numbers and metadata.tower_id not in tower_numbers:
            logger.info(
                "Image skipped: tower_id %s not in requested towers %s",
                metadata.tower_id,
                tower_numbers,
            )
            continue

        # 5. Filter by roadways
        if roadways:
            if metadata.roadway is None:
                logger.info(
                    "Image skipped: no roadway metadata but roadways filter active",
                )
                continue
            if metadata.roadway not in roadways:
                logger.info(
                    "Image skipped: roadway %s not in requested roadways %s",
                    metadata.roadway,
                    roadways,
                )
                continue

        # 6. Create one entry per valid image
        valid_entries.append({
            "tower_id": metadata.tower_id,
            "sub_id": metadata.sub_id,
            "report_date": metadata.report_date.isoformat(),
            "roadway": metadata.roadway,
            "message_id": mock_msg.id,
            "images": [img_path],
        })

    return valid_entries


async def process_and_filter_messages(
    file_paths_json: str,
    tower_numbers: list[str] | None,
    roadways: list[str] | None,
    temp_dir: Path,
) -> list[dict]:
    """
    Process Discord messages from file paths to extract valid report entries.

    Reads messages from the provided JSON file paths, combines them,
    processes in batches of 50 messages, downloads images,
    extracts metadata from each image (with configurable concurrency limit),
    filters by tower number and roadway, and returns structured data.
    """
    file_paths = json.loads(file_paths_json)
    if not isinstance(file_paths, list):
        raise ValueError("file_paths_json must be a JSON list of file paths")

    # Read all messages from files
    all_messages = []
    for filename in file_paths:
        file_path = temp_dir / filename
        if not file_path.exists():
            logger.warning("Message file not found, skipping: %s", file_path)
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                messages = json.load(f)
                if isinstance(messages, list):
                    all_messages.extend(messages)
                else:
                    logger.warning("Invalid message data in file %s (expected list)", file_path)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in file %s, skipping", file_path)
        except Exception:
            logger.exception("Failed to read message file %s", file_path)

    logger.info(
        "Processing %d total messages from %d files with tower_numbers=%s, roadways=%s",
        len(all_messages), len(file_paths), tower_numbers, roadways,
    )

    if not all_messages:
        logger.info("No messages to process")
        return []

    # Process all messages concurrently (Gemini semaphore throttles API calls)
    total_messages = len(all_messages)
    message_tasks = [
        _process_single_message(msg_dict, tower_numbers, roadways, temp_dir)
        for msg_dict in all_messages
    ]
    results = await asyncio.gather(*message_tasks)

    # Flatten results
    all_valid_entries = []
    for entries in results:
        all_valid_entries.extend(entries)

    logger.info(
        "Found %d valid report entries from %d messages",
        len(all_valid_entries),
        total_messages,
    )
    return all_valid_entries


def _slugify(value: str | None) -> str:
    """Create a filesystem-safe slug from a string."""
    if not value:
        return ""
    slug = value.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug


def generate_pdf_reports(
    processed_data: list[dict],
    temp_dir: Path,
) -> list[str]:
    """
    Generate PDF reports from processed message data.

    Groups data by report_date, tower_id, and roadway, then generates one PDF per group.
    """
    logger.info("Generating PDFs for %d processed entries", len(processed_data))

    # Group by (report_date, tower_id, roadway) -> sub_id -> list of {message_id, images}
    grouped: dict[tuple[date, str, str | None], dict] = {}
    for entry in processed_data:
        report_date = date.fromisoformat(entry["report_date"])
        tower_id = entry["tower_id"]
        roadway = entry.get("roadway")
        sub_id = entry["sub_id"]
        key = (report_date, tower_id, roadway)
        if key not in grouped:
            grouped[key] = {}
        if sub_id not in grouped[key]:
            grouped[key][sub_id] = []
        grouped[key][sub_id].append({
            "message_id": entry["message_id"],
            "images": entry.get("images", []),
        })

    pdf_paths = []
    for (report_date, tower_id, roadway), sub_data in grouped.items():
        tower_slug = _slugify(tower_id)
        roadway_slug = _slugify(roadway)
        if roadway_slug:
            filename = f"report-{tower_slug}-{roadway_slug}-{report_date}.pdf"
        else:
            filename = f"report-{tower_slug}-{report_date}.pdf"
        output_path = temp_dir / filename

        generate_pdf(
            report_id=tower_id,
            report_date=report_date,
            roadway=roadway,
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

    async def _parse_query(user_query: str) -> str:
        """Extract report query parameters from a natural language query."""
        from app.report_query_parser import parse_report_query
        result = await asyncio.to_thread(parse_report_query, user_query)
        if result is None:
            return json.dumps({"error": "Failed to parse query"})

        date_ranges_json = [
            {"start": start.isoformat(), "end": end.isoformat()}
            for start, end in result.discord_date_ranges
        ]
        return json.dumps({
            "tower_numbers": result.tower_numbers,
            "discord_date_ranges": date_ranges_json,
            "roadways": result.roadways,
            "reasoning": result.reasoning,
        })

    tools.append(StructuredTool.from_function(
        coroutine=_parse_query,
        name="parse_report_query",
        description=(
            "Extract report query parameters from a natural language query. "
            "Input: user_query (str). "
            "Output: JSON with tower_numbers (list[str]|null), "
            "discord_date_ranges (list of {start, end}), "
            "roadways (list[str]|null), and reasoning."
        ),
    ))

    async def _retrieve(discord_start_date: str, discord_end_date: str) -> str:
        """Retrieve Discord messages from the bound channel within a date range."""
        start = date.fromisoformat(discord_start_date)
        end = date.fromisoformat(discord_end_date)
        result = await retrieve_messages(start, end, channel, temp_dir)
        return json.dumps(result)

    tools.append(StructuredTool.from_function(
        coroutine=_retrieve,
        name="retrieve_messages",
        description=(
            "Retrieve all Discord messages from a channel within a date range. "
            "Writes stripped messages to a temporary file and returns "
            "{file_path: str, message_count: int}. "
            "Input: discord_start_date (YYYY-MM-DD), discord_end_date (YYYY-MM-DD). "
            "Output: JSON with file_path and message_count."
        ),
    ))

    async def _process(
        file_paths_json: str,
        tower_numbers_json: str,
        roadways_json: str,
    ) -> str:
        """Process Discord messages from file paths to extract valid report entries."""
        tower_numbers = json.loads(tower_numbers_json) if tower_numbers_json else None
        roadways = json.loads(roadways_json) if roadways_json else None
        entries = await process_and_filter_messages(
            file_paths_json, tower_numbers, roadways, temp_dir
        )
        return json.dumps(entries)

    tools.append(StructuredTool.from_function(
        coroutine=_process,
        name="process_and_filter_messages",
        description=(
            "Process Discord messages to extract valid report entries. "
            "Reads messages from JSON file paths, validates images, downloads images, "
            "extracts metadata from each image using Gemini vision (concurrent, "
            "rate-limited by GEMINI_MAX_CONCURRENT env var), "
            "filters by tower number and roadway. "
            "Input: file_paths_json (JSON string of list of file path strings), "
            "tower_numbers_json (JSON string of list[str] or 'null'), "
            "roadways_json (JSON string of list[str] or 'null'). "
            "Output: JSON string of list of objects with keys: "
            "tower_id, sub_id, report_date, roadway, images."
        ),
    ))

    async def _generate(processed_data_json: str) -> str:
        """Generate PDF reports from processed message data."""
        def _sync() -> str:
            data = json.loads(processed_data_json)
            paths = generate_pdf_reports(data, temp_dir)
            return json.dumps(paths)
        return await asyncio.to_thread(_sync)

    tools.append(StructuredTool.from_function(
        coroutine=_generate,
        name="generate_pdf_reports",
        description=(
            "Generate PDF reports from processed message data. "
            "Groups data by report_date, tower_id, and roadway, "
            "then generates one PDF per group. "
            "Input: processed_data_json (str). "
            "Output: JSON string of list of generated PDF file paths."
        ),
    ))

    return tools
