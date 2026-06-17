"""Parser module for extracting dates and report metadata from Discord messages."""

import re
from datetime import date, datetime, timedelta, timezone


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


def parse_report_message(content: str) -> dict | None:
    """
    Extract id, sub-id, and tanggal from a report message.

    Expected format:
      id: {tower-id}
      sub-id: {tower-section}
      tanggal: {yyyy-mm-dd}

    Returns {"id": str, "sub_id": str, "tanggal": date} or None.
    """
    # id: value
    id_match = re.search(r"^id\s*:\s*(.+)$", content, re.MULTILINE)
    if not id_match:
        return None

    # sub-id: value
    sub_id_match = re.search(r"^sub-id\s*:\s*(.+)$", content, re.MULTILINE)
    if not sub_id_match:
        return None

    # tanggal: yyyy-mm-dd
    tanggal_match = re.search(r"^tanggal\s*:\s*(\d{4}-\d{2}-\d{2})$", content, re.MULTILINE)
    if not tanggal_match:
        return None

    try:
        tanggal = date.fromisoformat(tanggal_match.group(1))
    except ValueError:
        return None

    return {
        "id": id_match.group(1).strip(),
        "sub_id": sub_id_match.group(1).strip(),
        "tanggal": tanggal,
    }


def gmt7_to_utc_range(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    """
    Convert an inclusive GMT+7 date range to UTC datetime boundaries.

    Returns (utc_start, utc_end) where:
      - utc_start = start_date 00:00:00 GMT+7
      - utc_end   = end_date   23:59:59 GMT+7
    """
    # GMT+7 is UTC+7. So 00:00 GMT+7 = 17:00 UTC (previous day)
    # 23:59:59 GMT+7 = 16:59:59 UTC (same day)
    start_naive = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
    end_naive = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)

    utc_start = (start_naive - timedelta(hours=7)).replace(tzinfo=timezone.utc)
    utc_end = (end_naive - timedelta(hours=7)).replace(tzinfo=timezone.utc)

    return utc_start, utc_end
