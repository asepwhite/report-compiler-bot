"""Report service module: orchestrates fetch, filter, download, group, and PDF generation."""

import asyncio
from datetime import date
from pathlib import Path

import aiohttp

from app.parser import gmt7_to_utc_range
from app.message_filter import fetch_messages_in_range, is_valid_report_message
from app.pdf_generator import generate_pdf


async def compile_report(channel, start_date: date, end_date: date, temp_dir: Path) -> list[str]:
    """
    Compile report PDFs for a given date range from a Discord channel.

    Parameters
    ----------
    channel : discord.TextChannel
        The channel to scan.
    start_date, end_date : date
        Inclusive date range in GMT+7.
    temp_dir : Path
        Temporary directory for downloaded images.

    Returns
    -------
    list[str]
        List of generated PDF file paths.
    """
    # 1. Convert to UTC range
    start_utc, end_utc = gmt7_to_utc_range(start_date, end_date)

    # 2. Fetch messages
    messages = await fetch_messages_in_range(channel, start_utc, end_utc)

    # 3. Filter valid report messages and download images
    valid_messages = []
    for msg in messages:
        parsed = is_valid_report_message(msg, start_date, end_date)
        if parsed:
            # Download images for this message
            local_images = await download_message_images(msg, temp_dir)
            parsed["local_images"] = local_images
            parsed["message_id"] = msg.id
            valid_messages.append(parsed)

    if not valid_messages:
        return []

    # 4. Group by id -> sub-id
    grouped_by_id = group_messages_by_id(valid_messages)

    # 5. Generate PDFs
    pdf_paths = []
    for report_id, grouped_by_sub_id in grouped_by_id.items():
        output_path = temp_dir / f"report-{report_id}-{start_date}-{end_date}.pdf"
        generate_pdf(
            report_id=report_id,
            start_date=start_date,
            end_date=end_date,
            grouped_data=grouped_by_sub_id,
            output_path=str(output_path),
        )
        pdf_paths.append(str(output_path))

    return pdf_paths


def group_messages_by_id(valid_messages: list[dict]) -> dict:
    """
    Group valid messages by tower id, then by sub-id.

    Returns
    -------
    dict
        {id: {sub_id: [{"message_id": ..., "images": [local_path, ...]}]}}
    """
    grouped = {}
    for parsed in valid_messages:
        report_id = parsed["id"]
        sub_id = parsed["sub_id"]
        if report_id not in grouped:
            grouped[report_id] = {}
        if sub_id not in grouped[report_id]:
            grouped[report_id][sub_id] = []
        grouped[report_id][sub_id].append({
            "message_id": parsed["message_id"],
            "images": parsed.get("local_images", []),
        })
    return grouped


async def download_message_images(message, temp_dir: Path) -> list[str]:
    """
    Download all image attachments from a Discord message.

    Returns
    -------
    list[str]
        List of local file paths for downloaded images.
    """
    image_attachments = [
        att for att in message.attachments
        if att.content_type and att.content_type.startswith("image/")
    ]

    if not image_attachments:
        return []

    local_paths = []
    async with aiohttp.ClientSession() as session:
        for att in image_attachments:
            try:
                local_path = await _download_image(session, att.url, att.filename, temp_dir)
                local_paths.append(local_path)
            except Exception:
                # Skip failed downloads
                pass

    return local_paths


async def _download_image(session, url: str, filename: str, temp_dir: Path) -> str:
    """Download a single image from a URL."""
    local_path = temp_dir / filename
    async with session.get(url) as response:
        response.raise_for_status()
        content = await response.read()
        with open(local_path, "wb") as f:
            f.write(content)
    return str(local_path)
