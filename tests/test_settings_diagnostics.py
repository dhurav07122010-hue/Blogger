import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_settings_diagnostics_gemini_endpoint():
    res = client.post("/api/settings/test/gemini")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert data["status"] in ["connected", "missing", "error"]
    assert "message" in data

def test_settings_diagnostics_search_endpoint():
    res = client.post("/api/settings/test/search")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert data["status"] in ["connected", "error"]
    assert "message" in data

def test_settings_diagnostics_trends_endpoint():
    res = client.post("/api/settings/test/trends")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert data["status"] in ["connected", "error"]
    assert "message" in data

def test_settings_diagnostics_blogger_endpoint():
    res = client.post("/api/settings/test/blogger")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert data["status"] in ["connected", "not_authenticated", "error"]
    assert "message" in data

def test_topic_discovery_api_routes():
    res_trending = client.get("/api/topics/discover/trending?country=IN&category=Technology&limit=5")
    assert res_trending.status_code == 200
    trending_data = res_trending.json()
    assert isinstance(trending_data, list)

    res_random = client.get("/api/topics/discover/random?category=Technology&difficulty=Beginner&limit=3")
    assert res_random.status_code == 200
    random_data = res_random.json()
    assert isinstance(random_data, list)
    assert len(random_data) <= 3
