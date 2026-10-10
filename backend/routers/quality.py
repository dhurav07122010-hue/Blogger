"""
Quality Router for Blogger AI Agent.
Handles quality score audits, breakdown inspection, and re-evaluations.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.entities import Article, QualityCheck, ResearchSource
from backend.models.schemas import QualityCheckRead
from backend.services.fact_checker import fact_checker
from backend.services.seo import seo_reviewer
from backend.services.quality_checker import quality_checker

router = APIRouter(prefix="/api/quality", tags=["Quality"])


@router.get("/article/{article_id}", response_model=List[QualityCheckRead])
def get_article_quality_history(article_id: int, db: Session = Depends(get_db)):
    """Fetch all quality check runs for an article."""
    checks = db.query(QualityCheck).filter(QualityCheck.article_id == article_id).order_by(QualityCheck.id.desc()).all()
    return checks


@router.post("/recheck/{article_id}", response_model=QualityCheckRead)
def rerun_quality_check(article_id: int, db: Session = Depends(get_db)):
    """Re-run quality gate inspection on an existing article."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    sources = db.query(ResearchSource).filter(ResearchSource.article_id == article.id).all()
    sources_data = [
        {
            "title": s.title,
            "url": s.url,
            "domain": s.domain,
            "publication_date": s.publication_date,
            "relevant_facts": s.relevant_facts or [],
            "is_verified": s.is_verified,
        }
        for s in sources
    ]

    # Run fact checker
    fc_res = fact_checker.check_article(
        article_content=article.content,
        sources=sources_data,
        research_notes=article.research_notes or "",
    )

    # Run SEO review
    seo_res = seo_reviewer.review_and_optimize(
        title=article.title,
        content=article.content,
        primary_keywords=article.keywords or [],
        search_intent=article.search_intent or "Informational",
    )
    article.seo_metadata = seo_res

    # Run Quality audit
    qc_res = quality_checker.evaluate_quality(
        article_title=article.title,
        article_content=article.content,
        research_sources=sources_data,
        fact_check_result=fc_res,
        seo_data=seo_res,
        search_intent=article.search_intent or "Informational",
    )

    # Automated Actionable Editorial Audits:
    detected_issues = qc_res.get("detected_issues", [])
    suggestions = qc_res.get("suggestions", [])

    # 1. Title audit
    if not article.title or len(article.title.strip()) < 10:
        detected_issues.append("Title Issue: Article title is missing or too short to convey value.")
    else:
        # Check duplicate titles in database
        dup_count = db.query(Article).filter(Article.title == article.title, Article.id != article.id).count()
        if dup_count > 0:
            detected_issues.append(f"Title Issue: Detected {dup_count} other article(s) with an identical title.")

    # 2. Meta description audit
    meta_desc = (seo_res.get("meta_description") or "").strip()
    if not meta_desc:
        detected_issues.append("SEO Issue: Meta description is missing. Add a 140-160 character description.")
    elif len(meta_desc) < 70 or len(meta_desc) > 170:
        suggestions.append(f"SEO Recommendation: Meta description length ({len(meta_desc)} chars) should ideally be 140-160 characters.")

    # 3. Heading structure audit
    content = article.content or ""
    import re
    h2_matches = re.findall(r"^##\s+(.+)$|<h2[^>]*>(.+?)</h2>", content, re.MULTILINE | re.IGNORECASE)
    if not h2_matches:
        detected_issues.append("Readability Issue: No H2 subheadings found. Break the article into logical H2 sections.")
    elif len(h2_matches) < 2:
        suggestions.append("Structure Recommendation: Consider adding at least 2 to 3 H2 subheadings for reader flow.")

    # 4. Link & Citation check
    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)|<a\s+[^>]*href=[\"']([^\"']+)[\"']", content)
    if not links and not sources_data:
        suggestions.append("Citations Recommendation: Add reference links or citations to authoritative primary sources.")

    # 5. Repetitive / Near-duplicate phrasing check
    repeated_phrases = re.findall(r"\b(\w+\s+\w+\s+\w+)\b", content.lower())
    phrase_counts = {}
    for p in repeated_phrases:
        if len(p) > 10 and not any(w in p for w in ["in order to", "as well as", "one of the"]):
            phrase_counts[p] = phrase_counts.get(p, 0) + 1
    overused = [p for p, c in phrase_counts.items() if c >= 4]
    if overused:
        suggestions.append(f"Wording Variety: Phrase '{overused[0]}' appears {phrase_counts[overused[0]]} times. Consider varying your wording.")

    qc_res["detected_issues"] = detected_issues
    qc_res["suggestions"] = suggestions

    qc_record = QualityCheck(
        article_id=article.id,
        factual_accuracy_score=qc_res.get("factual_accuracy_score", 0.0),
        usefulness_score=qc_res.get("usefulness_score", 0.0),
        originality_score=qc_res.get("originality_score", 0.0),
        readability_score=qc_res.get("readability_score", 0.0),
        search_intent_match_score=qc_res.get("search_intent_match_score", 0.0),
        seo_quality_score=qc_res.get("seo_quality_score", 0.0),
        source_quality_score=qc_res.get("source_quality_score", 0.0),
        overall_score=qc_res.get("overall_score", 0.0),
        passed=qc_res.get("passed", False),
        fact_check_results=fc_res.get("results", []),
        originality_notes=qc_res.get("originality_notes", ""),
        detected_issues=qc_res.get("detected_issues", []),
        suggestions=qc_res.get("suggestions", []),
    )
    db.add(qc_record)
    article.overall_quality_score = qc_res.get("overall_score", 0.0)
    db.commit()
    db.refresh(qc_record)
    return qc_record
