from backend.routers.dashboard import router as dashboard_router
from backend.routers.topics import router as topics_router
from backend.routers.research import router as research_router
from backend.routers.articles import router as articles_router
from backend.routers.quality import router as quality_router
from backend.routers.blogger import router as blogger_router
from backend.routers.settings import router as settings_router
from backend.routers.images import router as images_router

__all__ = [
    "dashboard_router",
    "topics_router",
    "research_router",
    "articles_router",
    "quality_router",
    "blogger_router",
    "settings_router",
    "images_router",
]
