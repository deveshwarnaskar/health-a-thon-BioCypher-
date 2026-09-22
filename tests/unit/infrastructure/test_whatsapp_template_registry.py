"""Unit tests for the WhatsApp template registry resolution logic."""

from unittest.mock import patch

from backend.infrastructure.channel import template_registry as module
from backend.infrastructure.channel.template_registry import WhatsAppTemplateRegistry


def test_prefers_first_approved_custom_template():
    registry = WhatsAppTemplateRegistry(
        business_account_id="acct",
        access_token="tok",
        api_version="v25.0",
        cache_ttl=0,
    )
    with patch.object(registry, "_fetch_approved_templates", return_value={"thali_welcome", "hello_world"}):
        assert registry.resolve_welcome_template() == "thali_welcome"


def test_skips_test_only_template_when_only_candidate():
    registry = WhatsAppTemplateRegistry(
        business_account_id="acct",
        access_token="tok",
        api_version="v25.0",
        cache_ttl=0,
    )
    # hello_world is APPROVED but test-only: must never be selected for live sends.
    with patch.object(registry, "_fetch_approved_templates", return_value={"hello_world"}):
        assert registry.resolve_welcome_template() == "text"


def test_falls_back_to_text_when_no_approved_template():
    registry = WhatsAppTemplateRegistry(
        business_account_id="acct",
        access_token="tok",
        api_version="v25.0",
        cache_ttl=0,
    )
    with patch.object(registry, "_fetch_approved_templates", return_value=set()):
        assert registry.resolve_welcome_template() == "text"


def test_fallback_available_without_credentials():
    registry = WhatsAppTemplateRegistry(
        business_account_id=None,
        access_token=None,
        api_version="v25.0",
    )
    assert registry.resolve_welcome_template() == "text"