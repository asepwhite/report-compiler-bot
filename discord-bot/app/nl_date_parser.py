"""Natural language date parser using Gemini for Indonesian queries."""

import logging
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.llm import create_llm


logger = logging.getLogger(__name__)


class ReportDateRequest(BaseModel):
    """Structured date request extracted from natural language."""

    discord_start_date: date = Field(
        description="Tanggal awal untuk mengambil pesan Discord (inclusive)."
    )
    discord_end_date: date = Field(
        description="Tanggal akhir untuk mengambil pesan Discord (inclusive)."
    )
    report_start_date: date = Field(
        description="Tanggal awal laporan yang diminta (inclusive)."
    )
    report_end_date: date = Field(
        description="Tanggal akhir laporan yang diminta (inclusive)."
    )
    reasoning: str = Field(
        description="Penjelasan singkat mengapa tanggal-tanggal ini dipilih."
    )


_DATE_PARSER_PROMPT = """Kamu adalah asisten pintar yang tugasnya mengekstrak tanggal dari permintaan pembuatan laporan dalam bahasa Indonesia.

Tanggal hari ini: {today}

Peraturan:
1. Jika pengguna tidak menyebutkan rentang tanggal pesan Discord secara eksplisit, maka discord_start_date dan discord_end_date SAMA dengan report_start_date dan report_end_date.
2. Jika pengguna menyebutkan rentang tanggal pesan Discord yang berbeda dari tanggal laporan, gunakan rentang tersebut untuk discord_start_date dan discord_end_date.
3. Tanggal laporan (report_start_date, report_end_date) adalah tanggal yang pengguna minta untuk dibuatkan laporannya.
4. Tanggal dalam format ISO: YYYY-MM-DD.

Contoh:
- "tolong bikin report untuk tanggal 11 juni 2026" → discord: 2026-06-11 s/d 2026-06-11, report: 2026-06-11 s/d 2026-06-11
- "tolong bikinin report untuk tanggal 10 juni 2026 dari message discord di tanggal 10 - 11 juni 2026" → discord: 2026-06-10 s/d 2026-06-11, report: 2026-06-10 s/d 2026-06-10
- "kemarin" → gunakan tanggal kemarin dari hari ini
- "minggu ini" → gunakan rentang Senin s/d Minggu minggu ini
- "bulan lalu" → gunakan rentang tanggal 1 s/d akhir bulan lalu

Permintaan pengguna: {query}
"""


def parse_report_dates(user_query: str) -> ReportDateRequest | None:
    """
    Extract report and Discord date ranges from an Indonesian natural language query.

    Parameters
    ----------
    user_query : str
        The user's message text (e.g. "tolong bikin report untuk tanggal 11 juni 2026").

    Returns
    -------
    ReportDateRequest | None
        The parsed date request, or None if parsing fails.
    """
    try:
        llm = create_llm()
        structured_llm = llm.with_structured_output(ReportDateRequest)

        today = datetime.now().strftime("%Y-%m-%d (%A)")
        prompt = _DATE_PARSER_PROMPT.format(today=today, query=user_query)

        result = structured_llm.invoke(prompt)
        logger.info("Date parsing successful: discord=%s to %s, report=%s to %s",
                    result.discord_start_date, result.discord_end_date,
                    result.report_start_date, result.report_end_date)
        return result
    except Exception as e:
        logger.exception("Date parsing failed for query: %s", user_query)
        return None
