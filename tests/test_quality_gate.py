"""
Tests for quality score calculations, fact checking, and quality gate threshold enforcement.
"""

from backend.services.quality_checker import quality_checker
from backend.services.fact_checker import fact_checker
from backend.config import settings
from backend.models.entities import Article, ArticleStatus
from backend.agents.orchestrator import orchestrator


def test_fact_checker_detects_unsupported_claim():
    # Test unsupported claim handling
    unsupported_fact_res = {
        "results": [
            {
                "claim": "Drinking raw mercury extends life by 50 years",
                "status": "UNSUPPORTED",
                "source": "Unverified",
                "reason": "Dangerous medical falsehood.",
            }
        ],
        "factual_accuracy_score": 0.0,
        "has_critical_failure": True,
        "supported_count": 0,
        "uncertain_count": 0,
        "unsupported_count": 1,
    }

    qc_res = quality_checker.evaluate_quality(
        article_title="Dangerous Claims Test",
        article_content="Some content",
        research_sources=[],
        fact_check_result=unsupported_fact_res,
        seo_data={"seo_quality_score": 80.0},
    )

    assert qc_res["passed"] is False
    assert any("Factual Violation" in issue or "Unsupported claim" in issue for issue in qc_res["detected_issues"])


def test_quality_gate_threshold_rejection(db_session):
    # Set threshold
    settings.QUALITY_THRESHOLD = 85

    # Article below threshold
    subpar_article = Article(
        title="Thin Content Article",
        content="Short text with little value.",
        status=ArticleStatus.NEEDS_REVISION,
        overall_quality_score=68.0,
    )
    db_session.add(subpar_article)
    db_session.commit()

    # Attempt to approve subpar article
    result = orchestrator.handle_human_decision(
        db=db_session,
        article_id=subpar_article.id,
        decision="APPROVE",
    )

    assert result["success"] is False
    assert "below the quality threshold" in result["error"]
    assert subpar_article.blogger_post_id is None


from unittest.mock import patch

def test_quality_check_breakdown_metrics():
    fact_res = {
        "results": [{"claim": "Supported fact", "status": "SUPPORTED", "source": "docs.google.com", "reason": "Verified"}],
        "factual_accuracy_score": 100.0,
        "has_critical_failure": False,
        "supported_count": 1,
        "uncertain_count": 0,
        "unsupported_count": 0,
    }

    mock_eval = {
        "usefulness_score": 88.0,
        "originality_score": 90.0,
        "readability_score": 85.0,
        "search_intent_match_score": 92.0,
        "detected_issues": [],
        "suggestions": [],
        "safety_passed": True,
    }

    with patch("backend.services.quality_checker.ai_provider.generate_json", return_value=(mock_eval, 50, 100)):
        qc_res = quality_checker.evaluate_quality(
            article_title="High Quality Technical Article",
            article_content="Deep practical guide with actionable examples and references.",
            research_sources=[{"is_verified": True}],
            fact_check_result=fact_res,
            seo_data={"seo_quality_score": 90.0},
        )

    assert "factual_accuracy_score" in qc_res
    assert "usefulness_score" in qc_res
    assert "originality_score" in qc_res
    assert "readability_score" in qc_res
    assert "search_intent_match_score" in qc_res
    assert "seo_quality_score" in qc_res
    assert "source_quality_score" in qc_res
    assert "overall_score" in qc_res
    assert qc_res["overall_score"] >= 75.0
