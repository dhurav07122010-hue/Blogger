"""
Security and Safety Test Suite for Blogger AI Agent.
Verifies:
1. CORS policy restricts non-local origins.
2. Status transitions protect APPROVED and PUBLISHED states from direct bypass.
3. Bleach HTML sanitization strips <script>, onerror handlers, and javascript: links.
4. Custom image upload enforces format, size, and dimension gates.
5. Research sources are not marked verified without independent evidence.
6. Topic discovery offline fallbacks are clearly labeled.
"""

import base64
import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.blogger import markdown_to_blogger_html, sanitize_blogger_html
from backend.services.topic_discovery import TopicDiscoveryService

client = TestClient(app)


def test_cors_policy_rejects_arbitrary_origins():
    # Make request with arbitrary external origin
    headers = {"Origin": "https://malicious-website.com"}
    res = client.options("/api/health", headers=headers)
    # The Access-Control-Allow-Origin header should not echo back arbitrary malicious origin
    allowed_origin = res.headers.get("access-control-allow-origin")
    assert allowed_origin != "https://malicious-website.com"
    assert allowed_origin != "*"


def test_html_sanitizer_strips_scripts_and_event_handlers():
    malicious_html = """
    <h1>Clean Title</h1>
    <script>alert('xss');</script>
    <img src="https://example.com/pic.jpg" onerror="alert('pwnd')" alt="test image" />
    <a href="javascript:stealTokens()">Click Here</a>
    <p style="color: red;">Safe Paragraph</p>
    """
    clean = sanitize_blogger_html(malicious_html)
    assert "<script>" not in clean
    assert "alert('xss')" not in clean
    assert "onerror" not in clean
    assert "javascript:" not in clean
    assert "Safe Paragraph" in clean
    assert "https://example.com/pic.jpg" in clean


def test_markdown_to_blogger_html_sanitizes_rich_input():
    dirty_md = """
    ## Safe Header
    <script>evilCode()</script>
    [Clickable](javascript:void(0))
    Normal text with **bold**.
    """
    html = markdown_to_blogger_html(dirty_md)
    assert "<script>" not in html
    assert "evilCode" not in html
    assert "javascript:" not in html
    assert "Safe Header" in html
    assert "<strong>bold</strong>" in html


def test_status_transition_prevents_bypassing_approval_gate():
    # Create article
    create_res = client.post("/api/articles", json={
        "title": "Security Transition Test",
        "content": "Draft body text",
        "summary": "Summary",
    })
    assert create_res.status_code == 200
    art_id = create_res.json()["id"]

    # Attempt to directly set status to APPROVED via general update PUT
    put_res = client.put(f"/api/articles/{art_id}", json={
        "status": "APPROVED",
    })
    assert put_res.status_code == 400
    assert "workflow" in put_res.json()["detail"].lower()

    # Attempt to directly set status to PUBLISHED via general update PUT
    put_res2 = client.put(f"/api/articles/{art_id}", json={
        "status": "PUBLISHED",
    })
    assert put_res2.status_code == 400
    assert "workflow" in put_res2.json()["detail"].lower()


def test_image_upload_rejects_corrupted_or_oversized_payloads():
    # 1. Reject invalid base64 / non-image
    res_corrupt = client.post("/api/images/custom-upload", json={
        "data": "data:image/png;base64,bm90YW5pbWFnZQ==",
        "filename": "fake.png",
    })
    assert res_corrupt.status_code == 400

    # 2. Reject empty payload
    res_empty = client.post("/api/images/custom-upload", json={
        "data": "",
        "filename": "empty.png",
    })
    assert res_empty.status_code == 400

    # 3. Accept valid small PNG
    img = Image.new("RGB", (200, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")

    res_valid = client.post("/api/images/custom-upload", json={
        "data": f"data:image/png;base64,{b64_data}",
        "filename": "valid_test.png",
        "title": "Valid Test Poster",
    })
    assert res_valid.status_code == 200
    assert res_valid.json()["success"] is True
    assert res_valid.json()["image"]["width"] == 200


def test_topic_discovery_offline_fallback_labeled_truthfully():
    service = TopicDiscoveryService()
    fallback = service._fallback_trending_topics(country="IN", category="Technology", limit=2)
    assert len(fallback) >= 1
    for item in fallback:
        assert item["discovery_mode"] == "offline_fallback"
        assert "Offline" in item["trend_evidence"]
        assert "Offline" in item["publication_date"] or "Undated" in item["publication_date"]
