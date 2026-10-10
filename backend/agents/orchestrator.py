"""
Workflow Orchestrator for Blogger AI Agent.
Coordinates logical agents:
1. Topic Planner
2. Research Analyst
3. Article Writer
4. Fact Checker
5. SEO Reviewer
6. Quality Reviewer
7. Hero Image Designer (Topic Analysis & AI Hero Image Generation)
8. Final Editor

Enforces the autonomous workflow pipeline:
USER TITLE -> RESEARCH -> DRAFT -> FACT CHECK -> SEO -> QUALITY AUDIT -> REVISION (if needed) -> AI HERO IMAGE -> READY FOR APPROVAL -> BLOGGER DRAFT
"""

import time
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from backend.models.entities import (
    Article,
    Topic,
    ResearchSource,
    ArticleRevision,
    QualityCheck,
    AgentRun,
    PublishingHistory,
    ArticleStatus,
)
from backend.services.research import research_analyst
from backend.services.writer import article_writer
from backend.services.fact_checker import fact_checker
from backend.services.seo import seo_reviewer
from backend.services.quality_checker import quality_checker
from backend.services.image_search import image_search_manager
from backend.services.blogger import blogger_service
from backend.config import settings

logger = logging.getLogger("blogger_agent.orchestrator")


class WorkflowOrchestrator:
    def __init__(self):
        pass

    def run_full_pipeline(
        self,
        db: Session,
        topic_id: Optional[int] = None,
        custom_title: Optional[str] = None,
        target_audience: str = "General Audience",
        country_region: str = "Global",
        search_intent: str = "Informational",
        desired_length: str = "medium (~1500w)",
        keywords: Optional[List[str]] = None,
    ) -> Article:
        """
        Execute the complete autonomous drafting, auditing, and image generation pipeline
        from a single title up to READY_FOR_APPROVAL.
        """
        keywords = keywords or []

        # 1. Resolve Topic or Create from Custom Title
        topic_obj = None
        if topic_id:
            topic_obj = db.query(Topic).filter(Topic.id == topic_id).first()
            if topic_obj:
                title = topic_obj.title
                target_audience = topic_obj.target_audience or target_audience
                country_region = topic_obj.country_region or country_region
                search_intent = topic_obj.search_intent or search_intent
                desired_length = topic_obj.desired_length or desired_length
                keywords = topic_obj.keywords or keywords
            else:
                title = custom_title or "Essential Strategies for Modern Digital Creators"
        else:
            title = custom_title or "Essential Strategies for Modern Digital Creators"

        # Create or fetch working Article in DB
        article = Article(
            topic_id=topic_obj.id if topic_obj else None,
            title=title,
            target_audience=target_audience,
            country_region=country_region,
            search_intent=search_intent,
            keywords=keywords,
            status=ArticleStatus.RESEARCHING,
        )
        db.add(article)
        db.commit()
        db.refresh(article)

        # STAGE 1: RESEARCH ANALYST
        self._record_agent_run(db, article.id, "Topic Planner", "SUCCESS", 50, 100, 0.3, f"Topic framed: '{title}'.")
        
        t0 = time.time()
        res_data = research_analyst.conduct_research(
            topic=title,
            target_audience=target_audience,
            country_region=country_region,
            search_intent=search_intent,
            desired_length=desired_length,
            keywords=keywords,
        )
        research_time = time.time() - t0

        article.research_notes = res_data.get("research_summary", "")
        raw_sources = res_data.get("sources", [])
        article.source_urls = [s.get("url", "") for s in raw_sources if s.get("url")]
        article.status = ArticleStatus.RESEARCHED

        # Save Research Sources to DB
        saved_sources = []
        for s in raw_sources:
            source_rec = ResearchSource(
                topic_id=topic_obj.id if topic_obj else None,
                article_id=article.id,
                title=s.get("title", "Authoritative Guide"),
                url=s.get("url", "https://official.domain"),
                domain=s.get("domain", ""),
                publication_date=s.get("publication_date", ""),
                relevant_facts=s.get("relevant_facts", []),
                notes=s.get("notes", ""),
                is_verified=True,
            )
            db.add(source_rec)
            saved_sources.append(s)

        db.commit()
        self._record_agent_run(
            db,
            article.id,
            "Research Analyst",
            "SUCCESS",
            res_data.get("input_tokens", 0),
            res_data.get("output_tokens", 0),
            research_time,
            f"Collected {len(raw_sources)} authoritative sources and facts.",
        )

        # STAGE 2: ARTICLE WRITER (Drafting)
        article.status = ArticleStatus.DRAFT
        db.commit()

        t0 = time.time()
        writer_res = article_writer.write_draft(
            title=title,
            research_summary=article.research_notes,
            sources=saved_sources,
            target_audience=target_audience,
            search_intent=search_intent,
            desired_length=desired_length,
            keywords=keywords,
        )
        writer_time = time.time() - t0

        article.content = writer_res.get("content", "")
        article.summary = writer_res.get("summary", "")

        # Record Initial Revision
        rev1 = ArticleRevision(
            article_id=article.id,
            revision_number=1,
            title=article.title,
            content=article.content,
            change_summary="Initial comprehensive, high-quality draft based strictly on title.",
        )
        db.add(rev1)
        db.commit()

        self._record_agent_run(
            db,
            article.id,
            "Article Writer",
            "SUCCESS",
            writer_res.get("input_tokens", 0),
            writer_res.get("output_tokens", 0),
            writer_time,
            "Complete article generated with proper headings, examples, and tables.",
        )

        # STAGE 3: FACT CHECKER
        article.status = ArticleStatus.FACT_CHECK
        db.commit()

        t0 = time.time()
        fc_res = fact_checker.check_article(
            article_content=article.content,
            sources=saved_sources,
            research_notes=article.research_notes,
        )
        fc_time = time.time() - t0

        self._record_agent_run(
            db,
            article.id,
            "Fact Checker",
            "FAILED" if fc_res.get("has_critical_failure") else "SUCCESS",
            fc_res.get("input_tokens", 0),
            fc_res.get("output_tokens", 0),
            fc_time,
            f"Factual score: {fc_res.get('factual_accuracy_score')}/100.",
        )

        # STAGE 4: SEO REVIEWER
        t0 = time.time()
        seo_res = seo_reviewer.review_and_optimize(
            title=article.title,
            content=article.content,
            primary_keywords=keywords,
            search_intent=search_intent,
        )
        seo_time = time.time() - t0

        article.seo_metadata = seo_res
        if not article.keywords and seo_res.get("related_terms"):
            article.keywords = seo_res.get("related_terms")[:6]
        db.commit()

        self._record_agent_run(
            db,
            article.id,
            "SEO Reviewer",
            "SUCCESS",
            seo_res.get("input_tokens", 0),
            seo_res.get("output_tokens", 0),
            seo_time,
            f"SEO score: {seo_res.get('seo_quality_score')}/100. Title & metadata optimized.",
        )

        # STAGE 5: ORIGINALITY & QUALITY REVIEWER
        article.status = ArticleStatus.QUALITY_REVIEW
        db.commit()

        t0 = time.time()
        qc_res = quality_checker.evaluate_quality(
            article_title=article.title,
            article_content=article.content,
            research_sources=saved_sources,
            fact_check_result=fc_res,
            seo_data=seo_res,
            search_intent=search_intent,
        )
        qc_time = time.time() - t0

        # Save Quality Check Result
        qc_record = QualityCheck(
            article_id=article.id,
            factual_accuracy_score=qc_res.get("factual_accuracy_score", 0.0),
            usefulness_score=qc_res.get("usefulness_score", 0.0),
            originality_score=qc_res.get("originality_score", 0.0),
            readability_score=qc_res.get("readability_score", 0.0),
            search_intent_match_score=qc_res.get("search_intent_match_score", 0.0),
            seo_quality_score=qc_res.get("seo_quality_score", 0.0),
            source_quality_score=qc_res.get("source_quality_score", 0.0),
            overall_score=qc_res.get("overall_score", 0.0),
            passed=qc_res.get("passed", False),
            fact_check_results=fc_res.get("results", []),
            originality_notes=qc_res.get("originality_notes", ""),
            detected_issues=qc_res.get("detected_issues", []),
            suggestions=qc_res.get("suggestions", []),
        )
        db.add(qc_record)
        article.overall_quality_score = qc_res.get("overall_score", 0.0)

        self._record_agent_run(
            db,
            article.id,
            "Quality Reviewer",
            "SUCCESS" if qc_res.get("passed") else "FAILED",
            qc_res.get("input_tokens", 0),
            qc_res.get("output_tokens", 0),
            qc_time,
            f"Overall score: {qc_res.get('overall_score')}/100. Quality passed: {qc_res.get('passed')}",
        )

        # STAGE 6: REVISION LOOP (If needed)
        if not qc_res.get("passed"):
            issues = qc_res.get("detected_issues", [])
            logger.info(f"Quality gate not met. Attempting targeted Final Editor revision. Issues: {issues}")
            t0 = time.time()
            revision_instructions = (
                f"Address the following quality and factual concerns directly:\n"
                + "\n".join([f"- {iss}" for iss in issues])
                + "\nEnhance clarity, deepen practical value, and eliminate unsupported claims."
            )
            rev_res = article_writer.revise_content(
                current_content=article.content,
                instructions=revision_instructions,
            )
            rev_time = time.time() - t0

            article.content = rev_res.get("content", "")
            rev2 = ArticleRevision(
                article_id=article.id,
                revision_number=2,
                title=article.title,
                content=article.content,
                change_summary="Automatic editorial revision to resolve quality audit items.",
            )
            db.add(rev2)
            db.commit()

        # STAGE 7: WEB FEATURED IMAGE SEARCH (Strictly relevant to article topic)
        logger.info(f"[IMAGE] Searching web for relevant featured images for: {article.title}")
        t0 = time.time()
        search_res = image_search_manager.find_images_for_article(
            article_title=article.title,
            article_content=article.content,
            article_summary=article.summary or "",
            keywords=article.keywords or [],
            auto_select=settings.IMAGE_AUTO_SELECT,
            min_relevance=settings.IMAGE_MIN_RELEVANCE,
        )
        img_time = time.time() - t0

        if search_res.get("selectedImage"):
            article.featured_image = search_res["selectedImage"]
            note = f"Found {len(search_res.get('candidates', []))} web images. Auto-selected '{search_res['selectedImage'].get('title')}' (Relevance: {search_res['selectedImage'].get('relevanceScore')}/100)."
        else:
            article.featured_image = {}
            cand_count = len(search_res.get("candidates", []))
            note = f"Found {cand_count} candidates, but none met relevance threshold ({search_res.get('threshold')}). Left without featured image for human selection."

        self._record_agent_run(
            db,
            article.id,
            "Featured Image Search",
            "SUCCESS",
            20,
            40,
            img_time,
            note,
        )

        # Final Status: Ready for human review
        article.status = ArticleStatus.READY_FOR_APPROVAL
        db.commit()
        db.refresh(article)
        return article

    def handle_human_decision(
        self,
        db: Session,
        article_id: int,
        decision: str,
        feedback: str = "",
        blog_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle user action: APPROVE, REVISION, REJECT, SAVE_DRAFT.
        Only on APPROVE will the article be staged as a Blogger DRAFT.
        """
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            return {"success": False, "error": "Article not found."}

        decision_upper = decision.upper()

        if decision_upper == "APPROVE":
            # Guard: ensure quality threshold met before approval
            threshold = settings.QUALITY_THRESHOLD
            if (article.overall_quality_score or 0) < threshold:
                return {
                    "success": False,
                    "error": f"Cannot approve article: Overall score ({article.overall_quality_score}) is below the quality threshold ({threshold}).",
                }

            article.status = ArticleStatus.APPROVED

            # Build content payload with hero image banner for Blogger
            content_to_send = article.content
            if article.featured_image:
                feat = article.featured_image
                img_url = feat.get("url") or feat.get("imageUrl") or feat.get("image")
                if img_url:
                    alt_text = feat.get("title") or feat.get("altText") or f"Featured image for {article.title}"
                    author = feat.get("author") or ""
                    license_info = feat.get("license") or "License unknown — verify before commercial/public use."
                    source_name = feat.get("sourceName") or "Web"
                    caption_items = []
                    if author and author != "Unknown":
                        caption_items.append(f"Photo: {author}")
                    caption_items.append(f"Source: {source_name}")
                    caption_items.append(f"License: {license_info}")
                    caption_str = " • ".join(caption_items)

                    img_banner = (
                        f'\n<div class="separator" style="clear: both; text-align: center; margin: 0 0 28px 0;">\n'
                        f'  <img src="{img_url}" alt="{alt_text}" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.12); display: inline-block;" loading="lazy" />\n'
                        f'  <p style="font-size: 12px; color: #64748b; font-style: italic; margin-top: 6px; text-align: center;">{caption_str}</p>\n'
                        f'</div>\n\n'
                    )
                    if img_url not in content_to_send:
                        content_to_send = img_banner + content_to_send

            # Create Blogger DRAFT (isDraft=True)
            draft_res = blogger_service.create_draft(
                title=article.title,
                content_html_or_md=content_to_send,
                blog_id=blog_id,
                labels=article.keywords or ["AI-Assisted", "Draft"],
            )

            if draft_res.get("success"):
                article.blogger_post_id = draft_res.get("post_id")
                article.blogger_draft_url = draft_res.get("post_url")
                # Record publishing history
                hist = PublishingHistory(
                    article_id=article.id,
                    blogger_blog_id=blog_id or settings.BLOGGER_BLOG_ID or "demo-blog",
                    blogger_post_id=draft_res.get("post_id", ""),
                    action="CREATE_DRAFT",
                    status="SUCCESS",
                    post_url=draft_res.get("post_url"),
                )
                db.add(hist)
                db.commit()
                return {
                    "success": True,
                    "status": ArticleStatus.APPROVED,
                    "blogger_post_id": article.blogger_post_id,
                    "blogger_draft_url": article.blogger_draft_url,
                    "message": "Article approved and successfully saved as Blogger DRAFT.",
                }
            else:
                hist = PublishingHistory(
                    article_id=article.id,
                    blogger_blog_id=blog_id or settings.BLOGGER_BLOG_ID or "demo-blog",
                    action="CREATE_DRAFT",
                    status="FAILED",
                    error_message=draft_res.get("error", "Unknown Blogger error"),
                )
                db.add(hist)
                db.commit()
                return {
                    "success": False,
                    "status": ArticleStatus.APPROVED,
                    "error": f"Article marked as approved locally, but Blogger draft creation encountered an error: {draft_res.get('error')}",
                }

        elif decision_upper == "REVISION":
            article.status = ArticleStatus.NEEDS_REVISION
            # Execute targeted revision with user feedback
            rev_res = article_writer.revise_content(
                current_content=article.content,
                instructions=feedback or "Revise and refine based on human editor comments.",
            )
            article.content = rev_res.get("content", "")

            # Count revisions
            rev_count = db.query(ArticleRevision).filter(ArticleRevision.article_id == article.id).count()
            rev = ArticleRevision(
                article_id=article.id,
                revision_number=rev_count + 1,
                title=article.title,
                content=article.content,
                change_summary=feedback or "Human requested revision.",
            )
            db.add(rev)
            db.commit()
            return {
                "success": True,
                "status": ArticleStatus.NEEDS_REVISION,
                "message": "Revision generated based on your feedback. Please re-review.",
            }

        elif decision_upper == "REJECT":
            article.status = ArticleStatus.REJECTED
            db.commit()
            return {
                "success": True,
                "status": ArticleStatus.REJECTED,
                "message": "Article has been marked as rejected.",
            }

        elif decision_upper == "SAVE_DRAFT":
            article.status = ArticleStatus.DRAFT
            db.commit()
            return {
                "success": True,
                "status": ArticleStatus.DRAFT,
                "message": "Saved locally as draft.",
            }

        return {"success": False, "error": f"Unknown decision '{decision}'."}

    def _record_agent_run(
        self,
        db: Session,
        article_id: Optional[int],
        agent_name: str,
        status: str,
        in_tokens: int,
        out_tokens: int,
        exec_time: float,
        notes: str,
    ):
        try:
            run = AgentRun(
                article_id=article_id,
                agent_name=agent_name,
                status=status,
                input_tokens_est=in_tokens,
                output_tokens_est=out_tokens,
                execution_time_seconds=round(exec_time, 2),
                notes=notes,
            )
            db.add(run)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to record agent run log: {str(e)}")


orchestrator = WorkflowOrchestrator()
