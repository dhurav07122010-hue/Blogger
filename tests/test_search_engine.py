import pytest
from backend.services.search_engine import LiveResearchEngine

def test_search_engine_conduct_deep_research():
    engine = LiveResearchEngine()

    # Pre-populate cache or test real research structure
    result = engine.conduct_deep_research("Python Asyncio Patterns")
    assert "sources" in result
    assert isinstance(result["sources"], list)
    assert len(result["sources"]) >= 1
    assert "research_summary" in result
    # Check that sources have required keys
    first_source = result["sources"][0]
    assert "title" in first_source
    assert "url" in first_source

def test_search_engine_cache_behavior():
    engine = LiveResearchEngine()
    fake_result = {
        "sources": [{"title": "Cached Title", "url": "https://example.com"}],
        "research_summary": "Cached Summary",
        "contradictions_or_caveats": [],
        "live_internet_used": True,
    }
    # Cache key format: f"{topic}_{country_region}".lower()
    engine._cache["cached topic_global"] = (9999999999.0, fake_result)

    cached = engine.conduct_deep_research("cached topic", country_region="Global")
    assert cached["sources"][0]["title"] == "Cached Title"
