"""
Tests for Blogger API v3 service, Google OAuth flow, and publishing safety mechanisms.
"""

from backend.services.blogger import blogger_service
from backend.config import settings


def test_blogger_oauth_url_generation():
    # When not configured, returns safe fallback URL
    url = blogger_service.get_auth_url()
    assert url is not None
    assert isinstance(url, str)
    assert len(url) > 0


def test_blogger_list_blogs():
    blogs = blogger_service.list_blogs()
    assert isinstance(blogs, list)
    assert len(blogs) > 0
    assert "id" in blogs[0]
    assert "name" in blogs[0]


def test_blogger_create_draft_strictly_draft():
    draft_res = blogger_service.create_draft(
        title="Testing Draft Creation Mode",
        content_html_or_md="<p>Draft content for testing</p>",
        blog_id="demo-blog-101",
    )

    assert draft_res["success"] is True
    assert draft_res["status"] == "DRAFT"
    assert "post_id" in draft_res
    assert draft_res["post_id"] is not None


def test_publish_guard_blocks_without_confirmation():
    # Attempt publish without explicit user confirmation
    res = blogger_service.publish_post(
        post_id="draft-123",
        quality_score=95.0,
        confirm_publish=False,
    )

    assert res["success"] is False
    assert "Explicit human confirmation" in res["error"]


def test_publish_guard_blocks_sub_threshold_articles():
    settings.QUALITY_THRESHOLD = 85
    # Attempt publish with failing score
    res = blogger_service.publish_post(
        post_id="draft-123",
        quality_score=78.5,
        confirm_publish=True,
    )

    assert res["success"] is False
    assert "does not meet the safety threshold" in res["error"]
