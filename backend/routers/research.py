"""
Research Router for Blogger AI Agent.
Exposes research dossier generation and authoritative source inspection.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.entities import ResearchSource, Topic
from backend.models.schemas import ResearchSourceCreate, ResearchSourceRead
from backend.services.research import research_analyst

router = APIRouter(prefix="/api/research", tags=["Research"])


@router.get("/sources", response_model=List[ResearchSourceRead])
def list_sources(topic_id: Optional[int] = None, article_id: Optional[int] = None, db: Session = Depends(get_db)):
    """List collected research sources, optionally filtered by topic or article."""
    query = db.query(ResearchSource)
    if topic_id:
        query = query.filter(ResearchSource.topic_id == topic_id)
    if article_id:
        query = query.filter(ResearchSource.article_id == article_id)
    return query.order_by(ResearchSource.id.desc()).all()


@router.post("/run-for-topic/{topic_id}")
def run_research_for_topic(topic_id: int, db: Session = Depends(get_db)):
    """Conduct research analyst investigation for a given topic."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    res_data = research_analyst.conduct_research(
        topic=topic.title,
        target_audience=topic.target_audience,
        country_region=topic.country_region,
        search_intent=topic.search_intent,
        desired_length=topic.desired_length,
        keywords=topic.keywords,
    )

    sources = res_data.get("sources", [])
    saved_count = 0
    for s in sources:
        # Determine verified status based on evidence rather than unconditionally marking true
        # A source is only verified if it has a valid accessible domain, title, and was independently confirmed
        verified = bool(s.get("is_verified", False))
        source_rec = ResearchSource(
            topic_id=topic.id,
            title=s.get("title", "Untitled Source"),
            url=s.get("url", ""),
            domain=s.get("domain", ""),
            publication_date=s.get("publication_date", ""),
            relevant_facts=s.get("relevant_facts", []),
            notes=s.get("notes", ""),
            is_verified=verified,
        )
        db.add(source_rec)
        saved_count += 1

    topic.status = "RESEARCHED"
    db.commit()

    return {
        "success": True,
        "topic_id": topic.id,
        "sources_found": saved_count,
        "research_summary": res_data.get("research_summary", ""),
        "live_internet_used": res_data.get("live_internet_used", False),
        "contradictions_or_caveats": res_data.get("contradictions_or_caveats", []),
        "sources": sources,
    }


@router.post("/sources", response_model=ResearchSourceRead)
def add_custom_source(source_in: ResearchSourceCreate, db: Session = Depends(get_db)):
    """Manually add a verified research citation."""
    source_rec = ResearchSource(
        topic_id=source_in.topic_id,
        article_id=source_in.article_id,
        title=source_in.title,
        url=source_in.url,
        domain=source_in.domain,
        publication_date=source_in.publication_date,
        relevant_facts=source_in.relevant_facts,
        notes=source_in.notes,
        is_verified=source_in.is_verified,
    )
    db.add(source_rec)
    db.commit()
    db.refresh(source_rec)
    return source_rec
