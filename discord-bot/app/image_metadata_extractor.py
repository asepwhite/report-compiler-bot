"""Image metadata extractor using Gemini vision for reading bottom-right corner text."""

import asyncio
import base64
import logging
import re
from datetime import date
from pathlib import Path
from typing import Optional

import dateparser
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.llm import create_llm


logger = logging.getLogger(__name__)


class RawImageMetadata(BaseModel):
    """Raw extraction output from Gemini vision."""

    date_text: str = Field(
        description="Date text exactly as shown, e.g. 'Sabtu, 23 Mei 2026' or '05/31/2026'"
    )
    tower_id_text: str = Field(
        description=(
            "Tower identifier text exactly as shown. "
            "Examples: 'T.495', 'T - 495', 'Tower 500', 'Tower 500 cimahi', "
            "'Tower 500 - depok, jawabarat'"
        )
    )
    section_text: str = Field(
        description="Section text exactly as shown, e.g. 'Section: Mid'"
    )


class NormalizedImageMetadata(BaseModel):
    """Metadata after Python normalization."""

    tower_id: str
    sub_id: str
    report_date: date
    raw_text: str


def normalize_tower_id(raw: str) -> Optional[str]:
    """
    Normalize tower ID variations to 'Tower {number}'.

    Handles formats like:
      - T.495, T - 495, Tower 500
      - Tower 500 cimahi, Tower 500 - depok, jawabarat
    """
    pattern = r"(?:tower|t)[\s.\-]*(\d+)"
    match = re.search(pattern, raw, re.IGNORECASE)
    if match:
        return f"Tower {match.group(1)}"
    return None


def normalize_section(raw: str) -> Optional[str]:
    """
    Normalize section text to 'Section {top|mid|bottom}'.

    Handles formats like:
      - Section: Mid, Section - Top, Section: Bottom
    """
    match = re.search(r"section\s*[:\-]?\s*(top|mid|bottom)", raw, re.IGNORECASE)
    if match:
        return f"Section {match.group(1).lower()}"
    return None


def parse_date(raw: str) -> Optional[date]:
    """
    Parse date from various formats using dateparser.

    Supports Indonesian and US date formats.
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
            "This text block typically contains a date, a tower identifier, and a section label. "
            "Extract the following exactly as it appears:\n"
            "- date_text: The date text (e.g. 'Sabtu, 23 Mei 2026' or '05/31/2026')\n"
            "- tower_id_text: The tower identifier text exactly as shown. "
            "Examples: 'T.495', 'T - 495', 'Tower 500', 'Tower 500 cimahi', "
            "'Tower 500 - depok, jawabarat'\n"
            "- section_text: The section text exactly as shown (e.g. 'Section: Mid')"
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

        return NormalizedImageMetadata(
            tower_id=tower_id,
            sub_id=sub_id,
            report_date=report_date,
            raw_text=(
                f"date: {raw.date_text}, "
                f"tower: {raw.tower_id_text}, "
                f"section: {raw.section_text}"
            ),
        )

    except Exception:
        logger.exception("Failed to extract metadata from image: %s", image_path)
        return None
