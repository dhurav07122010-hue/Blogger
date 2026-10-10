"""
Tests for UI/UX Redesign API Endpoints:
- Dedicated AI Writing Assistant endpoint (/api/articles/ai-assist)
- Publishing History endpoint (/api/blogger/history)
- Frontend static asset delivery (index.html, style.css, app.js)
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db, SessionLocal
from backend.models.entities import Article, PublishingHistory

client = TestClient(app)


def test_ai_assist_improve_action():
    resp = client.post("/api/articles/ai-assist", json={
        "action": "improve",
        "content": "This application uses artificial intelligence to write blogs quickly.",
        "target_audience": "Developers"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "improve"
    assert "result" in data
    assert len(data["result"]) > 0


def test_ai_assist_suggest_titles_action():
    resp = client.post("/api/articles/ai-assist", json={
        "action": "suggest_titles",
        "title": "Modern Frontend Development with Web Standards",
        "target_audience": "Software Engineers"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "suggest_titles"
    assert len(data["result"]) > 0


def test_ai_assist_generate_toc_action():
    sample_content = """
    <h2>Introduction to WebSockets</h2>
    <p>WebSockets enable bi-directional communication.</p>
    <h2>Setting Up the Server</h2>
    <p>Using Node or Python.</p>
    <h3>Configuring Keepalive</h3>
    <p>Details on pings.</p>
    <h2>Production Deployment</h2>
    <p>Best practices.</p>
    """
    resp = client.post("/api/articles/ai-assist", json={
        "action": "generate_toc",
        "content": sample_content
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "generate_toc"
    assert "Table of Contents" in data["result"]
    assert "Introduction to WebSockets" in data["result"]
    assert "Setting Up the Server" in data["result"]


def test_ai_assist_suggest_keywords_action():
    resp = client.post("/api/articles/ai-assist", json={
        "action": "suggest_keywords",
        "title": "Next.js 15 Server Components and Caching Strategies"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "suggest_keywords"
    assert len(data["result"]) > 0


def test_ai_assist_meta_description_action():
    resp = client.post("/api/articles/ai-assist", json={
        "action": "meta_description",
        "title": "Clean Architecture Principles in Python",
        "content": "A comprehensive walkthrough of dependency inversion, entities, and use cases."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "meta_description"
    assert len(data["result"]) > 0


def test_publishing_history_endpoint():
    db = SessionLocal()
    try:
        # Create a sample article and publishing record
        art = Article(title="Test History Article", content="Sample body")
        db.add(art)
        db.commit()
        db.refresh(art)

        hist = PublishingHistory(
            article_id=art.id,
            blogger_blog_id="demo-101",
            blogger_post_id="post-999",
            action="CREATE_DRAFT",
            status="SUCCESS",
            post_url="https://blogger.com/draft/999"
        )
        db.add(hist)
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/blogger/history")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    assert "article_title" in first
    assert "action" in first
    assert "status" in first


def test_frontend_serves_redesigned_ui():
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    # Verify core redesign elements exist
    assert "Bloggers — AI Content Studio" in html
    assert 'id="app-sidebar"' in html
    assert 'id="tab-create"' in html
    assert 'id="editor-article-title"' in html
    assert 'id="editor-content-area"' in html
    assert 'id="editor-toolbar"' in html or 'class="editor-toolbar"' in html
    assert 'id="tab-templates"' in html
    assert 'id="tab-history"' in html
    assert 'id="studio-config-drawer"' in html
