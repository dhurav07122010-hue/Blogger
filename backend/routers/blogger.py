"""
Blogger Router for Blogger AI Agent.
Exposes Google OAuth 2.0 flow, blog discovery, draft creation, and guarded publishing.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.entities import Article, PublishingHistory, ArticleStatus
from backend.models.schemas import (
    BloggerBlog,
    BloggerPost,
    CreateBloggerDraftRequest,
    PublishBloggerPostRequest,
)
from backend.services.blogger import blogger_service
from backend.config import settings

router = APIRouter(prefix="/api/blogger", tags=["Blogger"])


@router.get("/login")
def login():
    """Directly redirect browser to Google OAuth 2.0 authorization screen."""
    url = blogger_service.get_auth_url()
    return RedirectResponse(url=url)


@router.get("/auth-url")
def get_oauth_url():
    """Retrieve Google OAuth 2.0 authorization URL."""
    url = blogger_service.get_auth_url()
    return {
        "auth_url": url,
        "is_configured": blogger_service.is_oauth_configured(),
        "is_authenticated": blogger_service.is_authenticated(),
        "demo_mode": settings.DEMO_MODE,
    }


@router.get("/oauth2callback")
def oauth2_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Google OAuth 2.0 redirect callback endpoint."""
    if error:
        return RedirectResponse(url="/#settings?oauth_error=" + error)
    if not code:
        return RedirectResponse(url="/#settings?oauth_error=No_code_provided")

    success = blogger_service.handle_auth_callback(code=code, state=state)
    if success:
        return RedirectResponse(url="/#settings?oauth_success=1")
    return RedirectResponse(url="/#settings?oauth_error=Failed_to_exchange_token")


@router.get("/demo-auth-success")
def demo_auth_success():
    """Redirect for Demo Mode OAuth simulation."""
    return RedirectResponse(url="/#settings?demo_auth=1")


@router.get("/status")
def get_blogger_status():
    """Inspect current Blogger connection status."""
    return {
        "is_oauth_configured": blogger_service.is_oauth_configured(),
        "is_authenticated": blogger_service.is_authenticated(),
        "blog_id": settings.BLOGGER_BLOG_ID or "demo-blog-101",
        "auto_publish": settings.AUTO_PUBLISH,
        "demo_mode": settings.DEMO_MODE,
    }


@router.get("/blogs", response_model=List[BloggerBlog])
def list_blogs():
    """List available Blogger blogs."""
    return blogger_service.list_blogs()


@router.get("/posts", response_model=List[BloggerPost])
def list_posts(blog_id: Optional[str] = None, max_results: int = 10):
    """List recent posts from a selected blog."""
    return blogger_service.list_posts(blog_id=blog_id, max_results=max_results)


@router.post("/create-draft")
def create_draft(req: CreateBloggerDraftRequest, db: Session = Depends(get_db)):
    """Create a draft on Blogger for an approved article."""
    article = db.query(Article).filter(Article.id == req.article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    from backend.services.ai_provider import check_internet_connection
    if not settings.DEMO_MODE and not check_internet_connection():
        raise HTTPException(
            status_code=503,
            detail="Cannot push draft to Blogger while offline. An active internet connection is required to communicate with Blogger API. Your draft is preserved locally.",
        )

    # Safety check: article must have passed quality threshold
    threshold = settings.QUALITY_THRESHOLD
    if (article.overall_quality_score or 0) < threshold:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot push to Blogger: Quality score ({article.overall_quality_score}) is below threshold ({threshold}).",
        )

    content_to_send = article.content
    if article.featured_image:
        feat = article.featured_image
        img_url = feat.get("url") or feat.get("imageUrl") or feat.get("image")
        if img_url:
            alt_text = feat.get("title") or feat.get("altText") or f"Featured image for {article.title}"
            author = feat.get("author") or ""
            license_info = feat.get("license") or "License unknown — verify before commercial/public use."
            source_name = feat.get("sourceName") or "Web"
            caption_items = []
            if author and author != "Unknown":
                caption_items.append(f"Photo: {author}")
            caption_items.append(f"Source: {source_name}")
            caption_items.append(f"License: {license_info}")
            caption_str = " • ".join(caption_items)

            img_banner = (
                f'\n<div class="separator" style="clear: both; text-align: center; margin: 24px 0;">\n'
                f'  <img src="{img_url}" alt="{alt_text}" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.12); display: inline-block;" loading="lazy" />\n'
                f'  <p style="font-size: 12px; color: #64748b; font-style: italic; margin-top: 6px; text-align: center;">{caption_str}</p>\n'
                f'</div>\n\n'
            )
            if img_url not in content_to_send:
                content_to_send = img_banner + content_to_send

    res = blogger_service.create_draft(
        title=article.title,
        content_html_or_md=content_to_send,
        blog_id=req.blog_id,
        labels=article.keywords or ["Draft"],
    )

    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Draft creation failed"))

    article.blogger_post_id = res.get("post_id")
    article.blogger_draft_url = res.get("post_url")
    if article.status != ArticleStatus.APPROVED:
        article.status = ArticleStatus.APPROVED

    # Log publishing history
    hist = PublishingHistory(
        article_id=article.id,
        blogger_blog_id=req.blog_id or settings.BLOGGER_BLOG_ID or "demo-blog-101",
        blogger_post_id=res.get("post_id", ""),
        action="CREATE_DRAFT",
        status="SUCCESS",
        post_url=res.get("post_url"),
    )
    db.add(hist)
    db.commit()

    return res


@router.post("/publish")
def publish_post(req: PublishBloggerPostRequest, db: Session = Depends(get_db)):
    """
    Publish an approved draft on Blogger.
    Strict safety conditions apply:
    - User must pass confirm_publish=True.
    - AUTO_PUBLISH setting or explicit admin override.
    - Article must have passed quality score >= threshold.
    """
    article = db.query(Article).filter(Article.id == req.article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    from backend.services.ai_provider import check_internet_connection
    if not settings.DEMO_MODE and not check_internet_connection():
        raise HTTPException(
            status_code=503,
            detail="Cannot publish to Blogger while offline. An active internet connection is required to communicate with Blogger API. Your draft is preserved locally.",
        )

    if not req.confirm_publish:
        raise HTTPException(
            status_code=400,
            detail="Publishing rejected: confirm_publish parameter must be explicitly set to True.",
        )

    post_id = article.blogger_post_id
    if not post_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot publish: Article does not have an existing Blogger draft ID. Create a draft first.",
        )

    res = blogger_service.publish_post(
        post_id=post_id,
        blog_id=req.blog_id,
        quality_score=article.overall_quality_score or 0.0,
        confirm_publish=req.confirm_publish,
    )

    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Publishing failed"))

    article.status = ArticleStatus.PUBLISHED
    hist = PublishingHistory(
        article_id=article.id,
        blogger_blog_id=req.blog_id or settings.BLOGGER_BLOG_ID or "demo-blog-101",
        blogger_post_id=post_id,
        action="PUBLISH",
        status="SUCCESS",
        post_url=res.get("post_url"),
    )
    db.add(hist)
    db.commit()
    return res


@router.get("/history")
def get_publishing_history(db: Session = Depends(get_db)):
    """Fetch publishing and draft synchronization history from real database entries."""
    records = (
        db.query(PublishingHistory, Article.title)
        .outerjoin(Article, PublishingHistory.article_id == Article.id)
        .order_by(PublishingHistory.id.desc())
        .limit(100)
        .all()
    )
    result = []
    for h, title in records:
        result.append({
            "id": h.id,
            "article_id": h.article_id,
            "article_title": title or f"Article #{h.article_id}",
            "blogger_blog_id": h.blogger_blog_id,
            "blogger_post_id": h.blogger_post_id,
            "action": h.action,
            "status": h.status,
            "post_url": h.post_url,
            "error_message": h.error_message,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        })
    return result
