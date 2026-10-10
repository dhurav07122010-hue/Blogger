"""
DEPRECATED / REMOVED: Nano Banana AI image generation is completely removed.
Replaced by the Web Image Search System in backend.services.image_search.
All AI image generation, image prompts, SVG synthesis, and pillow graphic banner generation are removed.
"""

from typing import Dict, Any, Optional
from backend.services.image_search import image_search_manager


class NanoBananaImageService:
    def __init__(self):
        pass

    def generate_image(self, *args, **kwargs) -> Dict[str, Any]:
        """AI image generation is completely removed. Redirects to web search."""
        title = kwargs.get("article_title") or (args[0] if args else "Article")
        res = image_search_manager.find_images_for_article(article_title=title, auto_select=True)
        cand = res.get("selectedImage") or (res["candidates"][0] if res.get("candidates") else {})
        return {
            "success": bool(cand),
            "image": cand.get("url", ""),
            "mimeType": cand.get("mimeType", "image/jpeg"),
            "altText": cand.get("title", title),
            "filename": "web-featured-image.jpg",
            "promptUsed": cand.get("query", ""),
            "relevanceScore": cand.get("relevanceScore", 0.0),
            "relevanceRating": "Web Search",
            "visualAnalysis": res.get("searchRequest", {}),
            "message": "AI generation removed; using Web Image Search.",
        }

    def analyze_article_for_visuals(
        self,
        article_title: str,
        article_content: Optional[str] = "",
        article_summary: Optional[str] = "",
        category_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        return image_search_manager.generate_search_request(
            article_title=article_title,
            article_content=article_content,
            article_summary=article_summary,
        )

    def craft_structured_image_prompt(self, *args, **kwargs) -> str:
        return ""


nano_banana_service = NanoBananaImageService()
