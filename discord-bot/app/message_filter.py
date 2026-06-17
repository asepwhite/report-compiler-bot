"""Message filter module for validating and fetching Discord messages."""

from datetime import date, datetime, timedelta

from app.parser import parse_report_message


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


def is_valid_report_message(message, start_date: date, end_date: date) -> dict | None:
    """
    Check if a Discord message qualifies as a valid report message.

    Criteria:
      1. Has at least one image attachment.
      2. Content can be parsed by parse_report_message.
      3. The parsed 'tanggal' is within [start_date, end_date].

    Returns the parsed dict or None.
    """
    # Check for image attachments
    has_image = any(
        att.content_type and att.content_type.startswith("image/")
        for att in message.attachments
    )
    if not has_image:
        return None

    # Parse report content
    parsed = parse_report_message(message.content)
    if not parsed:
        return None

    # Check tanggal range
    if not (start_date <= parsed["tanggal"] <= end_date):
        return None

    return parsed
