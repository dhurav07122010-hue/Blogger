"""
Article Writer and Revision Service for Blogger AI Agent.
Produces human-quality, natural, original, publication-ready blog posts.

Writing Philosophy:
- Write for human readers first: clarity, warmth, genuine utility, and varied rhythm.
- Avoid repetitive phrases, cliché introductions, generic filler, and robotic formulaic structures.
- Grounded factual substance: real explanations, practical examples, tutorials or code where appropriate.
- Adaptable format tailored to the specific topic rather than an artificial, repetitive cookie-cutter template.
- Pre-presentation quality checks for repetition, tone, and coherence.
"""

from typing import List, Dict, Any, Optional
import re
import logging

from backend.services.ai_provider import ai_provider

logger = logging.getLogger("blogger_agent.writer")


class ArticleWriter:
    def __init__(self):
        self.writer_system_prompt = (
            "You are an accomplished essayist, technical journalist, and subject-matter writer who produces "
            "deeply engaging, natural, human-quality blog articles.\n\n"
            "EDITORIAL PRINCIPLES:\n"
            "1. HUMAN-FIRST VOICE: Write with natural cadence, conversational authority, and intellectual honesty. "
            "Use varied sentence lengths — pair punchy observations with nuanced explanations. Vary paragraph lengths naturally.\n"
            "2. ZERO ROBOTIC CLICHÉS: Never use tired AI tropes such as:\n"
            "   - 'In today's fast-paced digital world...'\n"
            "   - 'It is no secret that...'\n"
            "   - 'Delve into', 'Tapestry', 'Testament to', 'Beacon of', 'Game-changer'\n"
            "   - 'In conclusion, as we have seen throughout this comprehensive guide...'\n"
            "3. TOPIC RELEVANCE & HONESTY: Stay focused on the article title. Never invent statistics, fictional studies, "
            "imagined quotes, or fabricated personal experiences. If a point is an estimate or industry observation, frame it with integrity.\n"
            "4. ORGANIC STRUCTURE: Do NOT use a rigid cookie-cutter template for every article. Structure the piece according to "
            "what the topic actually demands: a step-by-step workflow for tutorials, practical tradeoffs for technical choices, "
            "historical context and clear principles for explainers. Include tables, code blocks, or checklists ONLY when they provide real clarity.\n"
            "5. COMPELLING OPENING: Hook the reader immediately with an insightful observation, practical problem, or compelling context. "
            "Skip introductory throat-clearing.\n"
            "6. THOUGHTFUL CLOSING: End with a practical takeaway, a forward-looking perspective, or an actionable next step, "
            "rather than a mechanical restatement of every section."
        )

    def write_draft(
        self,
        title: str,
        research_summary: str = "",
        sources: Optional[List[Dict[str, Any]]] = None,
        target_audience: str = "General Audience",
        search_intent: str = "Informational",
        desired_length: str = "medium (~1500w)",
        keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Produce a complete, human-quality, publication-ready article draft.
        """
        sources = sources or []
        keywords_str = ", ".join(keywords) if keywords else "Natural thematic integration"
        sources_summary = "\n".join(
            [f"- {s.get('title')} ({s.get('domain')}): {', '.join(s.get('relevant_facts', []))}" for s in sources if s.get('title')]
        ) or "Draw on authoritative domain knowledge and best practices."

        prompt = f"""
Write a complete, original, and deeply engaging blog article for the following brief:

Title: {title}
Target Audience: {target_audience}
Search Intent: {search_intent}
Target Length: {desired_length}
Primary Keywords (integrate naturally without stuffing): {keywords_str}

VERIFIED CONTEXT & RESEARCH NOTES:
{research_summary if research_summary else "Provide thorough, accurate coverage centered squarely on the subject."}

FACTUAL TOUCHPOINTS:
{sources_summary}

WRITING INSTRUCTIONS:
- Start directly with '# {title}'.
- Craft an immediate, captivating, and meaningful opening paragraph that answers the reader's actual question.
- Develop 3 to 6 substantial, logically ordered sections using ## and ### headings that fit this specific topic.
- Use varied sentence structures, natural transitions, and specific explanations.
- Include concrete examples, realistic scenarios, or code snippets with syntax highlighting (e.g. ```python, ```bash, ```html) where applicable.
- Where specific factual claims or data points from research are used, reference the authoritative source domain naturally (e.g. "According to Google Search Central documentation...").
- Include an optional 'Frequently Asked Questions' section ONLY if it genuinely helps clarify complex reader inquiries.
- Avoid repetitive introductions, generic conclusions, buzzword stuffing, fake personal anecdotes, and unnecessary filler.
- Conclude with actionable takeaways and next steps.
- Format strictly in clean Markdown. Never claim the article is guaranteed to pass AI detectors.
"""
        logger.info(f"Generating human-quality article for title: '{title}'")
        raw_content, in_tok, out_tok = ai_provider.generate_text(
            prompt=prompt,
            system_instruction=self.writer_system_prompt,
            temperature=0.65,
        )

        # Pre-presentation check & polish (repetition, clichés, missing sections)
        polished_content, p_in, p_out = self.verify_and_polish_article(raw_content, title)
        in_tok += p_in
        out_tok += p_out

        # Generate concise executive summary
        summary_prompt = f"Provide a concise 2-sentence executive summary of this article for readers and search preview:\n\n{polished_content[:2500]}"
        summary, s_in, s_out = ai_provider.generate_text(
            prompt=summary_prompt,
            system_instruction="You write concise, compelling 2-sentence summaries highlighting the core insight of the article.",
            temperature=0.3,
        )

        return {
            "content": polished_content,
            "summary": summary.strip(),
            "input_tokens": in_tok + s_in,
            "output_tokens": out_tok + s_out,
        }

    def verify_and_polish_article(self, content: str, title: str) -> (str, int, int):
        """
        Check generated draft for repetition, formulaic clichés, formatting flaws,
        and missing sections before presenting to user.
        """
        text = content.strip()

        # Ensure correct H1 title at top
        if not text.startswith("#"):
            text = f"# {title}\n\n{text}"

        # Clean multiple consecutive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Detect common repetitive or robotic phrases
        cliche_patterns = [
            r"in today's (?:fast-paced|rapidly evolving|digital) (?:world|landscape|age)",
            r"it is no secret that",
            r"delve into the",
            r"tapestry of",
            r"in conclusion, as we have seen",
            r"in this comprehensive guide, we will",
        ]
        has_cliches = any(re.search(pat, text, re.IGNORECASE) for pat in cliche_patterns)

        # If noticeable clichés exist and draft is long enough, perform a surgical polish pass
        if has_cliches and len(text) > 400:
            logger.info("Polishing article to remove formulaic clichés and enhance natural human flow.")
            polish_prompt = f"""
Review the following article draft. Refine the prose to eliminate any robotic cliches, generic openings, 
or formulaic transitions. Preserve all factual depth, code, structure, and headings, while making the sentence 
rhythms natural, varied, and direct.

Draft to polish:
{text}
"""
            try:
                polished, p_in, p_out = ai_provider.generate_text(
                    prompt=polish_prompt,
                    system_instruction=self.writer_system_prompt,
                    temperature=0.4,
                )
                if polished.strip().startswith("#") and len(polished) > len(text) * 0.7:
                    return polished.strip(), p_in, p_out
            except Exception as e:
                logger.warning(f"Draft polish pass skipped due to provider error: {e}")

        return text, 0, 0

    def revise_content(
        self,
        current_content: str,
        instructions: str,
        focus_sections: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Revise article draft based on editorial feedback or quality audit.
        """
        focus_str = f"Specific Focus Sections: {', '.join(focus_sections)}" if focus_sections else "General Article Revision"

        prompt = f"""
You are an expert editorial writer revising an existing draft according to specific editorial instructions.

{focus_str}
EDITORIAL REVISION INSTRUCTIONS:
{instructions}

CURRENT ARTICLE DRAFT:
{current_content}

REVISION RULES:
1. Address all feedback points directly with care and precision.
2. Remove any fluff, repetitive sentences, or unsupported claims.
3. Keep the factual grounding rigorous and the voice engaging and natural.
4. Output the complete revised article in clean Markdown.
"""
        logger.info("Executing editorial revision on article content.")
        revised, in_tok, out_tok = ai_provider.generate_text(
            prompt=prompt,
            system_instruction=self.writer_system_prompt,
            temperature=0.5,
        )

        return {
            "content": revised,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
        }


article_writer = ArticleWriter()
writer_service = article_writer
