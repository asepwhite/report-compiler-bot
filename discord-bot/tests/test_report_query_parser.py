"""Tests for the report query parser module."""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from app.report_query_parser import parse_report_query, ReportQueryRequest


class FakeStructuredLLM:
    """Fake structured LLM for testing query parsing."""

    def __init__(self, response: ReportQueryRequest | None):
        self._response = response

    def invoke(self, prompt: str):
        return self._response


class FakeLLM:
    """Fake LLM that returns a FakeStructuredLLM."""

    def __init__(self, response: ReportQueryRequest | None):
        self._response = response

    def with_structured_output(self, schema):
        return FakeStructuredLLM(self._response)


# ───────────────────────────────────────────────────────────────
# parse_report_query
# ───────────────────────────────────────────────────────────────


def test_single_tower():
    """Parse a single tower number."""
    expected = ReportQueryRequest(
        tower_numbers=["tower 123"],
        discord_date_ranges=[(date(2026, 6, 10), date(2026, 6, 10))],
        roadways=None,
        reasoning="User requested report for tower 123 on 10 June 2026",
    )

    with patch("app.report_query_parser.create_llm", return_value=FakeLLM(expected)):
        result = parse_report_query("tolong bikin report tower 123 tanggal 10 juni")

    assert result is not None
    assert result.tower_numbers == ["Tower 123"]
    assert result.discord_date_ranges == [(date(2026, 6, 10), date(2026, 6, 10))]
    assert result.roadways is None


def test_list_of_towers():
    """Parse a comma-separated list of tower numbers."""
    expected = ReportQueryRequest(
        tower_numbers=["tower 123", "tower 345"],
        discord_date_ranges=[(date(2026, 6, 10), date(2026, 6, 10))],
        roadways=None,
        reasoning="User requested report for towers 123 and 345",
    )

    with patch("app.report_query_parser.create_llm", return_value=FakeLLM(expected)):
        result = parse_report_query("report tower 123, 345 tanggal 10 juni")

    assert result is not None
    assert result.tower_numbers == ["Tower 123", "Tower 345"]


def test_no_tower():
    """When tower is not mentioned, tower_numbers should be None."""
    expected = ReportQueryRequest(
        tower_numbers=None,
        discord_date_ranges=[(date(2026, 6, 10), date(2026, 6, 10))],
        roadways=None,
        reasoning="User requested report for 10 June without specifying tower",
    )

    with patch("app.report_query_parser.create_llm", return_value=FakeLLM(expected)):
        result = parse_report_query("bikin report tanggal 10 juni")

    assert result is not None
    assert result.tower_numbers is None


def test_single_date():
    """Parse a single Discord date."""
    expected = ReportQueryRequest(
        tower_numbers=None,
        discord_date_ranges=[(date(2026, 6, 10), date(2026, 6, 10))],
        roadways=None,
        reasoning="User requested report for 10 June",
    )

    with patch("app.report_query_parser.create_llm", return_value=FakeLLM(expected)):
        result = parse_report_query("bikin report tanggal 10 juni")

    assert result is not None
    assert result.discord_date_ranges == [(date(2026, 6, 10), date(2026, 6, 10))]


def test_date_range():
    """Parse a Discord date range."""
    expected = ReportQueryRequest(
        tower_numbers=None,
        discord_date_ranges=[(date(2026, 6, 1), date(2026, 6, 7))],
        roadways=None,
        reasoning="User requested report from 1 to 7 June",
    )

    with patch("app.report_query_parser.create_llm", return_value=FakeLLM(expected)):
        result = parse_report_query("report dari 1 juni sampai 7 juni")

    assert result is not None
    assert result.discord_date_ranges == [(date(2026, 6, 1), date(2026, 6, 7))]


def test_list_of_dates():
    """Parse a list of specific Discord dates."""
    expected = ReportQueryRequest(
        tower_numbers=None,
        discord_date_ranges=[
            (date(2026, 6, 8), date(2026, 6, 8)),
            (date(2026, 6, 10), date(2026, 6, 10)),
            (date(2026, 6, 20), date(2026, 6, 20)),
        ],
        roadways=None,
        reasoning="User requested reports for 8, 10, and 20 June",
    )

    with patch("app.report_query_parser.create_llm", return_value=FakeLLM(expected)):
        result = parse_report_query("laporan 8 juni, 10 juni, 20 juni")

    assert result is not None
    assert len(result.discord_date_ranges) == 3
    assert result.discord_date_ranges[0] == (date(2026, 6, 8), date(2026, 6, 8))
    assert result.discord_date_ranges[2] == (date(2026, 6, 20), date(2026, 6, 20))


def test_single_roadway():
    """Parse a single roadway."""
    expected = ReportQueryRequest(
        tower_numbers=None,
        discord_date_ranges=[(date(2026, 6, 10), date(2026, 6, 10))],
        roadways=["jalur jakarta - bandung"],
        reasoning="User requested report for Jakarta - Bandung",
    )

    with patch("app.report_query_parser.create_llm", return_value=FakeLLM(expected)):
        result = parse_report_query("report tanggal 10 juni jalur jakarta - bandung")

    assert result is not None
    assert result.roadways == ["Jalur Jakarta - Bandung"]


def test_list_of_roadways():
    """Parse a comma-separated list of roadways."""
    expected = ReportQueryRequest(
        tower_numbers=None,
        discord_date_ranges=[(date(2026, 6, 10), date(2026, 6, 10))],
        roadways=["jalur jakarta - bandung", "jalur jakarta - surabaya"],
        reasoning="User requested reports for two roadways",
    )

    with patch("app.report_query_parser.create_llm", return_value=FakeLLM(expected)):
        result = parse_report_query("report jalur jakarta - bandung, jakarta - surabaya")

    assert result is not None
    assert len(result.roadways) == 2
    assert result.roadways[0] == "Jalur Jakarta - Bandung"


def test_no_roadway():
    """When roadway is not mentioned, roadways should be None."""
    expected = ReportQueryRequest(
        tower_numbers=None,
        discord_date_ranges=[(date(2026, 6, 10), date(2026, 6, 10))],
        roadways=None,
        reasoning="User requested report without specifying roadway",
    )

    with patch("app.report_query_parser.create_llm", return_value=FakeLLM(expected)):
        result = parse_report_query("bikin report tanggal 10 juni")

    assert result is not None
    assert result.roadways is None


def test_combined_all_params():
    """Parse query with tower, dates, and roadway all together."""
    expected = ReportQueryRequest(
        tower_numbers=["tower 123", "tower 345"],
        discord_date_ranges=[(date(2026, 6, 1), date(2026, 6, 7))],
        roadways=["jalur jakarta - bandung"],
        reasoning="User requested report for towers 123, 345 from 1-7 June for Jakarta - Bandung",
    )

    with patch("app.report_query_parser.create_llm", return_value=FakeLLM(expected)):
        result = parse_report_query(
            "report tower 123, 345 dari 1-7 juni jalur jakarta - bandung"
        )

    assert result is not None
    assert result.tower_numbers == ["Tower 123", "Tower 345"]
    assert result.discord_date_ranges == [(date(2026, 6, 1), date(2026, 6, 7))]
    assert result.roadways == ["Jalur Jakarta - Bandung"]


def test_failure():
    """When LLM returns None, parse_report_query returns None."""
    with patch("app.report_query_parser.create_llm", return_value=FakeLLM(None)):
        result = parse_report_query("some random text")

    assert result is None


def test_exception():
    """When LLM raises an exception, parse_report_query returns None."""
    with patch("app.report_query_parser.create_llm", side_effect=RuntimeError("API error")):
        result = parse_report_query("bikin report")

    assert result is None
