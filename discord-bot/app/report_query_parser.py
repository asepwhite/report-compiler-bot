"""Natural language report query parser using Gemini for Indonesian queries."""

import logging
import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.llm import create_llm


logger = logging.getLogger(__name__)


class ReportQueryRequest(BaseModel):
    """Structured query extracted from natural language."""

    tower_numbers: list[str] | None = Field(
        description="Daftar nomor tower yang dinormalisasi ke 'Tower {number}'. Kosong jika tidak disebutkan."
    )
    discord_date_ranges: list[tuple[date, date]] = Field(
        description="Daftar rentang tanggal Discord (start, end) dalam format ISO. Jika tidak disebutkan, gunakan hari ini."
    )
    roadways: list[str] | None = Field(
        description="Daftar jalur yang dinormalisasi ke 'Jalur {value}'. Kosong jika tidak disebutkan."
    )
    reasoning: str = Field(
        description="Penjelasan singkat mengapa hasil ini dipilih."
    )


_QUERY_PARSER_PROMPT = """Kamu adalah asisten pintar yang tugasnya mengekstrak parameter laporan dari permintaan pengguna dalam bahasa Indonesia.

Tanggal hari ini: {today}

Peraturan:
1. TOWER: Ekstrak nomor tower dari query. Bisa satu tower, daftar tower, atau tidak disebutkan.
   - Normalisasi ke format: "Tower {{number}}"
   - Contoh: "tower 123" → ["Tower 123"], "tower 123, 345" → ["Tower 123", "Tower 345"]
   - Jika tidak disebutkan, isi dengan null/empty list.

2. DISCORD DATES: Ekstrak rentang tanggal untuk mengambil pesan Discord.
   - Bisa satu tanggal, rentang tanggal, atau daftar tanggal.
   - Satu tanggal: "tanggal 10 juni" → [(2026-06-10, 2026-06-10)]
   - Rentang: "dari 1 juni sampai 7 juni" → [(2026-06-01, 2026-06-07)]
   - Daftar tanggal: "8 juni, 10 juni, 20 juni" → [(2026-06-08, 2026-06-08), (2026-06-10, 2026-06-10), (2026-06-20, 2026-06-20)]
   - Jika tidak disebutkan, gunakan hari ini → [(today, today)]
   - Format: list of tuples (start_date, end_date) dalam YYYY-MM-DD.

3. ROADWAYS: Ekstrak jalur/roadway dari query.
   - Normalisasi ke format: "Jalur {{value}}"
   - Contoh: "jalur jakarta - bandung" → ["Jalur Jakarta - Bandung"]
   - Bisa satu jalur, daftar jalur, atau tidak disebutkan.
   - Jika tidak disebutkan, isi dengan null/empty list.

4. Tidak perlu ekstrak "report date" — tanggal laporan berasal dari metadata foto.

Contoh:
- "tolong bikin report tower 123 tanggal 10 juni" → towers: ["Tower 123"], dates: [(2026-06-10, 2026-06-10)], roadways: null
- "report tower 123, 345 dari 1-7 juni jalur jakarta - bandung" → towers: ["Tower 123", "Tower 345"], dates: [(2026-06-01, 2026-06-07)], roadways: ["Jalur Jakarta - Bandung"]
- "laporan 8 juni, 10 juni, 20 juni" → towers: null, dates: [(2026-06-08, 2026-06-08), (2026-06-10, 2026-06-10), (2026-06-20, 2026-06-20)], roadways: null
- "bikin laporan kemarin" → towers: null, dates: [(yesterday, yesterday)], roadways: null

Permintaan pengguna: {query}
"""


def _normalize_tower_numbers(raw: list[str] | None) -> list[str] | None:
    """Normalize tower number strings to 'Tower {number}' format."""
    if not raw:
        return None
    normalized = []
    for item in raw:
        match = re.search(r"(?:tower|t)[\s.\-:]*(\d+)", item, re.IGNORECASE)
        if match:
            normalized.append(f"Tower {match.group(1)}")
    return normalized if normalized else None


def _normalize_roadways(raw: list[str] | None) -> list[str] | None:
    """Normalize roadway strings to 'Jalur {value}' format."""
    if not raw:
        return None
    normalized = []
    for item in raw:
        match = re.search(r"jalur\s*[:\-]?\s*(.+)", item, re.IGNORECASE | re.DOTALL)
        if match:
            value = match.group(1).replace("\n", " ").strip()
            value = re.sub(r"\s+", " ", value)
            normalized.append(f"Jalur {value.title()}")
    return normalized if normalized else None


def parse_report_query(user_query: str) -> ReportQueryRequest | None:
    """
    Extract report query parameters from an Indonesian natural language query.

    Parameters
    ----------
    user_query : str
        The user's message text (e.g. "tolong bikin report tower 123 tanggal 10 juni").

    Returns
    -------
    ReportQueryRequest | None
        The parsed query parameters, or None if parsing fails.
    """
    try:
        llm = create_llm()
        structured_llm = llm.with_structured_output(ReportQueryRequest)

        today = datetime.now().strftime("%Y-%m-%d (%A)")
        prompt = _QUERY_PARSER_PROMPT.format(today=today, query=user_query)

        result = structured_llm.invoke(prompt)

        # Post-process tower numbers and roadways for extra normalization
        result.tower_numbers = _normalize_tower_numbers(result.tower_numbers)
        result.roadways = _normalize_roadways(result.roadways)

        logger.info(
            "Query parsing successful: towers=%s, dates=%s, roadways=%s",
            result.tower_numbers,
            result.discord_date_ranges,
            result.roadways,
        )
        return result
    except Exception as e:
        logger.exception("Query parsing failed for query: %s", user_query)
        return None
