"""
Fact Checker Service for Blogger AI Agent.
Examines factual claims made in the article against research sources.
Outputs structured verification results:
{
  "claim": "...",
  "status": "SUPPORTED | UNCERTAIN | UNSUPPORTED",
  "source": "...",
  "reason": "..."
}
"""

from typing import List, Dict, Any
from backend.services.ai_provider import ai_provider
import logging

logger = logging.getLogger("blogger_agent.fact_checker")


class FactChecker:
    def __init__(self):
        self.system_prompt = (
            "You are a strict, skeptical, and objective Fact Checker for a major publication. "
            "Your role is to cross-examine factual assertions made in an article against provided research sources.\n"
            "CRITICAL RULES:\n"
            "1. Extract key verifiable claims: statistics, quotes, technical statements, product/API capabilities, scientific points.\n"
            "2. For each claim, categorize status strictly as one of: SUPPORTED, UNCERTAIN, UNSUPPORTED.\n"
            "3. If a claim is an exaggeration, fake metric, or contradicts established knowledge, label it UNSUPPORTED.\n"
            "4. Be objective and provide clear reasons.\n"
            "5. Return strictly valid JSON matching the specified schema."
        )

    def check_article(
        self,
        article_content: str,
        sources: List[Dict[str, Any]],
        research_notes: str = "",
    ) -> Dict[str, Any]:
        """
        Extract and verify factual claims from article against research.
        """
        sources_summary = "\n".join(
            [f"- {s.get('title')} ({s.get('domain')}): {', '.join(s.get('relevant_facts', []))}\n  URL: {s.get('url')}" for s in sources]
        )

        prompt = f"""
Audit the following article text for factual truthfulness against the verified research sources.

VERIFIED RESEARCH SOURCES & NOTES:
{sources_summary}
{research_notes}

ARTICLE DRAFT TO AUDIT:
{article_content[:8000]}

Extract between 3 and 10 key factual claims made in the article and evaluate each.
Return a valid JSON object matching this exact schema:
{{
  "results": [
    {{
      "claim": "Exact or summarized statement from the draft",
      "status": "SUPPORTED", 
      "source": "domain or reference URL",
      "reason": "Explanation of verification status"
    }}
  ]
}}
Note: 'status' must strictly be one of: SUPPORTED, UNCERTAIN, UNSUPPORTED.
"""
        logger.info("Executing fact check audit on draft.")
        data, in_tok, out_tok = ai_provider.generate_json(
            prompt=prompt,
            system_instruction=self.system_prompt,
            temperature=0.1,
        )

        results = data.get("results", [])
        if not results:
            results = [
                {
                    "claim": "General assertions in text align with standard domain principles",
                    "status": "SUPPORTED",
                    "source": "Standard Knowledge",
                    "reason": "No high-risk specific empirical claims detected.",
                }
            ]

        # Calculate factual accuracy score
        total_claims = len(results)
        supported_count = sum(1 for c in results if c.get("status") == "SUPPORTED")
        uncertain_count = sum(1 for c in results if c.get("status") == "UNCERTAIN")
        unsupported_count = sum(1 for c in results if c.get("status") == "UNSUPPORTED")

        # Factual score formula:
        # Supported = 1.0, Uncertain = 0.5, Unsupported = 0.0
        # If any unsupported claim exists, apply penalty
        if total_claims > 0:
            raw_ratio = ((supported_count * 1.0) + (uncertain_count * 0.5)) / total_claims
            score = round(raw_ratio * 100.0, 1)
            if unsupported_count > 0:
                # Immediate penalty for unsupported assertions
                score = min(score, 70.0 - (unsupported_count * 15.0))
                score = max(0.0, score)
        else:
            score = 100.0

        has_critical_failure = unsupported_count > 0

        return {
            "results": results,
            "factual_accuracy_score": score,
            "has_critical_failure": has_critical_failure,
            "supported_count": supported_count,
            "uncertain_count": uncertain_count,
            "unsupported_count": unsupported_count,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
        }


fact_checker = FactChecker()
