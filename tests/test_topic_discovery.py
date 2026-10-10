import pytest
from unittest.mock import patch, MagicMock
from backend.services.topic_discovery import (
    TopicDiscoveryService,
    topic_discovery_service,
)

SAMPLE_TRENDS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:ht="https://trends.google.com/trending/rss">
  <channel>
    <title>Daily Search Trends</title>
    <item>
      <title>TypeScript 5.6 Features</title>
      <ht:approx_traffic>50,000+</ht:approx_traffic>
      <description><![CDATA[TypeScript team unveils latest language and type system features.]]></description>
      <link>https://trends.google.com/trending?q=typescript</link>
      <pubDate>Thu, 09 Oct 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Cricket Match Score Today</title>
      <ht:approx_traffic>100,000+</ht:approx_traffic>
      <description><![CDATA[Match results update.]]></description>
      <link>https://trends.google.com/trending?q=cricket</link>
      <pubDate>Thu, 09 Oct 2026 11:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
"""

SAMPLE_NEWS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Google News - Technology</title>
    <item>
      <title>OpenAI Announces New Autonomous Coding Model - TechCrunch</title>
      <link>https://news.google.com/articles/openai-model</link>
      <pubDate>Thu, 09 Oct 2026 12:00:00 GMT</pubDate>
      <source url="https://techcrunch.com">TechCrunch</source>
    </item>
    <item>
      <title>Python 3.14 Release Candidate Highlights - Real Python</title>
      <link>https://news.google.com/articles/python-314</link>
      <pubDate>Thu, 09 Oct 2026 13:00:00 GMT</pubDate>
      <source url="https://realpython.com">Real Python</source>
    </item>
  </channel>
</rss>
"""

def test_topic_discovery_discover_trending_parses_properly():
    service = TopicDiscoveryService()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        # Mock first call (Google Trends) and second call (Google News)
        resp_trends = MagicMock(status_code=200, text=SAMPLE_TRENDS_RSS)
        resp_news = MagicMock(status_code=200, text=SAMPLE_NEWS_RSS)
        mock_client.get.side_effect = [resp_trends, resp_news]

        items = service.discover_trending(country="IN", category="Technology", limit=10)
        assert len(items) >= 2
        titles = [i["title"] for i in items]
        assert any("Typescript" in t or "TypeScript" in t for t in titles)
        assert any("Openai" in t or "OpenAI" in t for t in titles)

def test_topic_discovery_filters_and_deduplicates():
    service = TopicDiscoveryService()

    raw_items = [
        {
            "title": "React 19 Server Actions Deep Dive",
            "explanation": "Understanding server actions in React 19.",
            "source": "Google Trends",
            "source_url": "https://trends.google.com",
            "category": "Technology",
            "search_intent": "Informational",
            "estimated_difficulty": "Intermediate (Estimate)",
            "audience_fit": "High",
            "article_potential": "High",
        },
        {
            "title": "React 19 Server Actions Deep Dive Tutorial",  # Duplicate / Near-duplicate
            "explanation": "Duplicate tutorial concept.",
            "source": "Google News",
            "source_url": "https://news.google.com",
            "category": "Technology",
            "search_intent": "Informational",
            "estimated_difficulty": "Intermediate (Estimate)",
            "audience_fit": "High",
            "article_potential": "High",
        },
        {
            "title": "Irrelevant Celebrity Gossip News",
            "explanation": "Showbiz updates.",
            "source": "Trends",
            "source_url": "https://trends.google.com",
            "category": "Technology",
            "search_intent": "Informational",
            "estimated_difficulty": "Beginner (Estimate)",
            "audience_fit": "Low",
            "article_potential": "Low",
        }
    ]

    filtered = service._filter_and_deduplicate(raw_items, category="Technology")
    assert len(filtered) >= 1
    # Deduplication check: should only have 1 React 19 item
    react_items = [i for i in filtered if "React 19" in i["title"]]
    assert len(react_items) == 1

def test_evergreen_and_random_topic_generation():
    service = TopicDiscoveryService()
    evergreen = service.discover_random_or_evergreen(
        mode="evergreen",
        category="Web Development",
        difficulty="Intermediate",
        audience="Full-Stack Developers",
        country="IN",
        limit=5,
    )
    assert len(evergreen) >= 1
    for item in evergreen:
        assert item["discovery_mode"] == "evergreen"
        assert "(Estimate)" in item["estimated_difficulty"]
        assert len(item["title"]) > 5

    random_ideas = service.discover_random_or_evergreen(
        mode="random",
        category="AI & Machine Learning",
        difficulty="Advanced",
        audience="ML Engineers",
        country="IN",
        limit=4,
    )
    assert len(random_ideas) >= 1
    for item in random_ideas:
        assert item["discovery_mode"] == "random"
