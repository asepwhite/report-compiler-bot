"""Discord utility module for parsing commands, fetching messages, and downloading images."""

import re
from datetime import date, datetime, timedelta
from pathlib import Path

import aiohttp


def _strip_mention(text: str) -> str:
    """Remove Discord user mention patterns from the text."""
    # Matches <@123456789> and <@!123456789>
    return re.sub(r"<@!?\d+>", "", text).strip()


def parse_compile_command(content: str) -> tuple[date, date] | None:
    """
    Extract start and end dates from a compile command.

    Expected format: '@bot compile yyyy-mm-dd yyyy-mm-dd'
    Returns (start_date, end_date) or None if invalid.
    """
    text = _strip_mention(content)
    # Match: compile YYYY-MM-DD YYYY-MM-DD
    pattern = re.compile(
        r"^compile\s+(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})$",
        re.IGNORECASE,
    )
    match = pattern.match(text)
    if not match:
        return None

    try:
        start = date.fromisoformat(match.group(1))
        end = date.fromisoformat(match.group(2))
    except ValueError:
        return None

    if start > end:
        return None

    return start, end


async def fetch_messages_in_range(channel, start_utc: datetime, end_utc: datetime):
    """
    Fetch all messages from a channel within the given UTC datetime range.

    Uses channel.history() with after/before parameters. Note that discord.py
    treats 'after' as exclusive for exact datetimes, so we subtract a small
    buffer and filter manually to ensure inclusivity.
    """
    # discord.py history() treats after as exclusive, so use a small buffer
    buffer = timedelta(seconds=1)
    after = start_utc - buffer
    before = end_utc + buffer

    messages = []
    async for msg in channel.history(limit=None, after=after, before=before):
        if msg.created_at < start_utc or msg.created_at > end_utc:
            continue
        messages.append(msg)

    return messages


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
