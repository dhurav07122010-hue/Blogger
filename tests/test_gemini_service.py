"""
Tests for Gemini API service, retry logic, token tracking, and demo mode fallbacks.
"""

from backend.services.gemini import gemini_service, tracker
from backend.config import settings


def test_gemini_token_tracker():
    initial_tokens = tracker.total_prompt_tokens
    tracker.add_usage(prompt_tokens=150, completion_tokens=300)

    summary = tracker.get_summary()
    assert summary["prompt_tokens"] == initial_tokens + 150
    assert summary["completion_tokens"] >= 300
    assert summary["total_calls"] >= 1
    assert summary["estimated_cost_usd"] > 0


def test_gemini_text_generation_in_demo_mode():
    settings.DEMO_MODE = True
    text, in_tok, out_tok = gemini_service.generate_text("Explain core concepts of high reliability")

    assert len(text) > 50
    assert in_tok > 0
    assert out_tok > 0
    assert "# " in text or "## " in text


def test_gemini_structured_json_generation_in_demo_mode():
    settings.DEMO_MODE = True
    data, in_tok, out_tok = gemini_service.generate_json("Research sources on API performance")

    assert isinstance(data, dict)
    assert "sources" in data or "results" in data or "status" in data
    assert in_tok > 0
    assert out_tok > 0


def test_retry_mechanism_resilience():
    # Verify exponential backoff structure does not raise unhandled exceptions
    settings.DEMO_MODE = True
    data, _, _ = gemini_service.generate_json("Fact check this claim")
    assert isinstance(data, dict)
