"""
Tests for article state transitions, orchestrator pipeline, and human approval workflow.
"""

from backend.models.entities import Article, ArticleStatus, QualityCheck
from backend.agents.orchestrator import orchestrator
from backend.config import settings


def test_full_pipeline_execution(db_session):
    # Ensure demo mode for test execution
    settings.DEMO_MODE = True

    article = orchestrator.run_full_pipeline(
        db=db_session,
        custom_title="Comprehensive Architecture of High-Reliability Systems",
        target_audience="System Architects",
        country_region="Global",
        search_intent="Informational",
        desired_length="medium (~1500w)",
        keywords=["reliability", "architecture", "scalability"],
    )

    assert article.id is not None
    assert article.status in [ArticleStatus.READY_FOR_APPROVAL, ArticleStatus.NEEDS_REVISION]
    assert len(article.content) > 100
    assert len(article.research_sources) > 0
    assert len(article.revisions) >= 1
    assert len(article.quality_checks) >= 1
    assert article.overall_quality_score is not None
    assert article.seo_metadata is not None
    assert "seo_title" in article.seo_metadata


def test_human_approval_creates_blogger_draft(db_session):
    settings.DEMO_MODE = True

    # Create an article with passing quality score
    article = Article(
        title="Verified Systems Guide",
        content="# Verified Systems\n\nPractical content.",
        status=ArticleStatus.READY_FOR_APPROVAL,
        overall_quality_score=92.0,
    )
    db_session.add(article)
    db_session.commit()

    # User clicks APPROVE
    result = orchestrator.handle_human_decision(
        db=db_session,
        article_id=article.id,
        decision="APPROVE",
    )

    assert result["success"] is True
    assert result["status"] == ArticleStatus.APPROVED
    assert article.blogger_post_id is not None
    assert "demo-draft" in article.blogger_post_id
    assert article.blogger_draft_url is not None


def test_human_revision_request_updates_revision_count(db_session):
    article = Article(
        title="Draft Awaiting Edits",
        content="# Initial Content\n\nNeeds improvement.",
        status=ArticleStatus.READY_FOR_APPROVAL,
        overall_quality_score=80.0,
    )
    db_session.add(article)
    db_session.commit()

    result = orchestrator.handle_human_decision(
        db=db_session,
        article_id=article.id,
        decision="REVISION",
        feedback="Please expand on practical debugging examples and remove filler.",
    )

    assert result["success"] is True
    assert article.status == ArticleStatus.NEEDS_REVISION
    assert len(article.revisions) >= 1
    assert "Please expand" in article.revisions[-1].change_summary


def test_rejection_blocks_publishing(db_session):
    article = Article(
        title="Questionable Article",
        content="Poor quality content.",
        status=ArticleStatus.READY_FOR_APPROVAL,
        overall_quality_score=88.0,
    )
    db_session.add(article)
    db_session.commit()

    result = orchestrator.handle_human_decision(
        db=db_session,
        article_id=article.id,
        decision="REJECT",
    )

    assert result["success"] is True
    assert article.status == ArticleStatus.REJECTED
    assert article.blogger_post_id is None
