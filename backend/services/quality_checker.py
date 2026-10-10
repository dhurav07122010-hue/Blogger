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
        factual_score = float(fact_check_result.get("factual_accuracy_score", 90.0))
        seo_score = float(seo_data.get("seo_quality_score", 88.0))

        # Check source quality
        if not research_sources:
            source_quality_score = 70.0
        else:
            verified_count = sum(1 for s in research_sources if s.get("is_verified", True))
            source_quality_score = round(min(100.0, 75.0 + (verified_count / len(research_sources)) * 25.0), 1)

        prompt = f"""
Audit the following blog article draft:

Title: {article_title}
Search Intent: {search_intent}

Article Content (First 6000 chars):
{article_content[:6000]}

Research Sources Summary:
{len(research_sources)} sources supplied.

Fact-Check Score: {factual_score}/100 (Unsupported claims: {fact_check_result.get('unsupported_count', 0)})

Evaluate the following metrics from 0 to 100:
1. "usefulness_score": Practical value, depth of examples, actionable takeaways.
2. "originality_score": Fresh framing, absence of repetitive fluff, absence of obvious verbatim borrowing.
3. "readability_score": Logical progression, clarity, clear subheadings, smooth cadence.
4. "search_intent_match_score": How directly and thoroughly it solves the reader's inquiry.

Also check for safety violations:
- Any medical or financial misinformation?
- Fake personal experiences or fake product reviews?
- Plagiarism or mass-generated thin content characteristics?
- Illegal or deceptive claims?

Return a valid JSON object matching this schema:
{{
  "usefulness_score": 92.0,
  "originality_score": 90.0,
  "readability_score": 91.0,
  "search_intent_match_score": 93.0,
  "originality_notes": "Detailed review of phrasing freshness, structural flow, and lack of generic filler",
  "detected_issues": [
    "List of specific flaws, weak sections, or safety concerns (if any)"
  ],
  "suggestions": [
    "Actionable editorial suggestions to further elevate the quality"
  ],
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

        usefulness_score = float(data.get("usefulness_score", 85.0))
        originality_score = float(data.get("originality_score", 85.0))
        readability_score = float(data.get("readability_score", 85.0))
        intent_score = float(data.get("search_intent_match_score", 85.0))

        detected_issues = data.get("detected_issues", [])
        suggestions = data.get("suggestions", [])
        safety_passed = data.get("safety_passed", True)
        safety_flags = data.get("safety_flags", [])

        # If fact checker detected critical unsupported claims, add to detected issues
        if fact_check_result.get("has_critical_failure", False):
            for c in fact_check_result.get("results", []):
                if c.get("status") == "UNSUPPORTED":
                    detected_issues.append(f"Factual Violation: Unsupported claim detected: '{c.get('claim')}' ({c.get('reason')})")

        # Calculate composite overall score (weighted)
        # Factual Accuracy: 25%
        # Usefulness: 20%
        # Originality: 15%
        # Search Intent: 15%
        # Readability: 10%
        # SEO Quality: 10%
        # Source Quality: 5%
        overall_score = round(
            (factual_score * 0.25)
            + (usefulness_score * 0.20)
            + (originality_score * 0.15)
            + (intent_score * 0.15)
            + (readability_score * 0.10)
            + (seo_score * 0.10)
            + (source_quality_score * 0.05),
            1,
        )

        threshold = settings.QUALITY_THRESHOLD

        # Quality Gate Pass criteria:
        # 1. Overall score >= threshold
        # 2. No critical unsupported claims
        # 3. Safety passed
        passed = (
            (overall_score >= threshold)
            and not fact_check_result.get("has_critical_failure", False)
            and safety_passed
            and len(safety_flags) == 0
        )

        if not passed:
            if overall_score < threshold:
                detected_issues.append(f"Overall Quality Score ({overall_score:.1f}) is below mandatory threshold ({threshold}).")
            if not safety_passed:
                detected_issues.append(f"Safety gate failed due to flagged items: {', '.join(safety_flags)}")

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
            "input_tokens": in_tok,
            "output_tokens": out_tok,
        }


quality_checker = QualityChecker()
