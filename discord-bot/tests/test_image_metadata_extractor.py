"""Tests for the image metadata extractor module."""

import base64
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.image_metadata_extractor import (
    normalize_tower_id,
    normalize_section,
    normalize_roadway,
    normalize_measurement_tools,
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


def test_normalize_tower_id_colon_format():
    """Tower: 567 → Tower 567."""
    assert normalize_tower_id("Tower: 567") == "Tower 567"


def test_normalize_tower_id_colon_lowercase():
    """tower: 352 → Tower 352."""
    assert normalize_tower_id("tower: 352") == "Tower 352"


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


def test_normalize_section_atas():
    """Section: Atas → Section atas."""
    assert normalize_section("Section: Atas") == "Section atas"


def test_normalize_section_tengah():
    """Section: Tengah → Section tengah."""
    assert normalize_section("Section: Tengah") == "Section tengah"


def test_normalize_section_bawah():
    """Section: bawah → Section bawah."""
    assert normalize_section("Section: bawah") == "Section bawah"


def test_normalize_section_no_section():
    """Invalid section returns None."""
    assert normalize_section("some random text") is None


def test_normalize_section_empty():
    """Empty string returns None."""
    assert normalize_section("") is None


# ───────────────────────────────────────────────────────────────
# normalize_roadway
# ───────────────────────────────────────────────────────────────


def test_normalize_roadway_basic():
    """Jalur: Purwakarta - Banyuwangi → Jalur Purwakarta - Banyuwangi."""
    assert normalize_roadway("Jalur: Purwakarta - Banyuwangi") == "Jalur Purwakarta - Banyuwangi"


def test_normalize_roadway_multiline():
    """Jalur: ianine\n- angakgna → Jalur ianine - angakgna."""
    raw = "Jalur: ianine\n- angakgna"
    assert normalize_roadway(raw) == "Jalur ianine - angakgna"


def test_normalize_roadway_lowercase():
    """jalur: ianine → Jalur ianine."""
    assert normalize_roadway("jalur: ianine") == "Jalur ianine"


def test_normalize_roadway_dash_separator():
    """Jalur - Some Road → Jalur Some Road."""
    assert normalize_roadway("Jalur - Some Road") == "Jalur Some Road"


def test_normalize_roadway_no_match():
    """No roadway found returns None."""
    assert normalize_roadway("some random text") is None


def test_normalize_roadway_empty():
    """Empty string returns None."""
    assert normalize_roadway("") is None


# ───────────────────────────────────────────────────────────────
# normalize_roadway — fuzzy label tolerance
# ───────────────────────────────────────────────────────────────


def test_normalize_roadway_typo_jakur():
    """Jakur: → Jalur (fuzzy)."""
    assert (
        normalize_roadway("Jakur: Purwakarta - Banyuwangi")
        == "Jalur Purwakarta - Banyuwangi"
    )


def test_normalize_roadway_typo_jlaur():
    """Jlaur: → Jalur (fuzzy)."""
    assert (
        normalize_roadway("Jlaur: ianine - angakgna")
        == "Jalur ianine - angakgna"
    )


def test_normalize_roadway_typo_no_colon():
    """Jakur (no colon) → Jalur (fuzzy + optional separator)."""
    assert normalize_roadway("Jakur Purwakarta") == "Jalur Purwakarta"


def test_normalize_roadway_typo_multiline():
    """Multi-line value with fuzzy label."""
    raw = "Jlaur: ianine\n- angakgna"
    assert normalize_roadway(raw) == "Jalur ianine - angakgna"


def test_normalize_roadway_typo_too_far():
    """Label too far from 'jalur' (ratio < 0.75) returns None."""
    assert normalize_roadway("Xqrur: Foo") is None


# ───────────────────────────────────────────────────────────────
# normalize_section — fuzzy label tolerance
# ───────────────────────────────────────────────────────────────


def test_normalize_section_typo_sction():
    """Sction → Section (fuzzy)."""
    assert normalize_section("Sction: Atas") == "Section atas"


def test_normalize_section_typo_sction_no_colon():
    """Sction Atas (no colon) → Section atas."""
    assert normalize_section("Sction Atas") == "Section atas"


def test_normalize_section_typo_sction_mid():
    """Sction: Mid → Section mid."""
    assert normalize_section("Sction: Mid") == "Section mid"


def test_normalize_section_typo_invalid_value():
    """Fuzzy label match with invalid value still returns None."""
    assert normalize_section("Sction Foo") is None


def test_normalize_section_typo_too_far():
    """Label too far from 'section' returns None."""
    assert normalize_section("Xectn: Mid") is None


# ───────────────────────────────────────────────────────────────
# normalize_measurement_tools
# ───────────────────────────────────────────────────────────────


def test_normalize_measurement_tools_basic():
    """Alat ukur → Alat Ukur."""
    assert normalize_measurement_tools("Alat ukur") == "Alat Ukur"


def test_normalize_measurement_tools_lowercase():
    """alat ukur → Alat Ukur."""
    assert normalize_measurement_tools("alat ukur") == "Alat Ukur"


def test_normalize_measurement_tools_mixed_case():
    """ALAT UKUR → Alat Ukur."""
    assert normalize_measurement_tools("ALAT UKUR") == "Alat Ukur"


def test_normalize_measurement_tools_extra_whitespace():
    """alat  ukur → Alat Ukur."""
    assert normalize_measurement_tools("alat  ukur") == "Alat Ukur"


def test_normalize_measurement_tools_no_match():
    """No measurement tools found returns None."""
    assert normalize_measurement_tools("some random text") is None


def test_normalize_measurement_tools_negative_context():
    """Text that merely contains 'alat ukur' in a negative context returns None."""
    assert normalize_measurement_tools("Tidak ada alat ukur") is None
    assert normalize_measurement_tools("tidak terdapat alat ukur") is None


def test_normalize_measurement_tools_with_surrounding_text():
    """Text with extra words around 'alat ukur' returns None (fullmatch required)."""
    assert normalize_measurement_tools("alat ukur: multimeter") is None
    assert normalize_measurement_tools("label alat ukur") is None


def test_normalize_measurement_tools_empty():
    """Empty string returns None."""
    assert normalize_measurement_tools("") is None


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
async def test_extract_image_metadata_success_old_format(tmp_path):
    """Happy path: old format still works."""
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image data")

    raw = RawImageMetadata(
        date_text="Sabtu, 23 Mei 2026",
        tower_id_text="T.495",
        roadway_text="",
        section_text="Section: Mid",
        measurement_tools_text="",
    )

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = raw
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("app.image_metadata_extractor.create_llm", return_value=mock_llm):
        result = await extract_image_metadata(img_path)

    assert result is not None
    assert result.tower_id == "Tower 495"
    assert result.sub_id == "Section mid"
    assert result.report_date == date(2026, 5, 23)
    assert result.roadway is None
    assert result.measurement_tools is None


@pytest.mark.asyncio
async def test_extract_image_metadata_success_new_format(tmp_path):
    """Happy path: new format with all 5 fields."""
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image data")

    raw = RawImageMetadata(
        date_text="2026-06-25",
        tower_id_text="Tower: 567",
        roadway_text="Jalur: Purwakarta - Banyuwangi",
        section_text="Section: Atas",
        measurement_tools_text="Alat ukur",
    )

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = raw
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("app.image_metadata_extractor.create_llm", return_value=mock_llm):
        result = await extract_image_metadata(img_path)

    assert result is not None
    assert result.tower_id == "Tower 567"
    assert result.sub_id == "Section atas"
    assert result.report_date == date(2026, 6, 25)
    assert result.roadway == "Jalur Purwakarta - Banyuwangi"
    assert result.measurement_tools == "Alat Ukur"


@pytest.mark.asyncio
async def test_extract_image_metadata_multiline_roadway(tmp_path):
    """New format with multi-line roadway."""
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image data")

    raw = RawImageMetadata(
        date_text="2026-06-25",
        tower_id_text="Tower: 352",
        roadway_text="Jalur: ianine\n- angakgna",
        section_text="Section: bawah",
        measurement_tools_text="",
    )

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = raw
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("app.image_metadata_extractor.create_llm", return_value=mock_llm):
        result = await extract_image_metadata(img_path)

    assert result is not None
    assert result.tower_id == "Tower 352"
    assert result.sub_id == "Section bawah"
    assert result.roadway == "Jalur ianine - angakgna"
    assert result.measurement_tools is None


@pytest.mark.asyncio
async def test_extract_image_metadata_roadway_validation_fails(tmp_path):
    """If roadway text is provided but invalid, image is skipped."""
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image data")

    raw = RawImageMetadata(
        date_text="2026-06-25",
        tower_id_text="Tower: 567",
        roadway_text="invalid roadway text",
        section_text="Section: Atas",
        measurement_tools_text="Alat ukur",
    )

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = raw
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("app.image_metadata_extractor.create_llm", return_value=mock_llm):
        result = await extract_image_metadata(img_path)

    assert result is None


@pytest.mark.asyncio
async def test_extract_image_metadata_optional_measurement_tools(tmp_path):
    """Missing measurement tools should not block the image."""
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image data")

    raw = RawImageMetadata(
        date_text="2026-06-25",
        tower_id_text="Tower: 567",
        roadway_text="Jalur: Purwakarta - Banyuwangi",
        section_text="Section: Atas",
        measurement_tools_text="",
    )

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = raw
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("app.image_metadata_extractor.create_llm", return_value=mock_llm):
        result = await extract_image_metadata(img_path)

    assert result is not None
    assert result.measurement_tools is None


@pytest.mark.asyncio
async def test_extract_image_metadata_normalization_fails(tmp_path):
    """If normalization fails (e.g. missing tower ID), returns None."""
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image data")

    raw = RawImageMetadata(
        date_text="Sabtu, 23 Mei 2026",
        tower_id_text="invalid text",
        roadway_text="",
        section_text="Section: Mid",
        measurement_tools_text="",
    )

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = raw
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("app.image_metadata_extractor.create_llm", return_value=mock_llm):
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

    with patch("app.image_metadata_extractor.create_llm", return_value=mock_llm):
        result = await extract_image_metadata(img_path)

    assert result is None


# ───────────────────────────────────────────────────────────────
# extract_image_metadata — fuzzy label fallback
# ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_image_metadata_typo_jakur_corrected_by_regex(tmp_path):
    """Gemini did not correct 'Jakur:' — regex fuzzy fallback still extracts it."""
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image data")

    raw = RawImageMetadata(
        date_text="2026-06-25",
        tower_id_text="Tower: 567",
        roadway_text="Jakur: Purwakarta - Banyuwangi",
        section_text="Section: Atas",
        measurement_tools_text="",
    )

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = raw
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("app.image_metadata_extractor.create_llm", return_value=mock_llm):
        result = await extract_image_metadata(img_path)

    assert result is not None
    assert result.roadway == "Jalur Purwakarta - Banyuwangi"


@pytest.mark.asyncio
async def test_extract_image_metadata_typo_sction_corrected_by_regex(tmp_path):
    """Gemini did not correct 'Sction Atas' — regex fuzzy fallback still extracts it."""
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image data")

    raw = RawImageMetadata(
        date_text="2026-06-25",
        tower_id_text="Tower: 567",
        roadway_text="Jalur: Purwakarta - Banyuwangi",
        section_text="Sction Atas",
        measurement_tools_text="",
    )

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = raw
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("app.image_metadata_extractor.create_llm", return_value=mock_llm):
        result = await extract_image_metadata(img_path)

    assert result is not None
    assert result.sub_id == "Section atas"
