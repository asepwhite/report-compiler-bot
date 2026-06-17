"""Report service module: orchestrates fetch, filter, download, group, and PDF generation."""

from datetime import date
from pathlib import Path

from app.date_util import gmt7_to_utc_range
from app.discord_util import fetch_messages_in_range, download_message_images
from app.report_extractor import is_valid_report_message, group_messages_by_id
from app.document_generator import generate_pdf


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
