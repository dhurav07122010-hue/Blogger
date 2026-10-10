"""
SEO Reviewer Service for Blogger AI Agent.
Evaluates and creates clean, people-first search engine metadata.
Rules:
- NO keyword stuffing.
- Reject clickbait or misleading titles/descriptions.
- Produce clean URL slugs, structured headings, FAQs, and internal linking suggestions.
"""

from typing import List, Dict, Any, Optional
from backend.services.ai_provider import ai_provider
import re
import logging

logger = logging.getLogger("blogger_agent.seo")


def slugify(text: str) -> str:
    """Generate a clean URL slug from text."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


class SEOReviewer:
    def __init__(self):
        self.system_prompt = (
            "You are an ethical, senior Technical SEO Specialist focusing on Google Search Central guidelines. "
            "You optimize for reader satisfaction, clarity, and genuine topic relevance.\n"
            "MANDATORY CRITERIA:\n"
            "1. NO keyword stuffing or awkward keyword insertion.\n"
            "2. NO deceptive clickbait, false urgency ('You won't believe this!'), or hyperbole.\n"
            "3. Titles must be under 65 characters and clearly state the article's benefit.\n"
            "4. Meta descriptions must be concise (140-160 characters) and summarize the core value accurately.\n"
            "5. Include relevant FAQs and logical internal linking anchor suggestions.\n"
            "6. Return strictly valid JSON."
        )

    def review_and_optimize(
        self,
        title: str,
        content: str,
        primary_keywords: Optional[List[str]] = None,
        search_intent: str = "Informational",
    ) -> Dict[str, Any]:
        """
        Generate SEO metadata and evaluate SEO score.
        """
        kw_str = ", ".join(primary_keywords) if primary_keywords else "Natural topic themes"

        prompt = f"""
Audit the following blog draft and generate high-standard SEO metadata according to Google Search Central quality benchmarks:

Title: {title}
Intended Keywords: {kw_str}
Search Intent: {search_intent}

Draft Snippet (First 3500 characters):
{content[:3500]}

Return a valid JSON object matching this schema:
{{
  "seo_title": "Clean, compelling title under 65 chars (no clickbait)",
  "meta_description": "Accurate meta description between 140-160 chars",
  "url_slug": "url-friendly-slug-with-hyphens",
  "h1": "Exact suggested H1",
  "h2_structure": [
    "Section 1 title",
    "Section 2 title",
    "Section 3 title"
  ],
  "primary_topic": "Identified core topic",
  "related_terms": ["semantic term 1", "semantic term 2", "semantic term 3"],
  "faq_suggestions": [
    {{
      "question": "Common reader question directly answered by article?",
      "answer": "Concise factual answer (1-2 sentences)"
    }}
  ],
  "internal_link_suggestions": [
    {{
      "anchor": "Recommended anchor phrase",
      "topic": "Related topic or category"
    }}
  ],
  "seo_quality_score": 92.0,
  "is_clickbait_or_misleading": false,
  "seo_feedback": "Brief evaluation of keyword naturalness and structural hierarchy"
}}
"""
        logger.info(f"Generating SEO audit for title: {title}")
        data, in_tok, out_tok = ai_provider.generate_json(
            prompt=prompt,
            system_instruction=self.system_prompt,
            temperature=0.3,
        )

        seo_title = data.get("seo_title") or title
        url_slug = data.get("url_slug") or slugify(seo_title)
        seo_score = float(data.get("seo_quality_score", 88.0))

        # Check for clickbait penalty
        if data.get("is_clickbait_or_misleading", False):
            seo_score = min(seo_score, 60.0)

        data["url_slug"] = slugify(url_slug)
        data["seo_quality_score"] = seo_score
        data["input_tokens"] = in_tok
        data["output_tokens"] = out_tok

        return data


seo_reviewer = SEOReviewer()
