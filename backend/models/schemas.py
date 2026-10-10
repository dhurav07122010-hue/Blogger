"""
Pydantic schemas for data validation and API payloads.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# --- Topic Schemas ---
class TopicBase(BaseModel):
    title: str = Field(..., description="Topic headline or seed idea")
    target_audience: str = Field("General Audience", description="Intended reader demographic")
    country_region: str = Field("Global", description="Target region or country")
    search_intent: str = Field("Informational", description="Informational, Commercial, Navigational, Transactional")
    desired_length: str = Field("medium (~1500w)", description="Target article length")
    keywords: List[str] = Field(default_factory=list, description="Keywords for research focus")
    priority: str = Field("medium", description="Priority: low, medium, high")
    notes: Optional[str] = Field("", description="Additional context or constraints")
    source: Optional[str] = Field("User", description="Source of topic discovery")
    source_url: Optional[str] = Field("", description="URL of source")
    discovery_mode: Optional[str] = Field("manual", description="trending | random | evergreen | manual")
    trend_evidence: Optional[str] = Field("", description="Evidence of search trend if available")
    estimated_difficulty: Optional[str] = Field("Intermediate (Estimate)", description="Clearly marked as an estimate")
    audience_fit: Optional[str] = Field("High", description="Potential audience relevance")
    article_potential: Optional[str] = Field("High", description="Article potential rating")
    category: Optional[str] = Field("Technology", description="Topic category")


class TopicCreate(TopicBase):
    project_id: Optional[int] = None


class TopicRead(TopicBase):
    id: int
    project_id: Optional[int] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Research Source Schemas ---
class ResearchSourceBase(BaseModel):
    title: str
    url: str
    domain: str = ""
    publication_date: str = ""
    relevant_facts: List[str] = Field(default_factory=list)
    notes: str = ""
    is_verified: bool = True


class ResearchSourceCreate(ResearchSourceBase):
    topic_id: Optional[int] = None
    article_id: Optional[int] = None


class ResearchSourceRead(ResearchSourceBase):
    id: int
    topic_id: Optional[int] = None
    article_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Fact Check Schemas ---
class FactCheckItem(BaseModel):
    claim: str
    status: str = Field("SUPPORTED", description="SUPPORTED | UNCERTAIN | UNSUPPORTED")
    source: str = Field("", description="Source domain, URL, or citation")
    reason: str = Field("", description="Verification reasoning or warning")


# --- SEO Metadata Schemas ---
class SEOMetadata(BaseModel):
    seo_title: str = ""
    meta_description: str = ""
    url_slug: str = ""
    h1: str = ""
    h2_structure: List[str] = Field(default_factory=list)
    primary_topic: str = ""
    related_terms: List[str] = Field(default_factory=list)
    faq_suggestions: List[Dict[str, str]] = Field(default_factory=list)
    internal_link_suggestions: List[Dict[str, str]] = Field(default_factory=list)


# --- Quality Check Schemas ---
class QualityCheckRead(BaseModel):
    id: int
    article_id: int
    factual_accuracy_score: float
    usefulness_score: float
    originality_score: float
    readability_score: float
    search_intent_match_score: float
    seo_quality_score: float
    source_quality_score: float
    overall_score: float
    passed: bool
    fact_check_results: List[FactCheckItem] = Field(default_factory=list)
    originality_notes: str = ""
    detected_issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Article Revision Schemas ---
class ArticleRevisionRead(BaseModel):
    id: int
    article_id: int
    revision_number: int
    title: str
    content: str
    change_summary: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Article Schemas ---
class ArticleBase(BaseModel):
    title: str
    content: str = ""
    summary: str = ""
    status: str = "IDEA"
    search_intent: str = "Informational"
    target_audience: str = "General Audience"
    country_region: str = "Global"
    keywords: List[str] = Field(default_factory=list)
    research_notes: str = ""
    source_urls: List[str] = Field(default_factory=list)
    seo_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    featured_image: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ArticleCreate(ArticleBase):
    project_id: Optional[int] = None
    topic_id: Optional[int] = None


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = None
    research_notes: Optional[str] = None
    seo_metadata: Optional[Dict[str, Any]] = None
    featured_image: Optional[Dict[str, Any]] = None
    featuredImage: Optional[Dict[str, Any]] = None
    revision_summary: Optional[str] = "Manual update"


class ArticleRead(ArticleBase):
    id: int
    project_id: Optional[int] = None
    topic_id: Optional[int] = None
    blogger_post_id: Optional[str] = None
    blogger_draft_url: Optional[str] = None
    overall_quality_score: Optional[float] = None
    featured_image: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    quality_checks: List[QualityCheckRead] = Field(default_factory=list)
    revisions: List[ArticleRevisionRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# --- Workflow Requests ---
class StartWorkflowRequest(BaseModel):
    topic_id: Optional[int] = None
    custom_title: Optional[str] = None
    target_audience: Optional[str] = "General Audience"
    country_region: Optional[str] = "Global"
    search_intent: Optional[str] = "Informational"
    desired_length: Optional[str] = "medium (~1500w)"
    keywords: List[str] = Field(default_factory=list)
    skip_research: bool = False


class RevisionRequest(BaseModel):
    article_id: int
    instructions: str
    focus_sections: Optional[List[str]] = Field(default_factory=list)


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., description="APPROVE | REVISION | REJECT | SAVE_DRAFT")
    feedback: Optional[str] = ""


class AIAssistRequest(BaseModel):
    action: str = Field(..., description="improve | rewrite | expand | shorten | suggest_titles | suggest_keywords | generate_toc | meta_description")
    content: Optional[str] = ""
    selected_text: Optional[str] = ""
    title: Optional[str] = ""
    target_audience: Optional[str] = "General Audience"
    instructions: Optional[str] = ""


# --- Blogger Schemas ---
class BloggerBlog(BaseModel):
    id: str
    name: str
    url: str
    description: Optional[str] = ""
    posts_total: int = 0


class BloggerPost(BaseModel):
    id: str
    title: str
    url: Optional[str] = None
    status: str  # DRAFT, LIVE
    published: Optional[str] = None
    updated: Optional[str] = None


class CreateBloggerDraftRequest(BaseModel):
    article_id: int
    blog_id: Optional[str] = None


class PublishBloggerPostRequest(BaseModel):
    article_id: int
    blog_id: Optional[str] = None
    confirm_publish: bool = False


# --- Dashboard Stats ---
class DashboardStats(BaseModel):
    articles_created: int
    drafts_count: int
    awaiting_approval: int
    published_count: int
    failed_quality_checks: int
    images_generated: int = 0
    gemini_connected: bool = True
    blogger_connected: bool = False
    recent_agent_runs: List[Dict[str, Any]] = Field(default_factory=list)
    total_tokens_est: int = 0
    estimated_cost_usd: float = 0.0
    demo_mode: bool = True

