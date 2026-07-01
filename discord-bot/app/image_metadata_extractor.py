"""Image metadata extractor using Gemini vision for reading bottom-right corner text."""

import asyncio
import base64
import logging
import re
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import dateparser
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.llm import create_llm


logger = logging.getLogger(__name__)


_FUZZY_LABEL_THRESHOLD = 0.75


def _label_token_matches(token: str, canonical: str) -> bool:
    """Return True if `token` is within edit distance ~2 of `canonical`."""
    return (
        SequenceMatcher(None, token.lower(), canonical.lower()).ratio()
        >= _FUZZY_LABEL_THRESHOLD
    )


class RawImageMetadata(BaseModel):
    """Raw extraction output from Gemini vision."""

    date_text: str = Field(
        description="Date text exactly as shown, e.g. 'Sabtu, 23 Mei 2026' or '2026-06-25'"
    )
    tower_id_text: str = Field(
        description=(
            "Tower identifier text exactly as shown. "
            "Examples: 'T.495', 'T - 495', 'Tower 500', 'Tower: 567'"
        )
    )
    roadway_text: str = Field(
        description=(
            "Roadway text exactly as shown, starting with 'Jalur:'. "
            "May span multiple lines. Example: 'Jalur: Purwakarta - Banyuwangi'"
        )
    )
    section_text: str = Field(
        description="Section text exactly as shown, e.g. 'Section: Mid' or 'Section: Atas'"
    )
    measurement_tools_text: str = Field(
        description="Measurement tools text exactly as shown, e.g. 'Alat ukur'"
    )


class NormalizedImageMetadata(BaseModel):
    """Metadata after Python normalization."""

    tower_id: str
    sub_id: str
    report_date: date
    roadway: Optional[str] = None
    measurement_tools: Optional[str] = None
    raw_text: str


def normalize_tower_id(raw: str) -> Optional[str]:
    """
    Normalize tower ID variations to 'Tower {number}'.

    Handles formats like:
      - T.495, T - 495, Tower 500, Tower: 567
    """
    pattern = r"(?:tower|t)[\s.\-:]*(\d+)"
    match = re.search(pattern, raw, re.IGNORECASE)
    if match:
        return f"Tower {match.group(1)}"
    return None


def normalize_section(raw: str) -> Optional[str]:
    """
    Normalize section text to 'Section {value}'.

    Handles formats like:
      - Section: Mid, Section - Top, Section: Bottom
      - Section: Atas, Section: Tengah, Section: bawah
      - Typo-tolerant: Sction, Secion, etc. (ratio >= 0.75 vs 'section')
    """
    value_re = r"(top|mid|bottom|atas|tengah|bawah)"
    match = re.search(
        rf"section\s*[:\-]?\s*{value_re}",
        raw,
        re.IGNORECASE,
    )
    if match:
        return f"Section {match.group(1).lower()}"

    # Fuzzy fallback: tolerate keyword typos like "Sction" or "Secion".
    fuzzy_match = re.search(
        rf"^([A-Za-z]+)\s*[:\-]?\s*{value_re}",
        raw,
        re.IGNORECASE,
    )
    if fuzzy_match and _label_token_matches(fuzzy_match.group(1), "section"):
        return f"Section {fuzzy_match.group(2).lower()}"

    return None


def normalize_roadway(raw: str) -> Optional[str]:
    """
    Normalize roadway text to 'Jalur {value}'.

    Handles multi-line values. Example:
      - Jalur: Purwakarta - Banyuwangi
      - Jalur: ianine\n- angakgna
      - Typo-tolerant: Jakur:, Jlaur:, etc. (ratio >= 0.75 vs 'jalur')
    """
    match = re.search(r"jalur\s*[:\-]?\s*(.+)", raw, re.IGNORECASE | re.DOTALL)
    if match:
        value = match.group(1).replace("\n", " ").strip()
        value = re.sub(r"\s+", " ", value)
        return f"Jalur {value}"

    # Fuzzy fallback: tolerate keyword typos like "Jakur" or "Jlaur".
    fuzzy_match = re.search(
        r"^([A-Za-z]+)\s*[:\-]?\s*(.+)",
        raw,
        re.IGNORECASE | re.DOTALL,
    )
    if fuzzy_match and _label_token_matches(fuzzy_match.group(1), "jalur"):
        value = fuzzy_match.group(2).replace("\n", " ").strip()
        value = re.sub(r"\s+", " ", value)
        if not value:
            return None
        return f"Jalur {value}"

    return None


def normalize_measurement_tools(raw: str) -> Optional[str]:
    """
    Detect measurement tools text.

    Returns 'Alat Ukur' only when the text is exactly 'alat ukur'
    (case-insensitive, with any whitespace count). Phrases that merely
    contain the words (e.g. 'Tidak ada alat ukur') do NOT match.
    """
    if re.fullmatch(r"alat\s+ukur", raw.strip(), re.IGNORECASE):
        return "Alat Ukur"
    return None


def parse_date(raw: str) -> Optional[date]:
    """
    Parse date from various formats using dateparser.

    Supports Indonesian and US date formats, as well as ISO yyyy-mm-dd.
    """
    parsed = dateparser.parse(raw, languages=["en", "id"])
    if parsed:
        return parsed.date()
    return None


async def extract_image_metadata(image_path: Path) -> Optional[NormalizedImageMetadata]:
    """
    Extract metadata from an image using Gemini vision, then normalize.

    Parameters
    ----------
    image_path : Path
        Path to the local image file.

    Returns
    -------
    NormalizedImageMetadata | None
        Normalized metadata if extraction and normalization succeed,
        None otherwise.
    """
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        suffix = image_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(suffix, "image/jpeg")

        llm = create_llm()
        structured_llm = llm.with_structured_output(RawImageMetadata)

        prompt = (
            "Read all the text in the bottom-right corner of this image. "
            "This text block typically contains a date, a tower identifier, "
            "a roadway, a section label, and a measurement tools label. "
            "Extract the following exactly as it appears:\n"
            "- date_text: The date text (e.g. 'Sabtu, 23 Mei 2026' or '2026-06-25')\n"
            "- tower_id_text: The tower identifier text exactly as shown. "
            "Examples: 'T.495', 'T - 495', 'Tower 500', 'Tower: 567'\n"
            "- roadway_text: The roadway text exactly as shown, starting with 'Jalur:'. "
            "If it spans multiple lines, include all lines. "
            "Example: 'Jalur: Purwakarta - Banyuwangi'\n"
            "- section_text: The section text exactly as shown "
            "(e.g. 'Section: Mid', 'Section: Atas')\n"
            "- measurement_tools_text: The measurement tools text exactly as shown "
            "(e.g. 'Alat ukur'). "
            "If no measurement tools text is present, return an empty string.\n\n"
            "The label keywords themselves may be mistyped in the image "
            "(e.g. 'Jakur:', 'Jlaur:', 'Sction:', 'Secion Atas'). "
            "Normalize any label-keyword typo to its canonical form — "
            "'Jalur' for the roadway label and 'Section' for the section label — "
            "but transcribe the value after the label exactly as shown, including any "
            "typos in the value itself. The 'date_text', 'tower_id_text', and "
            "'measurement_tools_text' fields are not label keywords and should be "
            "transcribed as-is."
        )

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                },
            ]
        )

        raw = await asyncio.to_thread(structured_llm.invoke, [message])

        tower_id = normalize_tower_id(raw.tower_id_text)
        sub_id = normalize_section(raw.section_text)
        report_date = parse_date(raw.date_text)
        roadway = normalize_roadway(raw.roadway_text) if raw.roadway_text.strip() else None
        measurement_tools = (
            normalize_measurement_tools(raw.measurement_tools_text)
            if raw.measurement_tools_text.strip()
            else None
        )

        # Required fields: tower_id, sub_id, report_date
        if not tower_id or not sub_id or not report_date:
            logger.warning(
                "Metadata normalization failed: tower_id=%s, sub_id=%s, "
                "report_date=%s, raw=%s",
                tower_id,
                sub_id,
                report_date,
                raw.model_dump(),
            )
            return None

        # Roadway is required only when roadway_text is non-empty
        if raw.roadway_text.strip() and roadway is None:
            logger.warning(
                "Roadway normalization failed: roadway_text=%s, raw=%s",
                raw.roadway_text,
                raw.model_dump(),
            )
            return None

        return NormalizedImageMetadata(
            tower_id=tower_id,
            sub_id=sub_id,
            report_date=report_date,
            roadway=roadway,
            measurement_tools=measurement_tools,
            raw_text=(
                f"date: {raw.date_text}, "
                f"tower: {raw.tower_id_text}, "
                f"roadway: {raw.roadway_text}, "
                f"section: {raw.section_text}, "
                f"tools: {raw.measurement_tools_text}"
            ),
        )

    except Exception:
        logger.exception("Failed to extract metadata from image: %s", image_path)
        return None
