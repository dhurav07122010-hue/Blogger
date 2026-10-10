"""
Comprehensive test suite for the Web Image Search & Relevance Filtering System.
Verifies:
- Pluggable ImageSearchProvider interface (searchImages, getImageDetails, validateImage)
- Structured image-search request generation (descriptive visual subject query, 2-4 search queries, no title repeating)
- Relevance scoring (0-100) and strict exclusion of unrelated concepts (grocery stores, portraits, etc.)
- The 6 required test topics:
  1. How AI Is Changing Education
  2. Minecraft 1.21 Features
  3. NVIDIA GPUs for AI
  4. How Solar Panels Work
  5. Best Programming Languages for Beginners
  6. Latest Space Exploration Technologies
- Custom search endpoint (/api/images/search)
- Image selection and removal endpoints
- Draft preservation and publishing compatibility
- Complete removal of AI image generation (Nano Banana / Gemini image generation no longer called)
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.image_search import (
    image_search_manager,
    ImageSearchProvider,
    WikimediaImageSearchProvider,
    OpenverseImageSearchProvider,
    CuratedTopicWebProvider,
)
from backend.models.entities import Article, ArticleStatus
from backend.database import SessionLocal

client = TestClient(app)


def test_image_search_provider_abstraction():
    """Verify ImageSearchProvider base class and interface methods."""
    class CustomMockProvider(ImageSearchProvider):
        def search_images(self, query: str, limit: int = 10):
            return [{"url": "https://example.com/test.jpg", "title": "Custom Test"}]
        def get_image_details(self, result):
            return result
        def validate_image(self, result):
            return True

    provider = CustomMockProvider()
    assert isinstance(provider, ImageSearchProvider)
    # Test camelCase aliases
    results = provider.searchImages("test query")
    assert len(results) == 1
    assert provider.validateImage(results[0]) is True
    details = provider.getImageDetails(results[0])
    assert details["title"] == "Custom Test"


def test_structured_search_request_generation():
    """Verify structured image-search request generation describes visual subject, not title repeating."""
    req = image_search_manager.generate_search_request(
        article_title="How AI Is Changing Education in 2026",
        article_content="Classroom students using artificial intelligence tools to learn mathematics and science.",
        keywords=["AI", "education", "schools"],
    )
    assert "article_topic" in req
    assert "image_query" in req
    assert "search_queries" in req
    assert len(req["search_queries"]) >= 2
    # Ensure visual query does not just repeat the title verbatim with noise words
    q = req["image_query"].lower()
    assert "article" not in q
    assert any(term in q for term in ["education", "classroom", "student", "intelligence", "technology"])


def test_relevance_scoring_rejects_unrelated():
    """Verify strict rejection of unrelated images (grocery store, food, portraits)."""
    search_req = {
        "article_topic": "New NVIDIA GPUs for AI",
        "subject": "NVIDIA GPU computing hardware",
        "keywords": ["nvidia", "gpu", "ai", "hardware"],
        "search_queries": ["NVIDIA GPU AI technology", "NVIDIA graphics card"],
    }

    # Highly relevant candidate
    good_candidate = {
        "title": "NVIDIA High-Performance GPU Accelerator Silicon Processor Die",
        "description": "Macro view of NVIDIA GPU silicon die engineered for artificial intelligence neural network computing",
        "width": 1280,
        "height": 720,
    }
    good_score = image_search_manager.score_image_relevance(good_candidate, search_req)
    assert good_score >= 70.0

    # Totally unrelated candidate: grocery store
    grocery_candidate = {
        "title": "Supermarket aisle with grocery store shopping cart shelves",
        "description": "Produce section with shoppers in a local grocery store",
        "width": 1280,
        "height": 720,
    }
    grocery_score = image_search_manager.score_image_relevance(grocery_candidate, search_req)
    assert grocery_score <= 15.0  # Strictly rejected

    # Unrelated portrait for tech topic
    portrait_candidate = {
        "title": "Historic portrait statue of 19th century president",
        "description": "Stone sculpture of president in cemetery park",
        "width": 800,
        "height": 1000,
    }
    portrait_score = image_search_manager.score_image_relevance(portrait_candidate, search_req)
    assert portrait_score <= 20.0


def test_custom_search_endpoint():
    """Verify custom search endpoint works as requested."""
    response = client.post(
        "/api/images/search",
        json={"query": "blue futuristic AI robot", "limit": 6},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "candidates" in data
    assert isinstance(data["candidates"], list)


def test_find_for_article_endpoint():
    """Verify /api/images/find-for-article returns scored candidates and licensing metadata."""
    response = client.post(
        "/api/images/find-for-article",
        json={
            "articleTitle": "How Solar Panels Work",
            "articleContent": "Photovoltaic cells converting photons from sunlight into clean electrical energy.",
            "keywords": ["solar energy", "photovoltaic", "renewable"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "candidates" in data
    assert len(data["candidates"]) > 0

    top = data["candidates"][0]
    assert "url" in top
    assert "sourceUrl" in top
    assert "sourceName" in top
    assert "license" in top
    assert top.get("relevanceScore", 0) >= 50.0
    # Must preserve licensing info
    assert top["license"] != ""


# =========================================================================
# THE 6 REQUIRED TOPIC TESTS (VERIFYING RELEVANCE & NO UNRELATED SELECTION)
# =========================================================================

def test_topic_1_how_ai_is_changing_education():
    """1. How AI Is Changing Education"""
    res = image_search_manager.find_images_for_article(
        article_title="How AI Is Changing Education",
        article_content="Modern classrooms and students utilizing artificial intelligence tutoring systems.",
        auto_select=True,
        min_relevance="balanced",
    )
    assert res["success"] is True
    if res["suitableFound"]:
        selected = res["selectedImage"]
        assert selected is not None
        assert selected["relevanceScore"] >= 50.0
        text = (selected["title"] + " " + selected.get("description", "")).lower()
        # Must match education / classroom / technology
        assert any(w in text for w in ["education", "classroom", "student", "technology", "lab", "computer", "learning", "stem"])
        # MUST NOT be grocery or unrelated
        assert not any(w in text for w in ["grocery", "supermarket", "vegetable", "cart"])
    else:
        assert res["selectedImage"] is None


def test_topic_2_minecraft_121_features():
    """2. Minecraft 1.21 Features"""
    res = image_search_manager.find_images_for_article(
        article_title="Minecraft 1.21 Features",
        article_content="Trial chambers, Crafter automation block, and new Minecraft mobs in the latest update.",
        auto_select=True,
        min_relevance="strict",
    )
    assert res["success"] is True
    assert res["suitableFound"] is True
    selected = res["selectedImage"]
    assert selected is not None
    assert selected["relevanceScore"] >= 70.0
    text = (selected["title"] + " " + selected.get("description", "")).lower()
    # Must match Minecraft
    assert "minecraft" in text
    # MUST NOT be grocery or unrelated game
    assert not any(w in text for w in ["grocery", "supermarket", "fortnite", "roblox"])


def test_topic_3_nvidia_gpus_for_ai():
    """3. NVIDIA GPUs for AI"""
    res = image_search_manager.find_images_for_article(
        article_title="NVIDIA GPUs for AI",
        article_content="Tensor cores, memory bandwidth, and high-performance computing on NVIDIA GPUs for machine learning.",
        auto_select=True,
        min_relevance="balanced",
    )
    assert res["success"] is True
    if res["suitableFound"]:
        selected = res["selectedImage"]
        assert selected is not None
        assert selected["relevanceScore"] >= 50.0
        text = (selected["title"] + " " + selected.get("description", "")).lower()
        assert any(w in text for w in ["nvidia", "gpu", "graphics", "card", "hardware", "computing", "processor", "blade", "die", "chip"])
        assert not any(w in text for w in ["grocery", "supermarket", "produce", "shopping cart"])
    else:
        assert res["selectedImage"] is None


def test_topic_4_how_solar_panels_work():
    """4. How Solar Panels Work"""
    res = image_search_manager.find_images_for_article(
        article_title="How Solar Panels Work",
        article_content="Semiconductor materials and photovoltaic cells absorbing solar irradiance.",
        auto_select=True,
        min_relevance="balanced",
    )
    assert res["success"] is True
    if res["suitableFound"]:
        selected = res["selectedImage"]
        assert selected is not None
        assert selected["relevanceScore"] >= 50.0
        text = (selected["title"] + " " + selected.get("description", "")).lower()
        assert any(w in text for w in ["solar", "photovoltaic", "pv", "sunlight", "cells", "panel"])
        assert not any(w in text for w in ["grocery", "supermarket", "store"])
    else:
        assert res["selectedImage"] is None


def test_topic_5_best_programming_languages_for_beginners():
    """5. Best Programming Languages for Beginners"""
    res = image_search_manager.find_images_for_article(
        article_title="Best Programming Languages for Beginners",
        article_content="Python, JavaScript, clean syntax, and software development fundamentals.",
        auto_select=True,
        min_relevance="balanced",
    )
    assert res["success"] is True
    if res["suitableFound"]:
        selected = res["selectedImage"]
        assert selected is not None
        assert selected["relevanceScore"] >= 50.0
        text = (selected["title"] + " " + selected.get("description", "")).lower()
        assert any(w in text for w in ["code", "programming", "python", "software", "syntax", "developer", "monitor"])
        assert not any(w in text for w in ["grocery", "supermarket", "fruit"])
    else:
        assert res["selectedImage"] is None


def test_topic_6_latest_space_exploration_technologies():
    """6. Latest Space Exploration Technologies"""
    res = image_search_manager.find_images_for_article(
        article_title="Latest Space Exploration Technologies",
        article_content="Spacecraft propulsion, planetary rovers, orbital rockets, and NASA deep space exploration instruments.",
        auto_select=True,
        min_relevance="balanced",
    )
    assert res["success"] is True
    if res["suitableFound"]:
        selected = res["selectedImage"]
        assert selected is not None
        assert selected["relevanceScore"] >= 50.0
        text = (selected["title"] + " " + selected.get("description", "")).lower()
        assert any(w in text for w in ["space", "spacecraft", "rover", "rocket", "nasa", "propulsion", "orbital", "mars"])
        assert not any(w in text for w in ["grant", "civil war", "grocery", "supermarket"])
    else:
        assert res["selectedImage"] is None
    assert not any(w in text for w in ["grant", "civil war", "grocery", "supermarket"])


def test_article_persistence_and_publishing():
    """Verify featuredImage survives draft saving, updates, and publishing formatting."""
    db = SessionLocal()
    try:
        article = Article(
            title="Comprehensive Guide to Modern Solar Power",
            content="Photovoltaic panels are becoming widely adopted across residential and commercial buildings.",
            status=ArticleStatus.DRAFT,
            featured_image={
                "url": "https://upload.wikimedia.org/wikipedia/commons/test_solar.jpg",
                "thumbnailUrl": "https://upload.wikimedia.org/wikipedia/commons/test_solar_thumb.jpg",
                "sourceUrl": "https://commons.wikimedia.org/wiki/File:test_solar.jpg",
                "sourceName": "Wikimedia Commons",
                "title": "Solar Photovoltaic Rooftop Array",
                "author": "Jane Solar",
                "license": "CC BY-SA 4.0",
                "query": "solar photovoltaic array",
                "relevanceScore": 92.0,
            }
        )
        db.add(article)
        db.commit()
        db.refresh(article)

        # 1. Fetch via API
        get_res = client.get(f"/api/articles/{article.id}")
        assert get_res.status_code == 200
        art_data = get_res.json()
        feat = art_data.get("featured_image", {})
        assert feat.get("url") == "https://upload.wikimedia.org/wikipedia/commons/test_solar.jpg"
        assert feat.get("author") == "Jane Solar"
        assert feat.get("license") == "CC BY-SA 4.0"

        # 2. Update via select-featured API
        new_image = {
            "url": "https://upload.wikimedia.org/wikipedia/commons/test_solar2.jpg",
            "sourceName": "Wikimedia Commons",
            "title": "Industrial Solar Park",
            "author": "John Engineer",
            "license": "Public domain",
            "relevanceScore": 95.0,
        }
        sel_res = client.post(
            "/api/images/select-featured",
            json={"articleId": article.id, "image": new_image},
        )
        assert sel_res.status_code == 200

        # 3. Verify update persisted
        db.refresh(article)
        assert article.featured_image.get("url") == "https://upload.wikimedia.org/wikipedia/commons/test_solar2.jpg"
        assert article.featured_image.get("author") == "John Engineer"

        # 4. Remove featured image
        rem_res = client.post(
            "/api/images/remove-featured",
            json={"articleId": article.id},
        )
        assert rem_res.status_code == 200
        db.refresh(article)
        assert article.featured_image == {}

        # Clean up
        db.delete(article)
        db.commit()
    finally:
        db.close()


def test_legacy_ai_image_route_redirects_to_search():
    """Verify legacy /api/ai/generate-image returns web image, NOT AI generated images."""
    res = client.post(
        "/api/ai/generate-image",
        json={"articleTitle": "NVIDIA GPUs for AI"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    # The image returned must be a real web URL (starting with http), NOT data:image/ generated by AI!
    assert data["image"].startswith("http")
    assert "data:image/svg+xml" not in data["image"]


def test_custom_upload_hero_poster():
    """Verify user can upload their own image for the hero poster."""
    import base64
    import io
    from PIL import Image as PILImage

    # Create a small valid test PNG image
    img = PILImage.new("RGB", (120, 80), color=(73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_data = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    db = SessionLocal()
    try:
        article = Article(
            title="Article With Custom Poster",
            content="Testing user uploaded custom poster.",
            status=ArticleStatus.DRAFT,
        )
        db.add(article)
        db.commit()
        db.refresh(article)

        # Upload custom hero poster
        res = client.post(
            "/api/images/custom-upload",
            json={
                "articleId": article.id,
                "filename": "my_custom_poster.png",
                "data": b64_data,
                "title": "My Custom Hero Poster",
                "author": "Alice Designer",
                "license": "Custom Permitted",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        saved = data["image"]
        assert saved["url"].startswith("/static/uploads/")
        assert saved["width"] == 120
        assert saved["height"] == 80
        assert saved["title"] == "My Custom Hero Poster"
        assert saved["author"] == "Alice Designer"
        assert saved["isCustom"] is True

        # Verify database record
        db.refresh(article)
        assert article.featured_image.get("url") == saved["url"]
        assert article.featured_image.get("title") == "My Custom Hero Poster"

        db.delete(article)
        db.commit()
    finally:
        db.close()


def test_custom_url_hero_poster():
    """Verify user can supply a direct image URL for the hero poster."""
    db = SessionLocal()
    try:
        article = Article(
            title="Article With Direct URL Poster",
            content="Testing user provided image URL.",
            status=ArticleStatus.DRAFT,
        )
        db.add(article)
        db.commit()
        db.refresh(article)

        res = client.post(
            "/api/images/custom-url",
            json={
                "articleId": article.id,
                "url": "https://example.com/my-poster.jpg",
                "title": "Custom Online Hero Poster",
                "author": "Bob Photographer",
                "license": "All Rights Reserved",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        saved = data["image"]
        assert saved["url"] == "https://example.com/my-poster.jpg"
        assert saved["title"] == "Custom Online Hero Poster"
        assert saved["author"] == "Bob Photographer"
        assert saved["isCustom"] is True

        db.refresh(article)
        assert article.featured_image.get("url") == "https://example.com/my-poster.jpg"

        db.delete(article)
        db.commit()
    finally:
        db.close()

