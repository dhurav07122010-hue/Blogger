"""
Configuration module for Blogger AI Agent.
Handles environment variables, startup validation, and secret masking.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv

# Load .env if present
BASE_DIR = Path(__file__).resolve().parent.parent

# Support user data directory override for desktop packaging
if os.getenv("BLOGGER_DATA_DIR"):
    DATA_DIR = Path(os.environ["BLOGGER_DATA_DIR"]).resolve()
else:
    DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

if os.getenv("BLOGGER_ENV_FILE") and Path(os.environ["BLOGGER_ENV_FILE"]).exists():
    ENV_FILE = Path(os.environ["BLOGGER_ENV_FILE"]).resolve()
else:
    ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)


def mask_secret(secret: Optional[str], show_prefix: int = 4, show_suffix: int = 2) -> str:
    """Mask a secret key to prevent accidental leakage in logs and UI."""
    if not secret:
        return ""
    s = str(secret).strip()
    if len(s) <= 8:
        return "********"
    prefix = s[:show_prefix]
    suffix = s[-show_suffix:] if show_suffix > 0 else ""
    return f"{prefix}...{suffix}"


class Settings:
    def __init__(self):
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
        self.GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
        # AI Generation Mode: "online" (default, cloud AI) | "offline" (Ollama required)
        self.AI_GENERATION_MODE: str = os.getenv("AI_GENERATION_MODE", "online").strip().lower()
        if self.AI_GENERATION_MODE not in ("online", "offline"):
            self.AI_GENERATION_MODE = "online"
        self.OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/")
        self.OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2").strip()

        # Web Image Search configuration (Strict relevance by default, AI image gen removed)
        self.IMAGE_SOURCE: str = os.getenv("IMAGE_SOURCE", "web").strip().lower()
        self.IMAGE_AUTO_SELECT: bool = os.getenv("IMAGE_AUTO_SELECT", "true").strip().lower() in ("true", "1", "yes")
        self.IMAGE_MIN_RELEVANCE: str = os.getenv("IMAGE_MIN_RELEVANCE", "strict").strip().lower()
        
        # Internet Search & Research Provider configuration
        self.SEARCH_PROVIDER: str = os.getenv("SEARCH_PROVIDER", "auto").strip().lower()
        self.SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "").strip()
        self.TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "").strip()
        self.TRENDS_GEO: str = os.getenv("TRENDS_GEO", "IN").strip().upper()

        # Support both GOOGLE_CLIENT_ID and BLOGGER_CLIENT_ID aliases
        self.GOOGLE_CLIENT_ID: str = (os.getenv("BLOGGER_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID", "")).strip()
        self.GOOGLE_CLIENT_SECRET: str = (os.getenv("BLOGGER_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET", "")).strip()
        self.BLOGGER_REFRESH_TOKEN: str = os.getenv("BLOGGER_REFRESH_TOKEN", "").strip()
        self.GOOGLE_REDIRECT_URI: str = os.getenv(
            "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/blogger/oauth2callback"
        ).strip()
        self.BLOGGER_BLOG_ID: str = os.getenv("BLOGGER_BLOG_ID", "").strip()

        # Safety: auto-publish is strictly false by default
        raw_auto_publish = os.getenv("AUTO_PUBLISH", "false").strip().lower()
        self.AUTO_PUBLISH: bool = raw_auto_publish in ("true", "1", "yes")

        # Quality Gate: default 85/100
        try:
            self.QUALITY_THRESHOLD: int = int(os.getenv("QUALITY_THRESHOLD", "85"))
        except ValueError:
            self.QUALITY_THRESHOLD = 85

        # Demo Mode: if True, all AI and Blogger operations can run simulated or fallback
        raw_demo = os.getenv("DEMO_MODE", "true").strip().lower()
        self.DEMO_MODE: bool = raw_demo in ("true", "1", "yes")

        self.HOST: str = os.getenv("HOST", "127.0.0.1")
        self.PORT: int = int(os.getenv("PORT", "8000"))

        # Safely resolve database URL:
        # If relative path or BLOGGER_DATA_DIR is provided, always anchor database in DATA_DIR
        raw_db_url = os.getenv("DATABASE_URL", "").strip()
        if not raw_db_url or "sqlite:///./data" in raw_db_url or "sqlite:///data" in raw_db_url or os.getenv("BLOGGER_DATA_DIR"):
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            db_file = (DATA_DIR / "blogger_agent.db").resolve().as_posix()
            self.DATABASE_URL: str = f"sqlite:///{db_file}"
        else:
            self.DATABASE_URL = raw_db_url

        self.DATA_DIR: Path = DATA_DIR
        self.BASE_DIR: Path = BASE_DIR

    def validate_startup(self) -> List[str]:
        """
        Validate settings on application startup.
        Returns a list of warnings or non-fatal configuration gaps.
        Never reveals secret tokens in output.
        """
        warnings: List[str] = []

        if self.AI_GENERATION_MODE == "online":
            if not self.GEMINI_API_KEY:
                warnings.append(
                    "GEMINI_API_KEY is not configured for Online AI mode. Please configure your API key in Settings or switch to Offline AI (Ollama)."
                )
        elif self.AI_GENERATION_MODE == "offline":
            warnings.append(
                f"Offline AI Mode is active. Requires Ollama running at {self.OLLAMA_BASE_URL} with model '{self.OLLAMA_MODEL}'."
            )

        if not self.GOOGLE_CLIENT_ID or not self.GOOGLE_CLIENT_SECRET:
            warnings.append(
                "Google OAuth credentials (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET) not set. Blogger integration will run in simulated draft mode."
            )

        if not self.BLOGGER_BLOG_ID:
            warnings.append(
                "BLOGGER_BLOG_ID is not configured. You can select your blog after Google OAuth login or use demo blog ID."
            )

        if self.AUTO_PUBLISH:
            warnings.append(
                "CAUTION: AUTO_PUBLISH is enabled in environment variables. Note that articles must still pass all quality gates (>= %d score)."
                % self.QUALITY_THRESHOLD
            )

        return warnings

    def get_safe_summary(self) -> Dict[str, Any]:
        """
        Produce a safe dictionary for dashboard/settings UI without leaking credentials.
        """
        return {
            "has_gemini_key": bool(self.GEMINI_API_KEY),
            "gemini_key_preview": mask_secret(self.GEMINI_API_KEY) if self.GEMINI_API_KEY else "Not configured",
            "gemini_model": self.GEMINI_MODEL,
            "ai_generation_mode": self.AI_GENERATION_MODE,
            "ollama_base_url": self.OLLAMA_BASE_URL,
            "ollama_model": self.OLLAMA_MODEL,
            "has_oauth_client_id": bool(self.GOOGLE_CLIENT_ID),
            "has_oauth_client_secret": bool(self.GOOGLE_CLIENT_SECRET),
            "blogger_blog_id": self.BLOGGER_BLOG_ID if self.BLOGGER_BLOG_ID else "None",
            "auto_publish": self.AUTO_PUBLISH,
            "quality_threshold": self.QUALITY_THRESHOLD,
            "demo_mode": self.DEMO_MODE,
            "image_source": self.IMAGE_SOURCE,
            "image_auto_select": self.IMAGE_AUTO_SELECT,
            "image_min_relevance": self.IMAGE_MIN_RELEVANCE,
            "search_provider": self.SEARCH_PROVIDER,
            "has_serpapi_key": bool(self.SERPAPI_API_KEY),
            "serpapi_key_preview": mask_secret(self.SERPAPI_API_KEY) if self.SERPAPI_API_KEY else "Not configured",
            "has_tavily_key": bool(self.TAVILY_API_KEY),
            "tavily_key_preview": mask_secret(self.TAVILY_API_KEY) if self.TAVILY_API_KEY else "Not configured",
            "trends_geo": self.TRENDS_GEO,
            "database_path": str(self.DATABASE_URL),
            "warnings": self.validate_startup(),
        }


settings = Settings()
