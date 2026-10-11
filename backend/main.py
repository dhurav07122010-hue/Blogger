"""
FastAPI application entrypoint for Blogger AI Agent.
Coordinates database initialization, API routers, and static frontend serving.
Optimized for low-resource Windows workstations (8GB RAM, Intel i5).
"""

import logging
import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import init_db
from backend.routers import (
    dashboard_router,
    topics_router,
    research_router,
    articles_router,
    quality_router,
    blogger_router,
    settings_router,
    images_router,
)

# Configure clean logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("blogger_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence
    logger.info("Initializing Blogger AI Agent database...")
    init_db()

    # Run startup security & configuration validation
    warnings = settings.validate_startup()
    for w in warnings:
        logger.warning(f"Startup Notice: {w}")

    logger.info(
        f"Blogger AI Agent ready. Host: {settings.HOST}:{settings.PORT} | Demo Mode: {settings.DEMO_MODE} | Auto-Publish: {settings.AUTO_PUBLISH}"
    )
    yield
    # Shutdown sequence
    logger.info("Shutting down Blogger AI Agent...")


app = FastAPI(
    title="Blogger AI Agent",
    description="Production-grade AI-assisted blogging system prioritizing originality, accuracy, and Blogger-safe workflows.",
    version="1.0.0",
    lifespan=lifespan,
)

# Restrict CORS to legitimate local frontend origins
ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Prevent stale caching of frontend JS/CSS/HTML
@app.middleware("http")
async def add_cache_control_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Register API Routers
app.include_router(dashboard_router)
app.include_router(topics_router)
app.include_router(research_router)
app.include_router(articles_router)
app.include_router(quality_router)
app.include_router(blogger_router)
app.include_router(settings_router)
app.include_router(images_router)

# Mount frontend assets
def resolve_frontend_dir() -> Path:
    if os.getenv("FRONTEND_DIR") and Path(os.environ["FRONTEND_DIR"]).exists():
        return Path(os.environ["FRONTEND_DIR"])
    candidates = [
        settings.BASE_DIR / "frontend",
        Path(__file__).resolve().parent.parent / "frontend",
    ]
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidates.insert(0, Path(sys._MEIPASS) / "frontend")
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "frontend")
        candidates.append(exe_dir / "_internal" / "frontend")
    for p in candidates:
        if p.exists() and (p / "index.html").exists():
            return p
    return settings.BASE_DIR / "frontend"

FRONTEND_DIR = resolve_frontend_dir()
UPLOADS_DIR = FRONTEND_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/")
def serve_index():
    """Serve single-page frontend application."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(
        {
            "status": "online",
            "name": "Blogger AI Agent API",
            "docs": "/docs",
            "message": "Frontend index.html is being prepared.",
        }
    )


import time
SERVER_START_TIME = time.time()

@app.get("/api/health")
def health_check():
    """Health check endpoint with live database probe and uptime."""
    db_status = "connected"
    try:
        from backend.database import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)[:80]}"

    blogger_token_exists = (settings.DATA_DIR / "blogger_token.json").exists() or (settings.BASE_DIR / "data" / "blogger_token.json").exists()

    return {
        "status": "healthy" if "unhealthy" not in db_status else "degraded",
        "uptime_seconds": round(time.time() - SERVER_START_TIME, 1),
        "demo_mode": settings.DEMO_MODE,
        "database": db_status,
        "auto_publish": settings.AUTO_PUBLISH,
        "quality_threshold": settings.QUALITY_THRESHOLD,
        "ai_generation_mode": settings.AI_GENERATION_MODE,
        "search_provider": settings.SEARCH_PROVIDER,
        "blogger_token_detected": blogger_token_exists,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )
