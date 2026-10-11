"""
Reliability, HTML Sanitization, Quality Gate, and Hero Banner Verification Tests.
Ensures:
1. Malformed HTML / backslash escapes (e.g. \\<h2...\\>) are cleanly unescaped and formatted.
2. Mixed Markdown and HTML content converts properly to Blogger-compatible HTML.
3. Quality Checker heavily penalizes missing citations and unsupported claims (no unearned 80+ scores).
4. Hero Banner metadata update endpoint functions properly.
5. Rich /api/health diagnostics return uptime and DB connection status.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models.entities import Article, ArticleStatus
from backend.database import SessionLocal
from backend.services.blogger import markdown_to_blogger_html, sanitize_blogger_html
from backend.services.quality_checker import quality_checker

client = TestClient(app)


def test_markdown_to_blogger_html_unescapes_backslash_headings():
    """Verify \\<h2...\\> and mixed markdown is properly normalized to clean HTML."""
    raw_content = r"""# 10 Easy Ways to Use HTML

\<h2 id="structure"\>1. Clean Document Structure\</h2\>

Here is an explanation of standard semantics.

\<h2 id="media"\>2. Responsive Media Embeds\</h2\>

Make sure to use modern attributes.

```html
<picture>
  <source srcset="hero.webp" type="image/webp">
  <img src="hero.jpg" alt="Hero banner">
</picture>
```

- Item one
- Item two
"""
    html = markdown_to_blogger_html(raw_content)
    # Must contain proper <h2> tags without backslashes
    assert "<h2" in html
    assert r"\<h2" not in html
    assert r"\</h2\>" not in html
    assert "1. Clean Document Structure</h2>" in html
    assert "2. Responsive Media Embeds</h2>" in html
    # Code block must be preserved
    assert "<code" in html
    assert "<picture>" in html or "&lt;picture&gt;" in html
    # Lists must be preserved
    assert "<ul" in html
    assert "Item one</li>" in html


def test_mixed_html_and_markdown_preserves_both():
    """Ensure existing HTML blocks (e.g. hero banner separator) do not break markdown parsing."""
    banner = '<div class="separator"><img src="https://example.com/banner.jpg" alt="Banner" /></div>'
    markdown_body = """
## Advanced Techniques

When designing scalable architectures, observe standard patterns.

### Step 1: Modularity

Divide concerns logically.
"""
    full_text = banner + "\n\n" + markdown_body
    html = markdown_to_blogger_html(full_text)

    # Banner preserved
    assert '<div class="separator">' in html
    # Markdown headings converted
    assert '<h2' in html
    assert 'Advanced Techniques</h2>' in html
    assert '<h3' in html
    assert 'Step 1: Modularity</h3>' in html


def test_quality_checker_penalizes_missing_sources():
    """Verify an article with 0 research sources cannot pass the quality gate or get an inflated score."""
    res = quality_checker.evaluate_quality(
        article_title="Some Thin Claims Without Sources",
        article_content="This is a short article making bold claims without citing any documentation or empirical studies.",
        research_sources=[],  # Zero sources
        fact_check_result={
            "factual_accuracy_score": 75.0,
            "has_critical_failure": False,
            "unsupported_count": 0,
        },
        seo_data={"seo_quality_score": 70.0},
    )

    assert res["passed"] is False
    assert res["overall_score"] < 75.0
    assert res["source_quality_score"] <= 35.0
    assert any("Zero Research Sources" in issue for issue in res["detected_issues"])
    assert "score_breakdown" in res


def test_quality_checker_fails_on_unsupported_factual_claims():
    """Verify an article with unsupported factual claims is capped and fails the quality gate."""
    res = quality_checker.evaluate_quality(
        article_title="Fabricated Statistics in Tech",
        article_content="Study proves that 99.9% of developers use our proprietary tool every day.",
        research_sources=[{"title": "Valid Source", "is_verified": True}],
        fact_check_result={
            "factual_accuracy_score": 40.0,
            "has_critical_failure": True,
            "unsupported_count": 2,
            "results": [
                {"claim": "99.9% of developers use proprietary tool", "status": "UNSUPPORTED", "reason": "No survey found"}
            ],
        },
        seo_data={"seo_quality_score": 85.0},
    )

    assert res["passed"] is False
    # Score capped below 65 on unsupported claims
    assert res["overall_score"] <= 65.0
    assert any("Unsupported claim" in issue for issue in res["detected_issues"])


def test_update_hero_image_metadata_endpoint():
    """Verify editing alt text and caption via /api/images/update-metadata."""
    db = SessionLocal()
    try:
        article = Article(
            title="Article for Hero Metadata Edit",
            content="Article body content.",
            status=ArticleStatus.DRAFT,
            featured_image={
                "url": "https://example.com/photo.jpg",
                "title": "Old Title",
                "altText": "Old Alt",
                "author": "Old Author",
                "caption": "Old Caption",
            },
        )
        db.add(article)
        db.commit()
        db.refresh(article)

        res = client.post(
            "/api/images/update-metadata",
            json={
                "articleId": article.id,
                "altText": "Updated Alt For SEO",
                "caption": "Photo captured during 2026 conference",
                "author": "Jane Doe",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["image"]["altText"] == "Updated Alt For SEO"
        assert data["image"]["caption"] == "Photo captured during 2026 conference"
        assert data["image"]["author"] == "Jane Doe"

        # Verify DB persisted
        db.refresh(article)
        assert article.featured_image["altText"] == "Updated Alt For SEO"
        assert article.featured_image["caption"] == "Photo captured during 2026 conference"
    finally:
        db.close()


def test_health_check_returns_diagnostics():
    """Verify /api/health returns detailed runtime diagnostics."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data
    assert data["database"] == "connected"
    assert "quality_threshold" in data
    assert "ai_generation_mode" in data
