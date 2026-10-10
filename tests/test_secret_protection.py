"""
Tests ensuring secret protection: zero leakage of API keys, OAuth secrets, or tokens in UI, logs, or responses.
"""

from backend.config import settings


def test_api_config_endpoint_masks_secrets(client):
    test_secret_key = "AIzaSyFakeKeyForTestOnly123456789"
    settings.GEMINI_API_KEY = test_secret_key

    response = client.get("/api/settings/config")
    assert response.status_code == 200
    data = response.json()

    # Raw secret must NEVER appear anywhere in the response JSON
    raw_response_str = response.text
    assert test_secret_key not in raw_response_str
    assert data["has_gemini_key"] is True
    assert "AIza...89" in data["gemini_key_preview"] or "********" in data["gemini_key_preview"]


def test_logs_endpoint_contains_no_secrets(client):
    secret_token = "GOCSPX-secretOAuthToken12345"
    settings.GOOGLE_CLIENT_SECRET = secret_token

    response = client.get("/api/settings/logs")
    assert response.status_code == 200
    assert secret_token not in response.text


def test_dashboard_stats_endpoint_contains_no_secrets(client):
    test_key = "AIzaSyConfidentialKey987654321"
    settings.GEMINI_API_KEY = test_key

    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    assert test_key not in response.text
