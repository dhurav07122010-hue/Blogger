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

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "demo_mode": settings.DEMO_MODE,
        "database": "connected",
        "auto_publish": settings.AUTO_PUBLISH,
        "quality_threshold": settings.QUALITY_THRESHOLD,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )
