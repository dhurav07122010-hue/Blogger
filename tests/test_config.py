"""
Tests for configuration loading, secret masking, and startup validation.
"""

from backend.config import Settings, mask_secret


def test_mask_secret():
    assert mask_secret("") == ""
    assert mask_secret(None) == ""
    assert mask_secret("short") == "********"
    masked = mask_secret("AIzaSyD1234567890abcdefghij", show_prefix=4, show_suffix=2)
    assert masked == "AIza...ij"
    assert "1234567890" not in masked


def test_startup_validation_without_secrets():
    custom_settings = Settings()
    warnings = custom_settings.validate_startup()
    assert isinstance(warnings, list)
    # Check that secrets are never present in warnings
    for w in warnings:
        assert custom_settings.GEMINI_API_KEY not in w or custom_settings.GEMINI_API_KEY == ""
        assert custom_settings.GOOGLE_CLIENT_SECRET not in w or custom_settings.GOOGLE_CLIENT_SECRET == ""


def test_safe_summary_masking():
    custom_settings = Settings()
    custom_settings.GEMINI_API_KEY = "AIzaSySecretApiKey123456789"
    custom_settings.GOOGLE_CLIENT_SECRET = "GOCSPX-super-secret-token"

    summary = custom_settings.get_safe_summary()
    assert summary["has_gemini_key"] is True
    assert "AIzaSySecretApiKey123456789" not in summary["gemini_key_preview"]
    assert "GOCSPX-super-secret-token" not in str(summary)
    assert summary["auto_publish"] is False
    assert summary["quality_threshold"] >= 60
