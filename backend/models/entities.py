"""
SQLAlchemy ORM models for Blogger AI Agent.
"""

from datetime import datetime, timezone
import json
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship
from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ArticleStatus:
    IDEA = "IDEA"
    RESEARCHING = "RESEARCHING"
    RESEARCHED = "RESEARCHED"
    DRAFT = "DRAFT"
    FACT_CHECK = "FACT_CHECK"
    QUALITY_REVIEW = "QUALITY_REVIEW"
    NEEDS_REVISION = "NEEDS_REVISION"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"

    ALL = [
        IDEA,
        RESEARCHING,
        RESEARCHED,
        DRAFT,
        FACT_CHECK,
        QUALITY_REVIEW,
        NEEDS_REVISION,
        READY_FOR_APPROVAL,
        APPROVED,
        PUBLISHED,
        REJECTED,
    ]


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    default_country = Column(String(50), default="Global")
    default_target_audience = Column(String(100), default="General Audience")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    topics = relationship("Topic", back_populates="project", cascade="all, delete-orphan")
    articles = relationship("Article", back_populates="project", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    title = Column(String(300), nullable=False)
    target_audience = Column(String(150), default="General Audience")
    country_region = Column(String(100), default="Global")
    search_intent = Column(String(80), default="Informational")
    desired_length = Column(String(50), default="medium (~1500w)")
    keywords = Column(JSON, default=list)
    status = Column(String(50), default=ArticleStatus.IDEA)
    priority = Column(String(30), default="medium")  # low, medium, high
    notes = Column(Text, default="")
    source = Column(String(100), default="User")  # e.g. "Google Trends", "Google News (Tech)", "Evergreen AI", "User"
    source_url = Column(String(600), default="")
    discovery_mode = Column(String(50), default="manual")  # trending, random, evergreen, manual
    trend_evidence = Column(String(200), default="")  # e.g. "100K+ searches", "Tech Top Story"
    estimated_difficulty = Column(String(50), default="Intermediate (Estimate)")
    audience_fit = Column(String(50), default="High")
    article_potential = Column(String(50), default="High")
    category = Column(String(100), default="Technology")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="topics")
    research_sources = relationship("ResearchSource", back_populates="topic", cascade="all, delete-orphan")
    articles = relationship("Article", back_populates="topic")


class ResearchSource(Base):
    __tablename__ = "research_sources"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    title = Column(String(300), nullable=False)
    url = Column(String(600), nullable=False)
    domain = Column(String(150), default="")
    publication_date = Column(String(50), default="")
    relevant_facts = Column(JSON, default=list)
    notes = Column(Text, default="")
    is_verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    topic = relationship("Topic", back_populates="research_sources")
    article = relationship("Article", back_populates="research_sources")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)
    title = Column(String(300), nullable=False)
    content = Column(Text, default="")
    summary = Column(Text, default="")
    status = Column(String(50), default=ArticleStatus.IDEA, index=True)
    search_intent = Column(String(80), default="Informational")
    target_audience = Column(String(150), default="General Audience")
    country_region = Column(String(100), default="Global")
    keywords = Column(JSON, default=list)
    research_notes = Column(Text, default="")
    source_urls = Column(JSON, default=list)
    seo_metadata = Column(JSON, default=dict)
    blogger_post_id = Column(String(100), nullable=True)
    blogger_draft_url = Column(String(500), nullable=True)
    overall_quality_score = Column(Float, nullable=True)
    featured_image = Column(JSON, default=dict)  # {image_url_or_data, alt_text, filename, prompt}
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="articles")
    topic = relationship("Topic", back_populates="articles")
    research_sources = relationship("ResearchSource", back_populates="article", cascade="all, delete-orphan")
    revisions = relationship("ArticleRevision", back_populates="article", cascade="all, delete-orphan", order_by="ArticleRevision.revision_number.desc()")
    quality_checks = relationship("QualityCheck", back_populates="article", cascade="all, delete-orphan", order_by="QualityCheck.id.desc()")
    publishing_history = relationship("PublishingHistory", back_populates="article", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="article", cascade="all, delete-orphan")


class ArticleRevision(Base):
    __tablename__ = "article_revisions"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    revision_number = Column(Integer, nullable=False)
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False)
    change_summary = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)

    article = relationship("Article", back_populates="revisions")


class QualityCheck(Base):
    __tablename__ = "quality_checks"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    factual_accuracy_score = Column(Float, default=0.0)
    usefulness_score = Column(Float, default=0.0)
    originality_score = Column(Float, default=0.0)
    readability_score = Column(Float, default=0.0)
    search_intent_match_score = Column(Float, default=0.0)
    seo_quality_score = Column(Float, default=0.0)
    source_quality_score = Column(Float, default=0.0)
    overall_score = Column(Float, default=0.0)
    passed = Column(Boolean, default=False)
    fact_check_results = Column(JSON, default=list)  # list of {claim, status, source, reason}
    originality_notes = Column(Text, default="")
    detected_issues = Column(JSON, default=list)
    suggestions = Column(JSON, default=list)
    created_at = Column(DateTime, default=utcnow)

    article = relationship("Article", back_populates="quality_checks")


class PublishingHistory(Base):
    __tablename__ = "publishing_history"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    blogger_blog_id = Column(String(100), default="")
    blogger_post_id = Column(String(100), default="")
    action = Column(String(50), nullable=False)  # CREATE_DRAFT, UPDATE_DRAFT, PUBLISH
    status = Column(String(50), nullable=False)  # SUCCESS, FAILED
    post_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    article = relationship("Article", back_populates="publishing_history")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    agent_name = Column(String(100), nullable=False)
    status = Column(String(50), default="SUCCESS")  # SUCCESS, FAILED, RUNNING
    input_tokens_est = Column(Integer, default=0)
    output_tokens_est = Column(Integer, default=0)
    execution_time_seconds = Column(Float, default=0.0)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)

    article = relationship("Article", back_populates="agent_runs")


class AppSetting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, default="")
    description = Column(String(255), default="")
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
