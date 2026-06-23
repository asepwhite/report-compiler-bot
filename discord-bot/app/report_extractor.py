"""Report extractor module for validating and grouping Discord report messages."""


def is_valid_report_message(message) -> bool:
    """
    Check if a Discord message qualifies as a valid report message.

    A message is valid if it contains at least one image attachment.
    Text content is no longer required; metadata is extracted from images.

    Parameters
    ----------
    message
        A Discord message-like object with an ``attachments`` attribute.

    Returns
    -------
    bool
        True if the message has at least one image attachment, False otherwise.
    """
    return any(
        att.content_type and att.content_type.startswith("image/")
        for att in message.attachments
    )


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
