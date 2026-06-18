"""Report service module: orchestrates fetch, filter, download, extract, group, and PDF generation."""

from datetime import date
from pathlib import Path

from app.date_util import gmt7_to_utc_range
from app.discord_util import fetch_messages_in_range, download_message_images
from app.report_extractor import is_valid_report_message, group_messages_by_id
from app.image_metadata_extractor import extract_image_metadata
from app.document_generator import generate_pdf


async def compile_report(channel, start_date: date, end_date: date, temp_dir: Path) -> list[str]:
    """
    Compile report PDFs for a given date range from a Discord channel.

    Parameters
    ----------
    channel : discord.TextChannel
        The channel to scan.
    start_date, end_date : date
        Inclusive report date range in GMT+7.
    temp_dir : Path
        Temporary directory for downloaded images.

    Returns
    -------
    list[str]
        List of generated PDF file paths.
    """
    # 1. Convert to UTC range for Discord fetch
    start_utc, end_utc = gmt7_to_utc_range(start_date, end_date)

    # 2. Fetch messages
    messages = await fetch_messages_in_range(channel, start_utc, end_utc)

    # 3. Filter valid report messages (has images) and extract metadata per image
    valid_entries = []
    for msg in messages:
        if not is_valid_report_message(msg):
            continue

        # Download images for this message
        local_images = await download_message_images(msg, temp_dir)

        # Extract metadata from each image individually
        for img_path in local_images:
            metadata = await extract_image_metadata(Path(img_path))

            if metadata is None:
                continue

            # Filter by report date range
            if not (start_date <= metadata.report_date <= end_date):
                continue

            valid_entries.append({
                "id": metadata.tower_id,
                "sub_id": metadata.sub_id,
                "tanggal": metadata.report_date,
                "message_id": msg.id,
                "local_images": [img_path],
            })

    if not valid_entries:
        return []

    # 4. Group by id -> sub-id
    grouped_by_id = group_messages_by_id(valid_entries)

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
