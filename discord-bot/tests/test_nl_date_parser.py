"""Tests for the natural language date parser module."""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from app.nl_date_parser import parse_report_dates, ReportDateRequest


# ───────────────────────────────────────────────────────────────
# parse_report_dates
# ───────────────────────────────────────────────────────────────


class FakeStructuredLLM:
    """Fake structured LLM for testing date parsing."""

    def __init__(self, response: ReportDateRequest | None):
        self._response = response

    def invoke(self, prompt: str):
        return self._response


class FakeLLM:
    """Fake LLM that returns a FakeStructuredLLM."""

    def __init__(self, response: ReportDateRequest | None):
        self._response = response

    def with_structured_output(self, schema):
        return FakeStructuredLLM(self._response)


def test_parse_report_dates_explicit_single_day():
    """Parse a single-day explicit date request."""
    expected = ReportDateRequest(
        discord_start_date=date(2026, 6, 11),
        discord_end_date=date(2026, 6, 11),
        report_start_date=date(2026, 6, 11),
        report_end_date=date(2026, 6, 11),
        reasoning="User requested report for 11 June 2026",
    )

    with patch("app.nl_date_parser._create_llm", return_value=FakeLLM(expected)):
        result = parse_report_dates("tolong bikin report untuk tanggal 11 juni 2026")

    assert result is not None
    assert result.discord_start_date == date(2026, 6, 11)
    assert result.discord_end_date == date(2026, 6, 11)
    assert result.report_start_date == date(2026, 6, 11)
    assert result.report_end_date == date(2026, 6, 11)


def test_parse_report_dates_different_discord_range():
    """Parse request with explicit Discord message date range."""
    expected = ReportDateRequest(
        discord_start_date=date(2026, 6, 10),
        discord_end_date=date(2026, 6, 11),
        report_start_date=date(2026, 6, 10),
        report_end_date=date(2026, 6, 10),
        reasoning="Discord range 10-11 June, report for 10 June",
    )

    with patch("app.nl_date_parser._create_llm", return_value=FakeLLM(expected)):
        result = parse_report_dates(
            "tolong bikinin report untuk tanggal 10 juni 2026 dari message discord di tanggal 10 - 11 juni 2026"
        )

    assert result is not None
    assert result.discord_start_date == date(2026, 6, 10)
    assert result.discord_end_date == date(2026, 6, 11)
    assert result.report_start_date == date(2026, 6, 10)
    assert result.report_end_date == date(2026, 6, 10)


def test_parse_report_dates_relative_yesterday():
    """Parse relative date 'kemarin'."""
    expected = ReportDateRequest(
        discord_start_date=date(2026, 6, 16),
        discord_end_date=date(2026, 6, 16),
        report_start_date=date(2026, 6, 16),
        report_end_date=date(2026, 6, 16),
        reasoning="kemarin = 16 June 2026",
    )

    with patch("app.nl_date_parser._create_llm", return_value=FakeLLM(expected)):
        result = parse_report_dates("bikin laporan kemarin dong")

    assert result is not None
    assert result.report_start_date == date(2026, 6, 16)


def test_parse_report_dates_failure():
    """When LLM returns None, parse_report_dates returns None."""
    with patch("app.nl_date_parser._create_llm", return_value=FakeLLM(None)):
        result = parse_report_dates("some random text")

    assert result is None


def test_parse_report_dates_exception():
    """When LLM raises an exception, parse_report_dates returns None."""
    def raise_error():
        raise RuntimeError("API error")

    with patch("app.nl_date_parser._create_llm", side_effect=RuntimeError("API error")):
        result = parse_report_dates("bikin report 11 juni 2026")

    assert result is None
