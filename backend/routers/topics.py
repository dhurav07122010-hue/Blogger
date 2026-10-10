"""
Topics Router for Blogger AI Agent.
Handles topic ideas, search intents, priority levels, and sample seeding.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.entities import Topic, ArticleStatus
from backend.models.schemas import TopicCreate, TopicRead

router = APIRouter(prefix="/api/topics", tags=["Topics"])


@router.get("", response_model=List[TopicRead])
def list_topics(db: Session = Depends(get_db)):
    """List all topic ideas ordered by priority and recency."""
    return db.query(Topic).order_by(Topic.id.desc()).all()


@router.post("", response_model=TopicRead)
def create_topic(topic_in: TopicCreate, db: Session = Depends(get_db)):
    """Add a new topic idea to the queue."""
    topic = Topic(
        project_id=topic_in.project_id,
        title=topic_in.title,
        target_audience=topic_in.target_audience,
        country_region=topic_in.country_region,
        search_intent=topic_in.search_intent,
        desired_length=topic_in.desired_length,
        keywords=topic_in.keywords,
        priority=topic_in.priority,
        notes=topic_in.notes or "",
        source=topic_in.source or "User",
        source_url=topic_in.source_url or "",
        discovery_mode=topic_in.discovery_mode or "manual",
        trend_evidence=topic_in.trend_evidence or "",
        estimated_difficulty=topic_in.estimated_difficulty or "Intermediate (Estimate)",
        audience_fit=topic_in.audience_fit or "High",
        article_potential=topic_in.article_potential or "High",
        category=topic_in.category or "Technology",
        status=ArticleStatus.IDEA,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic


@router.get("/discover/trending")
def discover_trending_topics(
    country: str = "IN",
    category: str = "Technology",
    limit: int = 12,
):
    """Discover current search trends and popular topics from real internet sources."""
    from backend.services.topic_discovery import topic_discovery_service
    return topic_discovery_service.discover_trending(country=country, category=category, limit=limit)


@router.get("/discover/random")
def discover_random_or_evergreen(
    mode: str = "random",  # random or evergreen
    category: str = "Technology",
    difficulty: str = "All",
    audience: str = "Developers & Tech Enthusiasts",
    country: str = "IN",
    limit: int = 12,
):
    """Discover random or evergreen high-value topics for the blog niche."""
    from backend.services.topic_discovery import topic_discovery_service
    return topic_discovery_service.discover_random_or_evergreen(
        mode=mode,
        category=category,
        difficulty=difficulty,
        audience=audience,
        country=country,
        limit=limit,
    )


@router.get("/{topic_id}", response_model=TopicRead)
def get_topic(topic_id: int, db: Session = Depends(get_db)):
    """Get single topic details."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.delete("/{topic_id}")
def delete_topic(topic_id: int, db: Session = Depends(get_db)):
    """Delete a topic and decouple any associated articles."""
    from backend.models.entities import Article
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Decouple articles that reference this topic
    db.query(Article).filter(Article.topic_id == topic_id).update({Article.topic_id: None})
    db.delete(topic)
    db.commit()
    return {"success": True, "message": "Topic deleted"}



@router.post("/seed-sample", response_model=TopicRead)
def seed_sample_topic(db: Session = Depends(get_db)):
    """Seed a realistic, authoritative sample topic for testing and demo purposes."""
    sample = Topic(
        title="Building High-Impact Web Applications with Google Search Helpful Content Guidelines",
        target_audience="Web Developers & Technical Bloggers",
        country_region="Global",
        search_intent="Informational",
        desired_length="medium (~1500w)",
        keywords=["helpful content", "technical SEO", "developer documentation", "blogger draft"],
        priority="high",
        notes="Focus on official guidelines, avoiding thin content, and practical architectural patterns.",
        status=ArticleStatus.IDEA,
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample
