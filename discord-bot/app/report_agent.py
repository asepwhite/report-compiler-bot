"""Report agent orchestrator: natural language → dates → tools → PDFs."""

import logging
from datetime import date
from pathlib import Path

from langsmith import traceable

from app.nl_date_parser import parse_report_dates, ReportDateRequest
from app.agent_tools import retrieve_messages, process_messages, generate_pdf_reports


logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Base exception for report agent errors."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class DateParseError(AgentError):
    """Failed to parse dates from natural language."""
    pass


class NoMessagesError(AgentError):
    """No Discord messages found in the specified range."""
    pass


class NoValidReportsError(AgentError):
    """No valid report messages found after filtering."""
    pass


@traceable(run_type="chain", name="report_agent_pipeline")
async def run_report_agent(
    channel,
    user_query: str,
    temp_dir: Path,
) -> list[str]:
    """
    Run the full report agent pipeline from natural language to PDFs.

    Parameters
    ----------
    channel : discord.TextChannel
        The Discord channel to fetch messages from.
    user_query : str
        User's natural language request in Indonesian.
    temp_dir : Path
        Temporary directory for downloaded images and output PDFs.

    Returns
    -------
    list[str]
        List of generated PDF file paths.

    Raises
    ------
    DateParseError
        When the LLM fails to extract valid dates.
    NoMessagesError
        When no Discord messages exist in the retrieved range.
    NoValidReportsError
        When no valid report messages are found after filtering.
    """
    logger.info("Starting report agent for query: %s", user_query)

    # Step 1: Parse dates from natural language
    date_request = parse_report_dates(user_query)
    if date_request is None:
        logger.error("Date parsing failed for query: %s", user_query)
        raise DateParseError(
            "Gagal membuat laporan secara otomatis, silakan buat laporan secara manual."
        )

    logger.info("Parsed dates: discord=%s to %s, report=%s to %s",
                date_request.discord_start_date, date_request.discord_end_date,
                date_request.report_start_date, date_request.report_end_date)

    # Step 2: Retrieve messages from Discord
    messages = await retrieve_messages(
        discord_start_date=date_request.discord_start_date,
        discord_end_date=date_request.discord_end_date,
        channel=channel,
    )

    if not messages:
        logger.warning("No messages found in discord range %s to %s",
                       date_request.discord_start_date, date_request.discord_end_date)
        raise NoMessagesError(
            "Tidak ada pesan yang ditemukan di rentang tanggal tersebut."
        )

    # Step 3: Process messages (validate, filter by report date, download images)
    processed_data = await process_messages(
        messages=messages,
        report_start_date=date_request.report_start_date,
        report_end_date=date_request.report_end_date,
        temp_dir=temp_dir,
    )

    if not processed_data:
        logger.warning("No valid report messages after processing %d raw messages", len(messages))
        raise NoValidReportsError(
            "Tidak ada pesan laporan yang valid ditemukan."
        )

    # Step 4: Generate PDF reports
    pdf_paths = generate_pdf_reports(
        processed_data=processed_data,
        temp_dir=temp_dir,
        report_start_date=date_request.report_start_date,
        report_end_date=date_request.report_end_date,
    )

    logger.info("Report agent completed successfully: %d PDFs generated", len(pdf_paths))
    return pdf_paths
