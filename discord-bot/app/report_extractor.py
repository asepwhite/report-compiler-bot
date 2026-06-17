"""Report extractor module for validating, parsing, and grouping Discord report messages."""

import re
from datetime import date


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
