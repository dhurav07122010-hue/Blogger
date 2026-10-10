"""
Gemini API service using the official google-genai SDK.
Features:
- Never logs or exposes API keys
- Exponential backoff with maximum 3 retries
- Rate-limit (429) and quota error handling
- Structured JSON and Markdown content generation
- Token usage tracking and cost estimation
- Seamless fallback to deterministic Demo Mode if credentials are absent
"""

import json
import logging
import random
import time
from typing import Any, Dict, Optional, Tuple
from google import genai
from google.genai import types
from google.genai.errors import APIError

from backend.config import settings

logger = logging.getLogger("blogger_agent.gemini")
logger.setLevel(logging.INFO)


class TokenTracker:
    def __init__(self):
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_api_calls: int = 0
        self.last_call_time: Optional[float] = None

    def add_usage(self, prompt_tokens: int, completion_tokens: int):
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_api_calls += 1
        self.last_call_time = time.time()

    def get_summary(self) -> Dict[str, Any]:
        # Estimation based on Gemini 2.5 Flash / 1.5 Flash public rates:
        # Prompt: ~$0.075 / 1M tokens, Completion: ~$0.30 / 1M tokens
        est_cost = (self.total_prompt_tokens * 0.000000075) + (self.total_completion_tokens * 0.00000030)
        return {
            "total_calls": self.total_api_calls,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "estimated_cost_usd": round(est_cost, 6),
            "last_call_time": self.last_call_time,
        }


tracker = TokenTracker()


class GeminiService:
    def __init__(self):
        self._client: Optional[genai.Client] = None
        self._init_client()

    def _init_client(self):
        if settings.GEMINI_API_KEY:
            try:
                # Do NOT log the API key!
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logger.info("Initialized Google GenAI client successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize GenAI client: {str(e)}")
                self._client = None
        else:
            self._client = None

    @property
    def is_configured(self) -> bool:
        return self._client is not None and bool(settings.GEMINI_API_KEY)

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> Tuple[str, int, int]:
        """
        Generate raw text/markdown using centralized AI provider.
        Returns (text, estimated_input_tokens, estimated_output_tokens).
        """
        if settings.DEMO_MODE and not self.is_configured:
            logger.info("Operating in Demo Mode for generate_text.")
            return self._demo_fallback_text(prompt), 100, 400

        from backend.services.ai_provider import ai_provider
        text, in_tok, out_tok = ai_provider.generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            max_retries=max_retries,
        )
        tracker.add_usage(in_tok, out_tok)
        return text, in_tok, out_tok

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_retries: int = 3,
    ) -> Tuple[Dict[str, Any], int, int]:
        """
        Generate structured JSON using centralized AI provider.
        Returns (parsed_dict, estimated_input_tokens, estimated_output_tokens).
        """
        if settings.DEMO_MODE and not self.is_configured:
            logger.info("Operating in Demo Mode for generate_json.")
            return self._demo_fallback_json(prompt), 100, 200

        from backend.services.ai_provider import ai_provider
        data, in_tok, out_tok = ai_provider.generate_json(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            max_retries=max_retries,
        )
        tracker.add_usage(in_tok, out_tok)
        return data, in_tok, out_tok

    def _demo_fallback_text(self, prompt: str) -> str:
        """Fallback simulation for offline / test / demo execution."""
        return (
            "# Comprehensive Guide: Essential Strategies and Practical Insights\n\n"
            "## Introduction\n"
            "Navigating modern technological challenges requires a rigorous, structured approach. "
            "Whether you are optimizing organizational workflows or deploying reliable digital tools, "
            "grounding every decision in verified data produces superior long-term results.\n\n"
            "## Core Principles and Methodologies\n"
            "1. **Factual Integrity**: Ensuring information is cross-referenced with primary documentation.\n"
            "2. **Pragmatic Application**: Focusing on actionable advice rather than superficial theoretical filler.\n"
            "3. **Sustainable Performance**: Architecting lightweight solutions that avoid wasteful resource consumption.\n\n"
            "## Practical Implementation Steps\n"
            "To achieve optimal outcomes, implement changes iteratively. Begin by establishing measurable benchmarks, "
            "evaluating performance bottlenecks, and reviewing feedback loops systematically.\n\n"
            "## Conclusion\n"
            "By adhering to empirical standards and focusing on clarity, you create lasting value for your readers and stakeholders."
        )

    def _demo_fallback_json(self, prompt: str) -> Dict[str, Any]:
        """Contextual fallback dictionary for simulation."""
        prompt_lower = prompt.lower()
        if "seo" in prompt_lower or "meta_description" in prompt_lower:
            return {
                "seo_title": "Mastering Helpful Content and Modern Blogging Best Practices",
                "meta_description": "Discover actionable, verified strategies for creating high-quality, people-first content that resonates with readers and aligns with Google search guidelines.",
                "url_slug": "mastering-helpful-content-best-practices",
                "h1": "Mastering Helpful Content: Verified Strategies for Digital Creators",
                "h2_structure": [
                    "Understanding Search Intent and User Needs",
                    "Core Principles of Factual Accuracy",
                    "Step-by-Step Implementation Framework",
                    "Actionable Next Steps"
                ],
                "primary_topic": "Helpful Content Guidelines",
                "related_terms": ["search intent", "content quality", "factual accuracy", "blogger draft"],
                "faq_suggestions": [
                    {
                        "question": "Why is factual verification crucial for blog quality?",
                        "answer": "Factual verification protects reader trust, avoids misinformation, and adheres to quality guidelines."
                    }
                ],
                "internal_link_suggestions": [
                    {"anchor": "Blogger API Guide", "topic": "API Integration"}
                ],
                "seo_quality_score": 92.0,
                "is_clickbait_or_misleading": False,
                "seo_feedback": "Strong structural hierarchy and natural query alignment."
            }
        elif "research" in prompt_lower or "sources" in prompt_lower:
            return {
                "sources": [
                    {
                        "title": "Google Search Central: Creating Helpful, Reliable, People-First Content",
                        "url": "https://developers.google.com/search/docs/fundamentals/creating-helpful-content",
                        "domain": "developers.google.com",
                        "publication_date": "2024",
                        "relevant_facts": [
                            "Google rewards content created primarily for people rather than search engines.",
                            "Original information, reporting, research, or analysis provides highest user value.",
                            "Avoiding deceptive practices and thin content prevents ranking penalties."
                        ],
                        "notes": "Official search documentation on content quality and search intent."
                    },
                    {
                        "title": "Blogger API v3 Official Developer Documentation",
                        "url": "https://developers.google.com/blogger/docs/3.0/reference",
                        "domain": "developers.google.com",
                        "publication_date": "2024",
                        "relevant_facts": [
                            "Blogger API v3 supports creating draft posts with isDraft=true query parameter.",
                            "OAuth 2.0 authentication allows granular scope management for content posting."
                        ],
                        "notes": "Verified API endpoints for draft management."
                    }
                ],
                "research_summary": "Extracted key developer documentation verifying helpful content guidelines and safe API draft mechanics."
            }
        elif "fact" in prompt_lower or "claim" in prompt_lower:
            return {
                "results": [
                    {
                        "claim": "Google search systems prioritize content that demonstrates first-hand experience and expertise.",
                        "status": "SUPPORTED",
                        "source": "developers.google.com",
                        "reason": "Directly confirmed by Google Search Central Helpful Content documentation."
                    },
                    {
                        "claim": "The Blogger API allows inserting posts as drafts without immediate public publishing.",
                        "status": "SUPPORTED",
                        "source": "developers.google.com",
                        "reason": "Verified in Blogger API v3 specification using isDraft=true."
                    }
                ]
            }
        elif "quality" in prompt_lower or "score" in prompt_lower or "audit" in prompt_lower:
            return {
                "factual_accuracy_score": 95.0,
                "usefulness_score": 92.0,
                "originality_score": 90.0,
                "readability_score": 88.0,
                "search_intent_match_score": 94.0,
                "seo_quality_score": 90.0,
                "source_quality_score": 95.0,
                "overall_score": 92.0,
                "passed": True,
                "detected_issues": [],
                "suggestions": ["Add code snippet or visual diagrams to deepen practical value."]
            }
        return {"status": "ok", "message": "Demo simulated response completed."}


gemini_service = GeminiService()
