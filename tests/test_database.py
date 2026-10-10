"""
Tests for SQLite database schema, entity persistence, and relationships.
"""

from backend.models.entities import (
    Project,
    Topic,
    ResearchSource,
    Article,
    ArticleRevision,
    QualityCheck,
    PublishingHistory,
    AgentRun,
    AppSetting,
    ArticleStatus,
)


def test_database_entities_persistence(db_session):
    # 1. Project
    project = Project(name="Tech Publications", description="Main blog project")
    db_session.add(project)
    db_session.commit()
    assert project.id is not None

    # 2. Topic
    topic = Topic(
        project_id=project.id,
        title="Python 3.12 Concurrency Features",
        target_audience="Backend Developers",
        status=ArticleStatus.IDEA,
    )
    db_session.add(topic)
    db_session.commit()
    assert topic.id is not None

    # 3. Article
    article = Article(
        project_id=project.id,
        topic_id=topic.id,
        title="Mastering Python 3.12 Concurrency",
        content="# Python Concurrency\n\nPractical examples.",
        status=ArticleStatus.DRAFT,
    )
    db_session.add(article)
    db_session.commit()
    assert article.id is not None

    # 4. ResearchSource
    source = ResearchSource(
        article_id=article.id,
        title="Official Python 3.12 Docs",
        url="https://docs.python.org/3/whatsnew/3.12.html",
        domain="docs.python.org",
        relevant_facts=["Subinterpreters introduced", "GIL improvements"],
        is_verified=True,
    )
    db_session.add(source)

    # 5. ArticleRevision
    rev = ArticleRevision(
        article_id=article.id,
        revision_number=1,
        title=article.title,
        content=article.content,
        change_summary="Initial draft",
    )
    db_session.add(rev)

    # 6. QualityCheck
    qc = QualityCheck(
        article_id=article.id,
        factual_accuracy_score=95.0,
        usefulness_score=90.0,
        originality_score=92.0,
        overall_score=92.0,
        passed=True,
        detected_issues=[],
    )
    db_session.add(qc)

    # 7. PublishingHistory
    hist = PublishingHistory(
        article_id=article.id,
        blogger_blog_id="test-blog-123",
        blogger_post_id="post-456",
        action="CREATE_DRAFT",
        status="SUCCESS",
    )
    db_session.add(hist)

    # 8. AgentRun
    run = AgentRun(
        article_id=article.id,
        agent_name="Fact Checker",
        status="SUCCESS",
        input_tokens_est=150,
        output_tokens_est=80,
    )
    db_session.add(run)

    # 9. AppSetting
    setting = AppSetting(key="TEST_KEY", value="123")
    db_session.add(setting)

    db_session.commit()

    # Verify cascading and retrieval
    retrieved = db_session.query(Article).filter(Article.id == article.id).first()
    assert retrieved is not None
    assert len(retrieved.research_sources) == 1
    assert len(retrieved.revisions) == 1
    assert len(retrieved.quality_checks) == 1
    assert retrieved.research_sources[0].domain == "docs.python.org"
