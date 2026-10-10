"""
Tests for Online/Offline AI Generation Modes, Strict Mode Separation,
Human-Quality Writing Guidelines, and Blogger Offline Guard.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.config import settings
from backend.services.ai_provider import (
    AIProviderManager,
    GeminiProvider,
    OllamaProvider,
    ConnectivityError,
    OllamaConnectionError,
    OllamaModelError,
    AIProviderError,
    ai_provider,
)
from backend.services.writer import writer_service
from backend.models.entities import Article, ArticleStatus
from backend.database import SessionLocal

client = TestClient(app)


# ==============================================================================
# Scenario 1: Online mode with valid API key and internet connection
# ==============================================================================
def test_scenario_1_online_mode_valid_key_and_internet():
    """Online mode generates articles using the cloud provider when online and valid."""
    manager = AIProviderManager()
    manager.set_mode("online")

    with patch("backend.services.ai_provider.check_internet_connection", return_value=True), \
         patch.object(manager.gemini_provider, "generate_text", return_value=("Natural human-style article content about solar energy with nuanced insights.", 100, 250)):
        
        text, in_tok, out_tok = manager.generate_text("Explain solar panel mechanics")
        assert "solar energy" in text
        assert in_tok == 100
        assert out_tok == 250
        assert manager.active_mode == "online"


# ==============================================================================
# Scenario 2: Online mode with no internet connection
# ==============================================================================
def test_scenario_2_online_mode_no_internet_raises_clear_error():
    """Online mode with no internet fails immediately with required offline message."""
    manager = AIProviderManager()
    manager.set_mode("online")

    with patch("backend.services.ai_provider.check_internet_connection", return_value=False):
        with pytest.raises(ConnectivityError) as exc_info:
            manager.generate_text("Write an article about AI")
        
        expected_msg = "You're offline. Connect to the internet or switch to Offline AI and connect Ollama."
        assert expected_msg in str(exc_info.value)

    # Also test via the API endpoint
    with patch("backend.services.ai_provider.check_internet_connection", return_value=False):
        response = client.post("/api/articles/start-workflow", json={"custom_title": "Test Offline Guard"})
        assert response.status_code == 503
        data = response.json()
        assert "You're offline" in data["detail"]


# ==============================================================================
# Scenario 3: Online mode with invalid API key (no silent fallback)
# ==============================================================================
def test_scenario_3_online_mode_invalid_api_key_no_silent_fallback():
    """Online mode with an invalid API key raises AIProviderError and never falls back silently."""
    provider = GeminiProvider()
    
    with patch("backend.services.ai_provider.check_internet_connection", return_value=True):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("API_KEY_INVALID: Provided API key is invalid")
        provider._client = mock_client
        
        with pytest.raises(AIProviderError) as exc_info:
            provider.generate_text("Test prompt")
        
        assert "Invalid API key" in str(exc_info.value) or "API_KEY_INVALID" in str(exc_info.value)


# ==============================================================================
# Scenario 4: Offline mode with Ollama running and model installed
# ==============================================================================
def test_scenario_4_offline_mode_ollama_running_and_model_installed():
    """Offline mode queries local Ollama endpoint without touching cloud AI."""
    manager = AIProviderManager()
    manager.set_mode("offline")
    settings.OLLAMA_MODEL = "llama3.2"

    mock_chat_response = MagicMock()
    mock_chat_response.status_code = 200
    mock_chat_response.json.return_value = {
        "message": {"content": "Locally generated article about rust programming language."},
        "prompt_eval_count": 45,
        "eval_count": 120,
    }

    healthy_status = {
        "healthy": True,
        "connected": True,
        "base_url": "http://localhost:11434",
        "model": "llama3.2",
        "installed_models": ["llama3.2", "mistral"],
        "message": "Offline AI ready with Ollama (llama3.2)",
    }

    with patch.object(manager.ollama_provider, "check_health", return_value=healthy_status), \
         patch("requests.post", return_value=mock_chat_response):
        
        text, in_tok, out_tok = manager.generate_text("Rust memory safety")
        assert "Locally generated" in text
        assert in_tok == 45
        assert out_tok == 120
        assert manager.active_mode == "offline"


# ==============================================================================
# Scenario 5: Offline mode with Ollama stopped (setup instructions & no fallback)
# ==============================================================================
def test_scenario_5_offline_mode_ollama_stopped_shows_setup_instructions():
    """Offline mode when Ollama is unreachable stops and provides setup guide without online fallback."""
    manager = AIProviderManager()
    manager.set_mode("offline")

    disconnected_status = {
        "healthy": False,
        "connected": False,
        "base_url": "http://localhost:11434",
        "model": "llama3.2",
        "message": "Ollama is disconnected or unavailable at http://localhost:11434. Please start Ollama by running 'ollama serve'.",
    }

    with patch.object(manager.ollama_provider, "check_health", return_value=disconnected_status):
        with pytest.raises(OllamaConnectionError) as exc_info:
            manager.generate_text("Test Ollama offline")
        
        err_msg = str(exc_info.value)
        assert "Ollama is disconnected or unavailable" in err_msg
        assert "http://localhost:11434" in err_msg
        assert "ollama serve" in err_msg


# ==============================================================================
# Scenario 6: Offline mode with no models installed
# ==============================================================================
def test_scenario_6_offline_mode_no_models_installed():
    """Offline mode when Ollama has no models or selected model is missing raises OllamaModelError."""
    manager = AIProviderManager()
    manager.set_mode("offline")
    settings.OLLAMA_MODEL = "llama3.2"

    unhealthy_status = {
        "healthy": False,
        "connected": True,
        "base_url": "http://localhost:11434",
        "model": "llama3.2",
        "installed_models": [],
        "message": "Ollama is running at http://localhost:11434, but NO models are installed. Please run 'ollama pull llama3.2' in your terminal.",
    }

    with patch.object(manager.ollama_provider, "check_health", return_value=unhealthy_status):
        with pytest.raises(OllamaModelError) as exc_info:
            manager.generate_text("Test missing model")
        
        err_msg = str(exc_info.value)
        assert "ollama pull" in err_msg or "NO models are installed" in err_msg


# ==============================================================================
# Scenario 7: Mode switching updates provider and status
# ==============================================================================
def test_scenario_7_mode_switching_updates_active_provider_and_status():
    """Switching between online and offline modes updates the centralized manager seamlessly."""
    manager = AIProviderManager()
    manager.set_mode("online")
    assert manager.active_mode == "online"
    assert manager.get_active_provider() == manager.gemini_provider

    manager.set_mode("offline")
    assert manager.active_mode == "offline"
    assert manager.get_active_provider() == manager.ollama_provider

    # API endpoint settings update
    mock_health = {
        "healthy": True,
        "connected": True,
        "base_url": "http://127.0.0.1:11434",
        "model": "mistral",
        "installed_models": ["mistral"],
        "message": "Offline AI ready with Ollama (mistral)",
    }
    mock_gemini_health = {
        "healthy": True,
        "connected": True,
        "provider": "gemini",
        "message": "Online Gemini ready",
    }
    with patch.object(ai_provider.ollama_provider, "check_health", return_value=mock_health), \
         patch.object(ai_provider.gemini_provider, "check_health", return_value=mock_gemini_health):
        res = client.post("/api/settings/config", json={
            "ai_generation_mode": "offline",
            "ollama_base_url": "http://127.0.0.1:11434",
            "ollama_model": "mistral"
        })
        assert res.status_code == 200
        assert res.json()["config"]["ai_generation_mode"] == "offline"

        # Verify status endpoint reflects changes
        status_res = client.get("/api/settings/ai-status")
        assert status_res.status_code == 200
        data = status_res.json()
        assert data["ai_generation_mode"] == "offline"
        assert data["active_provider"] == "ollama"

        # Revert back to online
        res_revert = client.post("/api/settings/config", json={"ai_generation_mode": "online"})
        assert res_revert.status_code == 200
        assert res_revert.json()["config"]["ai_generation_mode"] == "online"


# ==============================================================================
# Scenario 8: Human-Quality Writing Guidelines & Automated Verification
# ==============================================================================
def test_scenario_8_human_quality_writing_verification():
    """Verify that writer service polishes robotic cliches and validates human quality."""
    cliche_draft = (
        "# Understanding Modern Machine Learning\n\n"
        "In today's fast-paced world, artificial intelligence is evolving rapidly across industries. "
        "It is no secret that organizations rely on neural networks. Let's delve into the intricate tapestry "
        "of machine learning algorithms that will revolutionize business operations worldwide.\n\n"
        "Modern deep learning architectures utilize multi-layered neural networks to extract high-dimensional "
        "representations from raw inputs. Rather than relying on rigid rules, these networks adapt statistical "
        "weights through gradient-based backpropagation across extensive training iterations.\n\n"
        "In conclusion, as we have seen throughout this comprehensive guide, the future is exceptionally bright."
    )

    polished_replacement = (
        "# Understanding Modern Machine Learning\n\n"
        "Machine learning models solve difficult pattern recognition problems by analyzing massive empirical datasets. "
        "Engineering teams apply deep neural networks across computer vision and natural language tasks.\n\n"
        "Modern deep learning architectures utilize multi-layered neural networks to extract high-dimensional "
        "representations from raw inputs. Rather than relying on rigid rules, these networks adapt statistical "
        "weights through gradient-based backpropagation across extensive training iterations.\n\n"
        "Practitioners focus on precision, latency constraints, and reproducible validation pipelines."
    )

    with patch.object(ai_provider, "generate_text", return_value=(polished_replacement, 60, 180)):
        cleaned, p_in, p_out = writer_service.verify_and_polish_article(
            cliche_draft,
            title="Understanding Modern Machine Learning"
        )
        
        # Robotic openers and cliches should be removed or cleaned
        assert "In today's fast-paced world" not in cleaned
        assert "delve into" not in cleaned
        assert "tapestry" not in cleaned
        assert "In conclusion, as we have seen" not in cleaned
        assert cleaned.startswith("# Understanding Modern Machine Learning")
        assert len(cleaned) > 200


# ==============================================================================
# Scenario 9: Blogger Offline Guard & Draft Local Persistence
# ==============================================================================
def test_scenario_9_blogger_offline_publishing_guard():
    """Verify that publishing to Blogger when offline is blocked with a 503 while preserving local draft."""
    settings.DEMO_MODE = False
    db = SessionLocal()
    article = Article(
        title="Offline Draft Test Article",
        content="# Content for draft\n\nUseful human-quality content.",
        overall_quality_score=92.0,
        status=ArticleStatus.DRAFT
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    article_id = article.id
    db.close()

    try:
        # When offline, attempt to push draft to Blogger
        with patch("backend.services.ai_provider.check_internet_connection", return_value=False):
            res = client.post("/api/blogger/create-draft", json={"article_id": article_id})
            assert res.status_code == 503
            assert "active internet connection" in res.json()["detail"]
            assert "saved locally" in res.json()["detail"] or "preserved locally" in res.json()["detail"]

        # When offline, attempt to publish to Blogger
        with patch("backend.services.ai_provider.check_internet_connection", return_value=False):
            res_pub = client.post("/api/blogger/publish", json={"article_id": article_id, "confirm_publish": True})
            assert res_pub.status_code == 503
            assert "active internet connection" in res_pub.json()["detail"]
            assert "preserved locally" in res_pub.json()["detail"]

        # Verify draft is still intact locally in database
        db = SessionLocal()
        persisted = db.query(Article).filter(Article.id == article_id).first()
        assert persisted is not None
        assert persisted.title == "Offline Draft Test Article"
        assert persisted.status == ArticleStatus.DRAFT
        db.close()
    finally:
        db = SessionLocal()
        db.query(Article).filter(Article.id == article_id).delete()
        db.commit()
        db.close()
