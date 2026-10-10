"""
Dashboard Router for Blogger AI Agent.
Provides aggregate metrics, status distributions, and recent activity logs.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.entities import Article, QualityCheck, AgentRun, ArticleStatus
from backend.models.schemas import DashboardStats
from backend.services.gemini import tracker
from backend.config import settings

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Fetch overview metrics for the main dashboard."""
    articles_created = db.query(Article).count()
    drafts_count = db.query(Article).filter(Article.status.in_([ArticleStatus.DRAFT, ArticleStatus.IDEA])).count()
    awaiting_approval = db.query(Article).filter(Article.status == ArticleStatus.READY_FOR_APPROVAL).count()
    published_count = db.query(Article).filter(Article.status == ArticleStatus.PUBLISHED).count()
    failed_quality_checks = db.query(QualityCheck).filter(QualityCheck.passed == False).count()
    
    # Real image count
    images_count = db.query(Article).filter(Article.featured_image != None, Article.featured_image != {}).count()

    from backend.services.blogger import blogger_service
    gemini_ok = bool(settings.GEMINI_API_KEY)
    blogger_ok = blogger_service.is_authenticated()

    recent_runs = (
        db.query(AgentRun)
        .order_by(AgentRun.id.desc())
        .limit(10)
        .all()
    )

    recent_runs_data = [
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
        for r in recent_runs
    ]

    usage_summary = tracker.get_summary()

    return DashboardStats(
        articles_created=articles_created,
        drafts_count=drafts_count,
        awaiting_approval=awaiting_approval,
        published_count=published_count,
        failed_quality_checks=failed_quality_checks,
        images_generated=images_count,
        gemini_connected=gemini_ok,
        blogger_connected=blogger_ok,
        recent_agent_runs=recent_runs_data,
        total_tokens_est=usage_summary.get("total_tokens", 0),
        estimated_cost_usd=usage_summary.get("estimated_cost_usd", 0.0),
        demo_mode=settings.DEMO_MODE,
    )
