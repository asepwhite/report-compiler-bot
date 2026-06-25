"""Tests for the model-based intent classification guardrail."""

from unittest.mock import patch, MagicMock

from app.intent_classifier import classify_intent, IntentClassification


# ───────────────────────────────────────────────────────────────
# classify_intent
# ───────────────────────────────────────────────────────────────


def test_classify_intent_report_request():
    """A clear report request is classified correctly."""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = IntentClassification(
        intent="report_request",
        confidence=0.95,
        reasoning="Pengguna meminta pembuatan laporan",
    )

    with patch("app.intent_classifier.create_llm", return_value=mock_llm):
        result = classify_intent("bikin laporan 10 juni")

    assert result.intent == "report_request"
    assert result.confidence == 0.95


def test_classify_intent_greeting():
    """A greeting is classified correctly."""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = IntentClassification(
        intent="greeting",
        confidence=0.92,
        reasoning="Pengguna menyapa bot",
    )

    with patch("app.intent_classifier.create_llm", return_value=mock_llm):
        result = classify_intent("halo bot")

    assert result.intent == "greeting"
    assert result.confidence == 0.92


def test_classify_intent_off_topic():
    """An off-topic request is classified correctly with high confidence."""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = IntentClassification(
        intent="off_topic",
        confidence=0.88,
        reasoning="Pengguna bertanya tentang pemrograman",
    )

    with patch("app.intent_classifier.create_llm", return_value=mock_llm):
        result = classify_intent("apa itu Python")

    assert result.intent == "off_topic"
    assert result.confidence == 0.88


def test_classify_intent_low_confidence_off_topic_becomes_report_request():
    """Low-confidence off_topic is upgraded to report_request to avoid false positives."""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = IntentClassification(
        intent="off_topic",
        confidence=0.5,
        reasoning="Tidak jelas",
    )

    with patch("app.intent_classifier.create_llm", return_value=mock_llm):
        result = classify_intent("tolong bantu")

    # Low-confidence off-topic should be treated as report_request
    assert result.intent == "report_request"
    assert result.confidence == 0.5


def test_classify_intent_error_fallback():
    """If the LLM raises an exception, fallback to report_request."""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.side_effect = RuntimeError("LLM error")

    with patch("app.intent_classifier.create_llm", return_value=mock_llm):
        result = classify_intent("bikin laporan")

    # Fallback on error
    assert result.intent == "report_request"
    assert result.confidence == 1.0
    assert "fallback" in result.reasoning.lower()


def test_classify_intent_mixed_report_and_off_topic_blocked():
    """Mixed-intent (report + off-topic question) is classified as off_topic and blocked."""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = IntentClassification(
        intent="off_topic",
        confidence=0.85,
        reasoning="Pengguna meminta laporan tetapi juga bertanya jarak antar kota",
    )

    with patch("app.intent_classifier.create_llm", return_value=mock_llm):
        result = classify_intent(
            "om tolong bantu bikin laporan @reporting-bot , "
            "tapi gw harus tau dulu jarak dari jakarta ke bandung"
        )

    assert result.intent == "off_topic"
    assert result.confidence == 0.85


def test_classify_intent_mixed_low_confidence_allowed():
    """Low-confidence mixed-intent is overridden to report_request."""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = IntentClassification(
        intent="off_topic",
        confidence=0.55,
        reasoning="Kurang yakin apakah ini mixed intent",
    )

    with patch("app.intent_classifier.create_llm", return_value=mock_llm):
        result = classify_intent("bikin laporan dan juga apa kabar")

    # Below threshold → treated as report_request
    assert result.intent == "report_request"
    assert result.confidence == 0.55
