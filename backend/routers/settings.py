"""
Settings and System Logs Router for Blogger AI Agent.
Exposes safe configuration visibility, threshold modifications, and sanitized audit logs.
"""

from typing import List, Dict, Any, Optional
import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.entities import AgentRun, AppSetting
from backend.services.gemini import tracker
from backend.config import settings

from backend.services.ai_provider import ai_provider

router = APIRouter(prefix="/api/settings", tags=["Settings"])


class SettingsUpdatePayload(BaseModel):
    quality_threshold: Optional[int] = None
    demo_mode: Optional[bool] = None
    auto_publish: Optional[bool] = None
    blogger_blog_id: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    ai_generation_mode: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    image_source: Optional[str] = None
    image_auto_select: Optional[bool] = None
    image_min_relevance: Optional[str] = None
    search_provider: Optional[str] = None
    serpapi_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    trends_geo: Optional[str] = None
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None


@router.get("/config")
def get_safe_configuration():
    """Retrieve runtime settings summary without leaking sensitive credentials."""
    return settings.get_safe_summary()


@router.get("/ai-status")
def get_ai_status():
    """Check connectivity, active AI generation mode, and provider health."""
    return ai_provider.check_health()


@router.get("/ollama-models")
def get_ollama_models():
    """Fetch installed models from local Ollama service."""
    models = ai_provider.ollama_provider.get_available_models()
    return {
        "success": True,
        "models": models,
        "base_url": settings.OLLAMA_BASE_URL,
    }


@router.post("/config")
def update_runtime_configuration(payload: SettingsUpdatePayload, db: Session = Depends(get_db)):
    """Update runtime parameters (threshold, demo mode, default blog, Gemini model, AI mode, Ollama, image search)."""
    if payload.quality_threshold is not None:
        settings.QUALITY_THRESHOLD = max(50, min(100, payload.quality_threshold))
    if payload.demo_mode is not None:
        settings.DEMO_MODE = payload.demo_mode
    if payload.auto_publish is not None:
        settings.AUTO_PUBLISH = payload.auto_publish
    if payload.blogger_blog_id is not None:
        settings.BLOGGER_BLOG_ID = payload.blogger_blog_id.strip()
    if payload.gemini_api_key is not None and payload.gemini_api_key.strip():
        settings.GEMINI_API_KEY = payload.gemini_api_key.strip()
        ai_provider.gemini_provider.refresh_credentials()
    if payload.gemini_model is not None and payload.gemini_model.strip():
        settings.GEMINI_MODEL = payload.gemini_model.strip()
    if payload.ai_generation_mode is not None:
        mode_val = payload.ai_generation_mode.strip().lower()
        if mode_val in ("online", "offline"):
            ai_provider.set_mode(mode_val)
    if payload.ollama_base_url is not None and payload.ollama_base_url.strip():
        settings.OLLAMA_BASE_URL = payload.ollama_base_url.strip().rstrip("/")
    if payload.ollama_model is not None and payload.ollama_model.strip():
        settings.OLLAMA_MODEL = payload.ollama_model.strip()
    if payload.image_source is not None:
        settings.IMAGE_SOURCE = payload.image_source.strip().lower()
    if payload.image_auto_select is not None:
        settings.IMAGE_AUTO_SELECT = payload.image_auto_select
    if payload.image_min_relevance is not None:
        settings.IMAGE_MIN_RELEVANCE = payload.image_min_relevance.strip().lower()
    if payload.search_provider is not None:
        settings.SEARCH_PROVIDER = payload.search_provider.strip().lower()
    if payload.serpapi_api_key is not None:
        settings.SERPAPI_API_KEY = payload.serpapi_api_key.strip()
    if payload.tavily_api_key is not None:
        settings.TAVILY_API_KEY = payload.tavily_api_key.strip()
    if payload.trends_geo is not None and payload.trends_geo.strip():
        settings.TRENDS_GEO = payload.trends_geo.strip().upper()
    if payload.google_client_id is not None and payload.google_client_id.strip():
        settings.GOOGLE_CLIENT_ID = payload.google_client_id.strip()
    if payload.google_client_secret is not None and payload.google_client_secret.strip():
        settings.GOOGLE_CLIENT_SECRET = payload.google_client_secret.strip()

    return {
        "success": True,
        "message": "Settings updated successfully.",
        "config": settings.get_safe_summary(),
        "ai_status": ai_provider.check_health(),
    }


@router.post("/test/gemini")
def test_gemini_connection():
    """Test connection directly against Gemini API."""
    from backend.services.ai_provider import check_internet_connection
    if not check_internet_connection():
        return {
            "status": "error",
            "message": "Device is offline. Connect to the internet to test Gemini API.",
            "last_tested": time.time(),
        }
    if not settings.GEMINI_API_KEY:
        return {
            "status": "missing",
            "message": "GEMINI_API_KEY is not configured.",
            "last_tested": time.time(),
        }
    try:
        from backend.services.gemini import gemini_service
        text, in_tok, out_tok = gemini_service.generate_text(
            prompt="Respond with exact text: 'Gemini connection verified.'",
            temperature=0.0,
        )
        return {
            "status": "connected",
            "message": f"Gemini API verified successfully: {text[:60].strip()}",
            "model": settings.GEMINI_MODEL,
            "last_tested": time.time(),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Gemini connection failed: {str(e)[:140]}",
            "last_tested": time.time(),
        }


@router.post("/test/search")
def test_search_integration():
    """Test connection and search results from configured research provider."""
    from backend.services.search_engine import live_research_engine
    return live_research_engine.test_search_provider()


@router.post("/test/trends")
def test_trends_integration():
    """Test Google Trends RSS / search trends feed connectivity."""
    from backend.services.topic_discovery import topic_discovery_service
    geo = getattr(settings, "TRENDS_GEO", "IN")
    trends = topic_discovery_service.discover_trending(country=geo, category="Technology", limit=3)
    if trends:
        return {
            "status": "connected",
            "message": f"Successfully received {len(trends)} trending topics for region {geo}.",
            "region": geo,
            "sample_topic": trends[0].get("title", ""),
            "evidence": trends[0].get("trend_evidence", ""),
            "last_tested": time.time(),
        }
    return {
        "status": "error",
        "message": f"Could not retrieve live trends for region {geo}.",
        "last_tested": time.time(),
    }


@router.post("/test/blogger")
def test_blogger_integration():
    """Test Google Blogger API v3 connectivity and OAuth authorization."""
    from backend.services.blogger import blogger_service
    is_cfg = blogger_service.is_oauth_configured()
    if not is_cfg:
        return {
            "status": "missing",
            "message": "Google OAuth credentials (Client ID / Client Secret) not set.",
            "last_tested": time.time(),
        }
    is_auth = blogger_service.is_authenticated()
    if not is_auth:
        return {
            "status": "unauthenticated",
            "message": "OAuth configured but user is not logged in. Click 'Connect Google OAuth'.",
            "last_tested": time.time(),
        }
    blogs = blogger_service.list_blogs()
    if blogs:
        blog_name = blogs[0].get("name", "Blogger Blog")
        blog_id = blogs[0].get("id", "")
        return {
            "status": "connected",
            "message": f"Connected to Blogger blog '{blog_name}' (ID: {blog_id}).",
            "blog_name": blog_name,
            "blog_id": blog_id,
            "blogs_count": len(blogs),
            "last_tested": time.time(),
        }
    return {
        "status": "error",
        "message": "Authenticated with Google, but unable to list Blogger blogs. Check permissions.",
        "last_tested": time.time(),
    }


@router.get("/logs")
def get_system_and_agent_logs(limit: int = 50, db: Session = Depends(get_db)):
    """Retrieve sanitized agent run logs and token usage metrics."""
    runs = db.query(AgentRun).order_by(AgentRun.id.desc()).limit(limit).all()
    logs_data = [
        {
            "id": r.id,
            "article_id": r.article_id,
            "agent_name": r.agent_name,
            "status": r.status,
            "input_tokens_est": r.input_tokens_est,
            "output_tokens_est": r.output_tokens_est,
            "execution_time_seconds": r.execution_time_seconds,
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]

    return {
        "agent_runs": logs_data,
        "usage_tracker": tracker.get_summary(),
        "warnings": settings.validate_startup(),
    }
