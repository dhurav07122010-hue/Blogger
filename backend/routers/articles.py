"""
Articles Router for Blogger AI Agent.
Handles article generation workflow, state transitions, human approval, revisions, and Blogger draft triggering.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.entities import Article, ArticleRevision, QualityCheck, ResearchSource, ArticleStatus
from backend.models.schemas import (
    ArticleRead,
    ArticleCreate,
    ArticleUpdate,
    StartWorkflowRequest,
    ApprovalDecisionRequest,
    RevisionRequest,
    AIAssistRequest,
)
from backend.agents.orchestrator import orchestrator

router = APIRouter(prefix="/api/articles", tags=["Articles"])


@router.get("", response_model=List[ArticleRead])
def list_articles(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """List articles, optionally filtered by status."""
    query = db.query(Article)
    if status:
        query = query.filter(Article.status == status.upper())
    return query.order_by(Article.id.desc()).all()


@router.post("/start-workflow", response_model=ArticleRead)
def start_pipeline_workflow(req: StartWorkflowRequest, db: Session = Depends(get_db)):
    """
    Launch the autonomous content creation pipeline:
    Topic -> Research -> Draft -> Fact-Check -> SEO -> Quality Audit -> Revision (if needed) -> Ready for Human Approval.
    """
    from backend.services.ai_provider import (
        ConnectivityError,
        OllamaConnectionError,
        OllamaModelError,
        AIProviderError,
    )
    try:
        article = orchestrator.run_full_pipeline(
            db=db,
            topic_id=req.topic_id,
            custom_title=req.custom_title,
            target_audience=req.target_audience or "General Audience",
            country_region=req.country_region or "Global",
            search_intent=req.search_intent or "Informational",
            desired_length=req.desired_length or "medium (~1500w)",
            keywords=req.keywords or [],
        )
        return article
    except ConnectivityError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except (OllamaConnectionError, OllamaModelError) as e:
        raise HTTPException(status_code=503, detail=str(e))
    except AIProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


@router.get("/{article_id}", response_model=ArticleRead)
def get_article(article_id: int, db: Session = Depends(get_db)):
    """Fetch complete article details including revisions, quality checks, and metadata."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.post("/{article_id}/decision")
def make_human_decision(
    article_id: int,
    req: ApprovalDecisionRequest,
    blog_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Submit human review decision:
    - APPROVE: Validates quality gate and pushes draft to Blogger (isDraft=True)
    - REVISION: Generates targeted revision addressing editor comments
    - REJECT: Marks article as rejected
    - SAVE_DRAFT: Keeps as local draft
    """
    res = orchestrator.handle_human_decision(
        db=db,
        article_id=article_id,
        decision=req.decision,
        feedback=req.feedback or "",
        blog_id=blog_id,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.put("/{article_id}", response_model=ArticleRead)
def update_article_content(article_id: int, req: ArticleUpdate, db: Session = Depends(get_db)):
    """Manually update article content or metadata."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    content_changed = req.content is not None and req.content != article.content

    if req.title is not None:
        article.title = req.title
    if req.content is not None:
        article.content = req.content
    if req.summary is not None:
        article.summary = req.summary
    if req.status is not None:
        article.status = req.status
    if req.research_notes is not None:
        article.research_notes = req.research_notes
    if req.seo_metadata is not None:
        article.seo_metadata = req.seo_metadata
    if req.featured_image is not None:
        article.featured_image = req.featured_image
    elif req.featuredImage is not None:
        article.featured_image = req.featuredImage

    if content_changed:
        rev_count = db.query(ArticleRevision).filter(ArticleRevision.article_id == article.id).count()
        rev = ArticleRevision(
            article_id=article.id,
            revision_number=rev_count + 1,
            title=article.title,
            content=article.content,
            change_summary=req.revision_summary or "Manual user edit.",
        )
        db.add(rev)

    db.commit()
    db.refresh(article)
    return article


@router.delete("/{article_id}")
def delete_article(article_id: int, db: Session = Depends(get_db)):
    """Delete an article."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    db.delete(article)
    db.commit()
    return {"success": True, "message": "Article deleted"}


@router.post("/seed-demo-article", response_model=ArticleRead)
def seed_demo_article(db: Session = Depends(get_db)):
    """
    Seed a complete, pre-audited article ready for approval.
    Useful for Demo Mode and immediate testing without burning API quota.
    """
    article = orchestrator.run_full_pipeline(
        db=db,
        custom_title="Building High-Impact Web Applications with Google Search Helpful Content Guidelines",
        target_audience="Web Developers & Technical Bloggers",
        country_region="Global",
        search_intent="Informational",
        desired_length="medium (~1500w)",
        keywords=["helpful content", "technical SEO", "developer documentation", "blogger draft"],
    )
    return article


@router.post("/ai-assist")
def ai_assistant(req: AIAssistRequest):
    """
    Dedicated AI Writing Assistant for the rich article workspace:
    - improve: Polishes sentence flow, vocabulary, and readability.
    - rewrite: Provides fresh alternative phrasing.
    - expand: Elaborates with clear explanations, examples, or technical context.
    - shorten: Condenses text, eliminating filler and wordiness.
    - suggest_titles: Suggests 5 SEO-friendly titles.
    - suggest_keywords: Suggests 8-12 search keywords.
    - generate_toc: Generates a structured Table of Contents from headings.
    - meta_description: Generates an engaging 150-160 character meta description.
    """
    from backend.services.ai_provider import ai_provider
    from backend.config import settings

    target_text = req.selected_text or req.content or ""
    action = req.action.lower()

    if action == "generate_toc":
        # Extract headings from content (HTML or markdown)
        import re
        content = req.content or ""
        h2_h3 = re.findall(r"<(h[2-3])[^>]*>(.*?)</\1>|^([#]{2,3})\s+(.+)$", content, re.MULTILINE | re.IGNORECASE)
        items = []
        for match in h2_h3:
            tag, tag_text, md_hashes, md_text = match
            level = 2 if (tag == "h2" or md_hashes == "##") else 3
            text = (tag_text or md_text or "").strip()
            # strip any nested tags
            clean_text = re.sub(r"<[^>]+>", "", text).strip()
            if clean_text:
                slug = re.sub(r"[^\w\s-]", "", clean_text).strip().lower().replace(" ", "-")
                indent = "  " if level == 3 else ""
                items.append(f"{indent}- [{clean_text}](#{slug})")
        if not items:
            toc = "### Table of Contents\n- [Introduction](#introduction)\n- [Key Concepts & Fundamentals](#key-concepts)\n- [Step-by-Step Implementation](#implementation)\n- [Best Practices](#best-practices)\n- [Summary & Next Steps](#summary)"
        else:
            toc = "### Table of Contents\n" + "\n".join(items)
        return {"action": action, "result": toc}

    # For text generation actions
    prompts = {
        "improve": f"You are a professional editor. Improve the following text for clarity, cadence, natural human tone, and readability. Keep the factual meaning intact. Do not use generic filler or robotic boilerplate.\n\nText:\n{target_text}\n\nAdditional instructions: {req.instructions or 'None'}\n\nReturn ONLY the improved text.",
        "rewrite": f"You are an expert copywriter. Rewrite the following passage in a fresh, natural, engaging voice for {req.target_audience}. Maintain factual accuracy.\n\nText:\n{target_text}\n\nAdditional instructions: {req.instructions or 'None'}\n\nReturn ONLY the rewritten text.",
        "expand": f"You are an authoritative technical writer. Expand and elaborate on this passage with clear explanations, concrete real-world context, and practical nuances. Avoid fluff.\n\nText:\n{target_text}\n\nTopic / Title: {req.title}\nAdditional instructions: {req.instructions or 'None'}\n\nReturn ONLY the expanded text.",
        "shorten": f"You are an editor focusing on crisp, concise writing. Condense the following passage while preserving key points, core facts, and strong tone. Cut all redundancy.\n\nText:\n{target_text}\n\nReturn ONLY the tightened text.",
        "regenerate_section": f"You are an expert editorial writer. Completely regenerate this article section with fresh, compelling, human-quality depth, real explanations, and practical examples.\n\nSection to regenerate:\n{target_text}\n\nArticle Topic / Title: {req.title}\nAdditional instructions: {req.instructions or 'Make it informative and authoritative'}\n\nReturn ONLY the regenerated section in clean Markdown.",
        "fact_check": f"You are a strict, objective Fact Checker. Cross-examine the factual statements and claims in the following excerpt:\n\nExcerpt:\n{target_text}\n\nIdentify any unsupported assertions, exaggerations, or unverified claims, and suggest how to frame them accurately.\nReturn a concise, bulleted fact-check finding.",
        "suggest_titles": f"Generate 5 compelling, human-sounding, SEO-friendly article titles for an article about: '{req.title or target_text}'. Target audience: {req.target_audience}.\nMake them distinct (e.g. How-To, Deep Dive, Practical Guide, Industry Analysis, Thought Leadership).\nReturn the 5 titles as a numbered list.",
        "suggest_keywords": f"Suggest 10 high-value search keywords, search intent variations, and semantic LSI terms for an article on: '{req.title or target_text}'.\nReturn the keywords as a clean comma-separated list.",
        "meta_description": f"Write a compelling, search-optimized meta description (145-160 characters) for an article titled '{req.title or 'this topic'}'.\nArticle excerpt: {target_text[:400]}.\nReturn ONLY the meta description string.",
    }

    prompt = prompts.get(action, f"Assist with this text: {target_text}")

    if settings.DEMO_MODE:
        demo_responses = {
            "improve": f"Here is the refined version: {target_text.strip() if target_text else 'Clear, well-structured communication connects directly with human readers through specific examples and natural cadence.'}",
            "rewrite": f"Alternative phrasing: {target_text.strip() if target_text else 'Mastering this topic requires understanding the core mechanisms before applying them in production workflows.'}",
            "expand": f"{target_text.strip()}\n\nFurthermore, practitioners should consider how these principles interact across different application architectures. Implementing structured testing and observability early prevents costly edge cases later in deployment.",
            "shorten": f"{target_text[:120].strip()}...",
            "suggest_titles": f"1. How to Master {req.title or 'Modern Development'}: A Complete Guide\n2. The Engineering Behind {req.title or 'Web Architecture'}\n3. 7 Proven Strategies for {req.title or 'High Performance'}\n4. Why {req.title or 'Modern Systems'} Matter in 2026\n5. Step-by-Step Breakdown: {req.title or 'Next-Gen Workflow'}",
            "suggest_keywords": "software engineering, web development, architecture best practices, scalable systems, developer productivity, code optimization, tutorial, guide 2026",
            "meta_description": f"Discover how {req.title or 'modern systems'} work with practical examples, clear architecture breakdowns, and step-by-step guidance."[:160],
        }
        return {"action": action, "result": demo_responses.get(action, "Operation completed in demo mode.")}

    try:
        text, _, _ = ai_provider.generate_text(
            prompt=prompt,
            system_instruction="You are an expert editorial and technical writing partner. Return clear, natural, direct text without conversational pleasantries or preamble.",
            temperature=0.6 if action in ("suggest_titles", "rewrite") else 0.4,
        )
        return {"action": action, "result": text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Assistant error: {str(e)}")
