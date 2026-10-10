"""
Web Image Search Router for Blogger AI Agent.
Exposes endpoints for web image search, multi-query topic search, relevance filtering,
and featured image management. All AI image generation has been completely removed.

Endpoints:
- POST /api/images/find-for-article: Runs multi-query search, relevance scoring, and threshold filtering
- POST /api/images/search: Custom query web image search
- POST /api/images/select-featured: Persists selected featured image to article in database
- POST /api/images/remove-featured: Clears featured image from article in database
- POST /api/ai/generate-image: Backwards-compatible route redirecting to Web Image Search
- POST /api/ai/craft-image-prompt: Backwards-compatible route returning structured search query
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging
import base64
import io
import re
import uuid
from pathlib import Path
from PIL import Image as PILImage

from backend.database import get_db
from backend.models.entities import Article
from backend.services.image_search import image_search_manager
from backend.config import settings

logger = logging.getLogger("blogger_agent.image_router")

router = APIRouter(tags=["Web Image Search"])


class FindImagesRequest(BaseModel):
    articleTitle: str = Field(..., description="Title of the article")
    articleContent: Optional[str] = Field("", description="Draft content or full text")
    articleSummary: Optional[str] = Field("", description="Article summary")
    keywords: Optional[List[str]] = Field(default_factory=list, description="Article keywords")
    autoSelect: Optional[bool] = Field(None, description="Whether to auto-select best image if above threshold")
    minRelevance: Optional[str] = Field(None, description="strict | balanced | relaxed")
    articleId: Optional[int] = Field(None, description="Optional article ID to auto-save to database")


class CustomSearchRequest(BaseModel):
    query: str = Field(..., description="Custom search query string")
    limit: Optional[int] = Field(8, description="Max images to retrieve")


class SelectFeaturedRequest(BaseModel):
    articleId: int = Field(..., description="Target article ID")
    image: Dict[str, Any] = Field(..., description="Selected image metadata dictionary")


class RemoveFeaturedRequest(BaseModel):
    articleId: int = Field(..., description="Target article ID")


class CustomUploadRequest(BaseModel):
    articleId: Optional[int] = Field(None, description="Target article ID if available")
    filename: str = Field(..., description="Original filename (e.g. poster.png)")
    data: str = Field(..., description="Base64 encoded image string or data URL")
    title: Optional[str] = Field(None, description="Image title / caption")
    author: Optional[str] = Field("User", description="Image author / credit")
    license: Optional[str] = Field("User Owned / Permitted", description="License status")


class CustomUrlRequest(BaseModel):
    articleId: Optional[int] = Field(None, description="Target article ID if available")
    url: str = Field(..., description="Direct web URL of the image")
    title: Optional[str] = Field(None, description="Image title / caption")
    author: Optional[str] = Field("User Provided", description="Image author / credit")
    license: Optional[str] = Field("User Provided / Verify Rights", description="License status")


# =========================================================================
# WEB IMAGE SEARCH ENDPOINTS
# =========================================================================

@router.post("/api/images/find-for-article")
def find_images_for_article(req: FindImagesRequest, db: Session = Depends(get_db)):
    """
    Find relevant web images for an article.
    Synthesizes structured query, queries web search provider, scores relevance (0-100),
    and enforces strict relevance threshold filtering.
    """
    if not req.articleTitle.strip():
        raise HTTPException(status_code=400, detail="articleTitle is required.")

    auto_sel = req.autoSelect if req.autoSelect is not None else settings.IMAGE_AUTO_SELECT
    min_rel = req.minRelevance if req.minRelevance is not None else settings.IMAGE_MIN_RELEVANCE

    result = image_search_manager.find_images_for_article(
        article_title=req.articleTitle,
        article_content=req.articleContent or "",
        article_summary=req.articleSummary or "",
        keywords=req.keywords or [],
        auto_select=auto_sel,
        min_relevance=min_rel,
    )

    # If articleId is supplied and a valid image passed the threshold, persist to DB
    if req.articleId and result.get("selectedImage"):
        article = db.query(Article).filter(Article.id == req.articleId).first()
        if article:
            article.featured_image = result["selectedImage"]
            db.commit()

    return result


@router.post("/api/images/search")
def custom_image_search(req: CustomSearchRequest):
    """
    Search the web for images using a custom user-defined query string.
    """
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    candidates = image_search_manager.custom_search(query=query, limit=req.limit or 8)
    return {
        "success": True,
        "query": query,
        "candidates": candidates,
        "count": len(candidates),
    }


@router.post("/api/images/select-featured")
def select_featured_image(req: SelectFeaturedRequest, db: Session = Depends(get_db)):
    """
    Persist the user's selected featured image to the article record in the database.
    """
    article = db.query(Article).filter(Article.id == req.articleId).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found.")

    article.featured_image = req.image
    db.commit()
    db.refresh(article)

    return {
        "success": True,
        "message": "Featured image saved to article.",
        "articleId": article.id,
        "featuredImage": article.featured_image,
    }


@router.post("/api/images/remove-featured")
def remove_featured_image(req: RemoveFeaturedRequest, db: Session = Depends(get_db)):
    """
    Remove the featured image from the article.
    """
    article = db.query(Article).filter(Article.id == req.articleId).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found.")

    article.featured_image = {}
    db.commit()
    db.refresh(article)

    return {
        "success": True,
        "message": "Featured image removed.",
        "articleId": article.id,
    }


def get_uploads_dir() -> Path:
    uploads_dir = settings.BASE_DIR / "frontend" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    return uploads_dir


@router.post("/api/images/custom-upload")
def custom_upload_hero_image(req: CustomUploadRequest, db: Session = Depends(get_db)):
    """
    Allow user to upload their own image from local disk to use as the hero poster.
    Accepts base64 encoded image data, validates image integrity, stores file locally,
    and updates the article's featured_image.
    """
    if not req.data:
        raise HTTPException(status_code=400, detail="Image data is required.")

    # Strip data URL prefix if present (e.g. data:image/png;base64,...)
    raw_data = req.data
    if "," in raw_data and raw_data.startswith("data:"):
        raw_data = raw_data.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(raw_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {str(e)}")

    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty image data.")

    # Validate image using Pillow
    try:
        pil_img = PILImage.open(io.BytesIO(image_bytes))
        width, height = pil_img.size
        img_format = pil_img.format or "JPEG"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Corrupt or unsupported image file: {str(e)}")

    # Sanitize filename and create unique filename
    raw_name = req.filename or f"custom_poster.{img_format.lower()}"
    clean_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw_name)
    ext = Path(clean_name).suffix.lower()
    if not ext:
        ext = f".{img_format.lower()}"
    safe_name = f"{uuid.uuid4().hex[:10]}_{Path(clean_name).stem}{ext}"

    # Save to frontend/uploads
    uploads_dir = get_uploads_dir()
    file_path = uploads_dir / safe_name
    try:
        file_path.write_bytes(image_bytes)
    except Exception as e:
        logger.error(f"Failed to write image file: {e}")
        raise HTTPException(status_code=500, detail="Failed to write uploaded image to disk.")

    file_url = f"/static/uploads/{safe_name}"

    image_meta = {
        "url": file_url,
        "imageUrl": file_url,
        "thumbnailUrl": file_url,
        "fullUrl": file_url,
        "sourceUrl": "local-upload",
        "sourceName": "User Upload",
        "title": req.title or Path(raw_name).stem or "Custom Hero Poster",
        "author": req.author or "User",
        "license": req.license or "User Owned / Permitted",
        "width": width,
        "height": height,
        "mimeType": f"image/{img_format.lower()}",
        "relevanceScore": 100.0,
        "isCustom": True,
    }

    if req.articleId:
        article = db.query(Article).filter(Article.id == req.articleId).first()
        if article:
            article.featured_image = image_meta
            db.commit()
            db.refresh(article)

    return {
        "success": True,
        "message": "Custom hero poster uploaded successfully.",
        "image": image_meta,
        "articleId": req.articleId,
    }


@router.post("/api/images/custom-url")
def custom_url_hero_image(req: CustomUrlRequest, db: Session = Depends(get_db)):
    """
    Allow user to supply an external image URL directly for the hero poster.
    """
    clean_url = req.url.strip()
    if not clean_url or not (clean_url.startswith("http://") or clean_url.startswith("https://") or clean_url.startswith("/")):
        raise HTTPException(status_code=400, detail="A valid HTTP(S) or relative image URL is required.")

    image_meta = {
        "url": clean_url,
        "imageUrl": clean_url,
        "thumbnailUrl": clean_url,
        "fullUrl": clean_url,
        "sourceUrl": clean_url,
        "sourceName": "Custom URL",
        "title": req.title or "Custom Hero Poster",
        "author": req.author or "User Provided",
        "license": req.license or "User Provided / Verify Rights",
        "relevanceScore": 100.0,
        "isCustom": True,
    }

    if req.articleId:
        article = db.query(Article).filter(Article.id == req.articleId).first()
        if article:
            article.featured_image = image_meta
            db.commit()
            db.refresh(article)

    return {
        "success": True,
        "message": "Custom image URL set as hero poster successfully.",
        "image": image_meta,
        "articleId": req.articleId,
    }


# =========================================================================
# BACKWARDS-COMPATIBILITY ENDPOINTS (Redirect AI calls to Web Search)
# =========================================================================

class LegacyGenerateImageRequest(BaseModel):
    articleTitle: str = Field(..., description="Title of the article")
    articleContent: Optional[str] = ""
    articleSummary: Optional[str] = ""
    articleCategory: Optional[str] = None
    imagePrompt: Optional[str] = None
    style: Optional[str] = "professional-tech"
    aspectRatio: Optional[str] = "16:9"
    customInstructions: Optional[str] = None
    forceRegenerate: Optional[bool] = False


@router.post("/api/ai/generate-image")
def legacy_generate_image(req: LegacyGenerateImageRequest):
    """
    Backwards compatibility: redirects old AI generation calls to the Web Image Search provider.
    AI image generation is completely disabled.
    """
    res = image_search_manager.find_images_for_article(
        article_title=req.articleTitle,
        article_content=req.articleContent or "",
        article_summary=req.articleSummary or "",
        auto_select=True,
        min_relevance=settings.IMAGE_MIN_RELEVANCE,
    )

    selected = res.get("selectedImage") or (res["candidates"][0] if res.get("candidates") else None)
    if not selected:
        return {
            "success": False,
            "image": "",
            "mimeType": "image/jpeg",
            "altText": req.articleTitle,
            "filename": "no-image.jpg",
            "message": "No relevant web images found.",
            "relevanceScore": 0.0,
            "candidates": res.get("candidates", []),
        }

    img_url = selected.get("url") or selected.get("imageUrl", "")
    return {
        "success": True,
        "image": img_url,
        "mimeType": selected.get("mimeType", "image/jpeg"),
        "altText": selected.get("title", req.articleTitle),
        "filename": selected.get("title", "featured-image")[:30].replace(" ", "-") + ".jpg",
        "promptUsed": selected.get("query", ""),
        "relevanceScore": selected.get("relevanceScore", 80.0),
        "relevanceRating": "Excellent" if selected.get("relevanceScore", 0) >= 80 else "Acceptable",
        "selectedImage": selected,
        "candidates": res.get("candidates", []),
        "message": f"Web image found with relevance {selected.get('relevanceScore', 0):.0f}/100.",
    }


@router.post("/api/ai/craft-image-prompt")
@router.post("/api/ai/analyze-visuals")
def legacy_craft_prompt(req: LegacyGenerateImageRequest):
    """
    Backwards compatibility: returns structured visual search request instead of AI prompt.
    """
    search_req = image_search_manager.generate_search_request(
        article_title=req.articleTitle,
        article_content=req.articleContent or "",
        article_summary=req.articleSummary or "",
    )
    return {
        "prompt": search_req.get("image_query", req.articleTitle),
        "analysis": search_req,
        "category": "Technology",
    }
