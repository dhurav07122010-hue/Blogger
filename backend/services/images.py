"""
Image Service for Blogger AI Agent.
Provides Blogger-compatible responsive image HTML formatting and helpers.
All image generation is topic-driven and handled through the AI image pipeline.
Generic stock photos and placeholder collections are strictly removed.
"""

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger("blogger_agent.images")


class ImageService:
    @staticmethod
    def format_image_html(image_info: Dict[str, Any], is_hero: bool = True) -> str:
        """Format responsive Blogger-compatible HTML figure with licensing and attribution."""
        url = image_info.get("url") or image_info.get("imageUrl") or image_info.get("image", "")
        alt = image_info.get("title") or image_info.get("alt") or image_info.get("altText", "Featured Article Illustration")
        author = image_info.get("author", "")
        license_info = image_info.get("license", "License unknown — verify before commercial/public use.")
        source_name = image_info.get("sourceName", "Web")

        caption_items = []
        if author and author != "Unknown":
            caption_items.append(f"Photo: {author}")
        caption_items.append(f"Source: {source_name}")
        caption_items.append(f"License: {license_info}")
        caption = " • ".join(caption_items)

        max_w = "100%" if is_hero else "90%"
        margin = "20px auto 30px auto"

        return (
            f'<div class="post-image-container separator" style="clear: both; text-align: center; margin: {margin}; max-width: {max_w};">\n'
            f'  <img src="{url}" alt="{alt}" style="width: 100%; max-width: 100%; height: auto; border-radius: 10px; box-shadow: 0 4px 14px rgba(0,0,0,0.12); display: block; margin: 0 auto;" loading="lazy" />\n'
            f'  <p style="font-size: 12px; color: #64748b; font-style: italic; margin-top: 8px; text-align: center;">{caption}</p>\n'
            f'</div>'
        )


image_service = ImageService()
