"""
Research Analyst Service for Blogger AI Agent.
Collects, structures, and validates authoritative sources and factual notes.
Rules:
- Never invents sources or fabricate citations.
- Clearly flags unverified claims if authoritative source is unavailable.
- Prioritizes official docs, peer-reviewed knowledge, and reputable industry domains.
"""

from typing import List, Dict, Any, Optional
import urllib.parse
from backend.services.ai_provider import ai_provider
from backend.config import settings
import logging

logger = logging.getLogger("blogger_agent.research")


class ResearchAnalyst:
    def __init__(self):
        self.system_prompt = (
            "You are a meticulous, ethics-focused Research Analyst for a high-quality blog publication. "
            "Your objective is to assemble verified, truthful, and authoritative background information on a given topic. "
            "STRICT RULES:\n"
            "1. NEVER invent sources, fake authors, or bogus URLs. If you do not have an exact live URL, use the authoritative root domain or documentation portal (e.g., https://developers.google.com/search or https://www.w3.org).\n"
            "2. NEVER make claims that a source supports something unless it is objectively true and standard knowledge in that field.\n"
            "3. If any factual claim is tentative or cannot be fully verified, mark it with '[Requires Verification]'.\n"
            "4. Return strictly structured JSON containing 'sources' and 'research_summary'.\n"
            "5. Focus on practical insights, technical reality, search intent satisfaction, and reader benefit."
        )

    def conduct_research(
        self,
        topic: str,
        target_audience: str = "General Audience",
        country_region: str = "Global",
        search_intent: str = "Informational",
        desired_length: str = "medium (~1500w)",
        keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze topic and produce structured research dossier with real live web sources.
        """
        from backend.services.search_engine import live_research_engine

        # If in Demo Mode without internet, provide simulated response if needed
        if settings.DEMO_MODE and not settings.GEMINI_API_KEY:
            logger.info(f"Conducting research on topic: {topic} (Demo Mode)")
            data, in_tok, out_tok = ai_provider.generate_json(
                prompt=f"Research topic: {topic}",
                system_instruction=self.system_prompt,
                temperature=0.2,
            )
            return {
                "sources": data.get("sources", []),
                "research_summary": data.get("research_summary", ""),
                "contradictions_or_caveats": [],
                "live_internet_used": False,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
            }

        return live_research_engine.conduct_deep_research(
            topic=topic,
            target_audience=target_audience,
            country_region=country_region,
            search_intent=search_intent,
            desired_length=desired_length,
            keywords=keywords,
        )


research_analyst = ResearchAnalyst()
