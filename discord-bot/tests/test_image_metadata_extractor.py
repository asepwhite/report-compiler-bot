"""Tests for the image metadata extractor module."""

import base64
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.image_metadata_extractor import (
    normalize_tower_id,
    normalize_section,
    parse_date,
    extract_image_metadata,
    RawImageMetadata,
)


# ───────────────────────────────────────────────────────────────
# normalize_tower_id
# ───────────────────────────────────────────────────────────────


def test_normalize_tower_id_dot_format():
    """T.495 → Tower 495."""
    assert normalize_tower_id("T.495") == "Tower 495"


def test_normalize_tower_id_dash_format():
    """T - 495 → Tower 495."""
    assert normalize_tower_id("T - 495") == "Tower 495"


def test_normalize_tower_id_full_format():
    """Tower 500 → Tower 500."""
    assert normalize_tower_id("Tower 500") == "Tower 500"


def test_normalize_tower_id_with_location():
    """Tower 500 cimahi → Tower 500."""
    assert normalize_tower_id("Tower 500 cimahi") == "Tower 500"


def test_normalize_tower_id_with_multiple_locations():
    """Tower 500 - depok, jawabarat → Tower 500."""
    assert normalize_tower_id("Tower 500 - depok, jawabarat") == "Tower 500"


def test_normalize_tower_id_lowercase():
    """tower 500 → Tower 500."""
    assert normalize_tower_id("tower 500") == "Tower 500"


def test_normalize_tower_id_t_lowercase_dot():
    """t.500 → Tower 500."""
    assert normalize_tower_id("t.500") == "Tower 500"


def test_normalize_tower_id_no_match():
    """No tower ID found returns None."""
    assert normalize_tower_id("some random text") is None


def test_normalize_tower_id_empty():
    """Empty string returns None."""
    assert normalize_tower_id("") is None


# ───────────────────────────────────────────────────────────────
# normalize_section
# ───────────────────────────────────────────────────────────────


def test_normalize_section_mid():
    """Section: Mid → Section mid."""
    assert normalize_section("Section: Mid") == "Section mid"


def test_normalize_section_top():
    """Section: Top → Section top."""
    assert normalize_section("Section: Top") == "Section top"


def test_normalize_section_bottom():
    """Section: Bottom → Section bottom."""
    assert normalize_section("Section: Bottom") == "Section bottom"


def test_normalize_section_lowercase():
    """Section: mid → Section mid."""
    assert normalize_section("Section: mid") == "Section mid"


def test_normalize_section_dash_separator():
    """Section - Top → Section top."""
    assert normalize_section("Section - Top") == "Section top"


def test_normalize_section_no_section():
    """Invalid section returns None."""
    assert normalize_section("some random text") is None


def test_normalize_section_empty():
    """Empty string returns None."""
    assert normalize_section("") is None


# ───────────────────────────────────────────────────────────────
# parse_date
# ───────────────────────────────────────────────────────────────


def test_parse_date_indonesian_format():
    """Sabtu, 23 Mei 2026 → 2026-05-23."""
    result = parse_date("Sabtu, 23 Mei 2026")
    assert result == date(2026, 5, 23)


def test_parse_date_us_slash_format():
    """05/31/2026 → 2026-05-31."""
    result = parse_date("05/31/2026")
    assert result == date(2026, 5, 31)


def test_parse_date_iso_format():
    """2026-06-11 → 2026-06-11."""
    result = parse_date("2026-06-11")
    assert result == date(2026, 6, 11)


def test_parse_date_invalid():
    """Invalid date string returns None."""
    assert parse_date("not a date") is None


def test_parse_date_empty():
    """Empty string returns None."""
    assert parse_date("") is None


# ───────────────────────────────────────────────────────────────
# extract_image_metadata
# ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_image_metadata_success(tmp_path):
    """Happy path: Gemini returns valid metadata."""
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image data")

    raw = RawImageMetadata(
        date_text="Sabtu, 23 Mei 2026",
        tower_id_text="T.495",
        section_text="Section: Mid",
    )

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = raw
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("app.image_metadata_extractor._create_llm", return_value=mock_llm):
        result = await extract_image_metadata(img_path)

    assert result is not None
    assert result.tower_id == "Tower 495"
    assert result.sub_id == "Section mid"
    assert result.report_date == date(2026, 5, 23)
    assert result.raw_text == "date: Sabtu, 23 Mei 2026, tower: T.495, section: Section: Mid"


@pytest.mark.asyncio
async def test_extract_image_metadata_normalization_fails(tmp_path):
    """If normalization fails (e.g. missing tower ID), returns None."""
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image data")

    raw = RawImageMetadata(
        date_text="Sabtu, 23 Mei 2026",
        tower_id_text="invalid text",
        section_text="Section: Mid",
    )

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = raw
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("app.image_metadata_extractor._create_llm", return_value=mock_llm):
        result = await extract_image_metadata(img_path)

    assert result is None


@pytest.mark.asyncio
async def test_extract_image_metadata_gemini_error(tmp_path):
    """If Gemini raises an exception, returns None."""
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image data")

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.side_effect = Exception("API error")
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("app.image_metadata_extractor._create_llm", return_value=mock_llm):
        result = await extract_image_metadata(img_path)

    assert result is None
