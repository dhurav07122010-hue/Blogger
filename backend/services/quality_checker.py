"""
Comprehensive Quality and Originality Reviewer for Blogger AI Agent.
Evaluates 7 distinct quality dimensions (0-100):
1. Factual Accuracy
2. Usefulness
3. Originality (anti-copying, no generic filler, no idea duplication)
4. Readability
5. Search Intent Match
6. SEO Quality
7. Source Quality

Rules:
- Strictly does NOT use pseudo-scientific 'AI-detector' tools.
- Evaluates intrinsic editorial merit: depth, substance, duplication, structure, safety.
- Flags harmful domains: medical/financial misinformation, fake reviews, illegalities.
- Enforces Quality Gate Threshold (default >= 85).
"""

from typing import List, Dict, Any, Optional
from backend.services.ai_provider import ai_provider
from backend.config import settings
import logging

logger = logging.getLogger("blogger_agent.quality_checker")


class QualityChecker:
    def __init__(self):
        self.system_prompt = (
            "You are a Senior Editor-in-Chief and Publication Safety Officer. "
            "Your task is to conduct an uncompromising audit of a blog draft across editorial value, originality, and safety.\n"
            "DO NOT evaluate whether text is 'AI-written'. Instead evaluate the tangible quality of the writing:\n"
            "- Originality: Are ideas duplicated? Is there excessive verbatim copying from sources? Is there generic fluff?\n"
            "- Usefulness: Does it solve a real problem with practical substance and actionable insights?\n"
            "- Readability: Is the prose clear, well-structured, logically ordered, and pleasant to read?\n"
            "- Search Intent: Does it genuinely satisfy why someone searched for this topic?\n"
            "- Source Quality: Are citations authoritative and accurately represented?\n"
            "- Safety: Reject any medical/financial dangerous advice, scams, fake reviews, or illegal conduct.\n"
            "Return strictly valid JSON."
        )

    def evaluate_quality(
        self,
        article_title: str,
        article_content: str,
        research_sources: List[Dict[str, Any]],
        fact_check_result: Dict[str, Any],
        seo_data: Dict[str, Any],
        search_intent: str = "Informational",
    ) -> Dict[str, Any]:
        """
        Evaluate full multi-dimensional quality scores, detected issues, and pass/fail gate status.
        """
        words_count = len((article_content or "").split())
        unsupported_count = int(fact_check_result.get("unsupported_count", 0))

        # 1. Source Quality Scoring based on real evidence
        if not research_sources:
            source_quality_score = 25.0
        else:
            verified_count = sum(1 for s in research_sources if s.get("is_verified", False))
            total_sources = len(research_sources)
            # Baseline: 40 + (verified_ratio * 40) + (min(total_sources, 5) * 4)
            source_quality_score = round(min(100.0, 40.0 + (verified_count / total_sources * 40.0) + (min(total_sources, 5) * 4.0)), 1)

        # 2. Factual Accuracy
        factual_score = float(fact_check_result.get("factual_accuracy_score", 90.0))
        if unsupported_count > 0:
            factual_score = max(0.0, min(factual_score, 60.0 - (unsupported_count * 15.0)))

        seo_score = float(seo_data.get("seo_quality_score", 85.0))

        prompt = f"""
Audit the following blog article draft for editorial merit, depth, and originality:

Title: {article_title}
Search Intent: {search_intent}
Word Count: {words_count} words
Sources Supplied: {len(research_sources)} ({sum(1 for s in research_sources if s.get('is_verified', False))} verified)
Fact Check: {unsupported_count} unsupported claims detected.

Article Content Preview:
{article_content[:5000]}

Evaluate the following metrics honestly from 0 to 100:
1. "usefulness_score": Practical substance, real solutions, code/examples if relevant. (Deduct if shallow or generic).
2. "originality_score": Distinctive voice, lack of repetitive robotic clichés and boilerplate fluff.
3. "readability_score": Logical organization, heading structure, paragraph flow, clear transition.
4. "search_intent_match_score": Directness and thoroughness in satisfying reader query.

Safety check:
- Flag any misinformation, deceptive claims, illegal guidance, or keyword stuffing.

Return valid JSON:
{{
  "usefulness_score": 85.0,
  "originality_score": 85.0,
  "readability_score": 85.0,
  "search_intent_match_score": 85.0,
  "originality_notes": "Specific notes on phrasing and structure",
  "detected_issues": [],
  "suggestions": [],
  "safety_passed": true,
  "safety_flags": []
}}
"""
        logger.info(f"Running quality evaluation for '{article_title}'")
        data, in_tok, out_tok = ai_provider.generate_json(
            prompt=prompt,
            system_instruction=self.system_prompt,
            temperature=0.2,
        )

        usefulness_score = float(data.get("usefulness_score", 80.0))
        originality_score = float(data.get("originality_score", 80.0))
        readability_score = float(data.get("readability_score", 82.0))
        intent_score = float(data.get("search_intent_match_score", 82.0))

        detected_issues = data.get("detected_issues", [])
        suggestions = data.get("suggestions", [])
        safety_passed = data.get("safety_passed", True)
        safety_flags = data.get("safety_flags", [])

        # Strict Penalties for Deficiencies
        if words_count < 350:
            usefulness_score = min(usefulness_score, 50.0)
            detected_issues.append(f"Insufficient Depth: Article is only {words_count} words, which does not provide adequate depth for publication.")
        elif words_count < 600:
            usefulness_score = min(usefulness_score, 75.0)

        if not research_sources:
            detected_issues.append("Zero Research Sources: No authoritative research citations or external evidence were cataloged.")

        if fact_check_result.get("has_critical_failure", False) or unsupported_count > 0:
            for c in fact_check_result.get("results", []):
                if c.get("status") == "UNSUPPORTED":
                    detected_issues.append(f"Factual Violation: Unsupported claim: '{c.get('claim')}' ({c.get('reason')})")

        # Calculate composite overall score (weighted)
        # Factual Accuracy: 25%
        # Usefulness: 20%
        # Originality: 15%
        # Search Intent: 15%
        # Readability: 10%
        # SEO Quality: 10%
        # Source Quality: 5%
        raw_overall = (
            (factual_score * 0.25)
            + (usefulness_score * 0.20)
            + (originality_score * 0.15)
            + (intent_score * 0.15)
            + (readability_score * 0.10)
            + (seo_score * 0.10)
            + (source_quality_score * 0.05)
        )

        # Caps: an article with unsupported claims or 0 sources cannot score high
        if unsupported_count > 0:
            raw_overall = min(raw_overall, 64.0)
        elif not research_sources:
            raw_overall = min(raw_overall, 72.0)

        overall_score = round(raw_overall, 1)
        threshold = settings.QUALITY_THRESHOLD

        # Quality Gate Pass criteria:
        passed = (
            (overall_score >= threshold)
            and not fact_check_result.get("has_critical_failure", False)
            and unsupported_count == 0
            and safety_passed
            and len(safety_flags) == 0
        )

        if not passed:
            if overall_score < threshold:
                detected_issues.append(f"Overall Quality Score ({overall_score:.1f}) is below mandatory threshold ({threshold}).")
            if not safety_passed:
                detected_issues.append(f"Safety gate failed: {', '.join(safety_flags)}")

        return {
            "factual_accuracy_score": factual_score,
            "usefulness_score": usefulness_score,
            "originality_score": originality_score,
            "readability_score": readability_score,
            "search_intent_match_score": intent_score,
            "seo_quality_score": seo_score,
            "source_quality_score": source_quality_score,
            "overall_score": overall_score,
            "passed": passed,
            "originality_notes": data.get("originality_notes", "Passed originality review."),
            "detected_issues": detected_issues,
            "suggestions": suggestions,
            "safety_passed": safety_passed,
            "safety_flags": safety_flags,
            "score_breakdown": {
                "factual_accuracy": {"score": factual_score, "weight": 25, "unsupported_claims": unsupported_count},
                "usefulness": {"score": usefulness_score, "weight": 20, "word_count": words_count},
                "originality": {"score": originality_score, "weight": 15},
                "search_intent": {"score": intent_score, "weight": 15},
                "readability": {"score": readability_score, "weight": 10},
                "seo_quality": {"score": seo_score, "weight": 10},
                "source_quality": {"score": source_quality_score, "weight": 5, "sources_count": len(research_sources)},
            },
            "input_tokens": in_tok,
            "output_tokens": out_tok,
        }


quality_checker = QualityChecker()
