"""WhatsApp template registry for business-initiated messaging compliance.

Meta restricts business-initiated messages on live (non-test) numbers: free-form
text is only delivered inside an open 24h customer-care session (opened when the
customer messages the business first). Outside that window a business must use an
APPROVED template. This module resolves which template to use for the onboarding
welcome, preferring the platform's own personalized templates:

    preferred  → thali_welcome / thali_welcome_greeting (personalized, need APPROVAL)
    last resort→ free-form text (only succeeds inside a 24h window)

Meta's bundled sample templates (e.g. ``hello_world``) are usable only from
public *test* numbers and are therefore excluded here. The registry reads the
template list from the Meta Graph API, caches the result briefly, and never
raises: any lookup failure falls back to free-form text.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Sequence

from config.settings import Settings

logger = logging.getLogger(__name__)

# Preference order: first APPROVED template wins.
WELCOME_TEMPLATE_PREFERENCE: Sequence[str] = (
    "thali_welcome",
    "thali_welcome_greeting",
    "hello_world",
)

# Meta's sample templates may only be sent from public *test* numbers; on a real
# business line they are rejected (meta_code_131058). Never select them for live.
TEST_ONLY_TEMPLATE_NAMES: frozenset[str] = frozenset({"hello_world"})

_CACHE_TTL_SECONDS: float = 300.0
_cache: dict[str, tuple[float, set[str] | None]] = {}


_UNSET = object()


class WhatsAppTemplateRegistry:
    """Resolves approved WhatsApp message templates for business-initiated sends.

    PHI-safe: only template names are fetched/stored, never message content.
    """

    GRAPH_BASE_URL = "https://graph.facebook.com"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        business_account_id: Any = _UNSET,
        access_token: Any = _UNSET,
        api_version: Any = _UNSET,
        cache_ttl: float = _CACHE_TTL_SECONDS,
    ) -> None:
        self._settings = settings or Settings()
        self._business_account_id = (
            self._settings.whatsapp.business_account_id
            if business_account_id is _UNSET
            else business_account_id
        )
        self._access_token = (
            self._settings.whatsapp.access_token
            if access_token is _UNSET
            else access_token
        )
        self._api_version = (
            self._settings.whatsapp.api_version
            if api_version is _UNSET
            else (api_version or self._settings.whatsapp.api_version)
        )
        self._cache_ttl = cache_ttl
        configured = (self._settings.whatsapp.welcome_template_names or "").split(",")
        self._preference: Sequence[str] = tuple(
            name.strip() for name in configured if name.strip()
        ) or WELCOME_TEMPLATE_PREFERENCE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def approved_templates(self) -> set[str]:
        """Return the set of template names currently APPROVED by Meta (cached)."""
        if not self._business_account_id or not self._access_token:
            return set()

        now = time.monotonic()
        cached = _cache.get(self._business_account_id)
        if cached is not None and cached[0] >= now and cached[1] is not None:
            return cached[1]

        names = self._fetch_approved_templates()
        # A failed fetch returns an empty set which we do not cache; we fall back
        # to free-form so a transient registry outage never blocks sends.
        _cache[self._business_account_id] = (now + self._cache_ttl, names)
        return names

    def resolve_welcome_template(self) -> str:
        """Pick the best welcome template name, or ``text`` for free-form fallback.

        Test-only sample templates (e.g. ``hello_world``) are excluded so a
        "sending" resolution can never hit meta_code_131058 on the live number.
        """
        approved = self.approved_templates()
        for name in self._preference:
            if name in approved and name not in TEST_ONLY_TEMPLATE_NAMES:
                logger.info("welcome template resolved: %s", name)
                return name
        logger.info("no live-usable approved welcome template; falling back to free-form text")
        return "text"

    # ------------------------------------------------------------------
    # Graph API
    # ------------------------------------------------------------------

    def _fetch_approved_templates(self) -> set[str]:
        url = (
            f"{self.GRAPH_BASE_URL}/{self._api_version}/{self._business_account_id}"
            "/message_templates?fields=name,status"
        )
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "User-Agent": "THALI-PLATE/1.0",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=10.0) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            logger.warning("whatsapp template registry lookup failed: %s", type(exc).__name__)
            return set()

        approved: set[str] = set()
        for template in body.get("data") or []:
            name = template.get("name")
            status = str(template.get("status") or "").upper()
            if name and status == "APPROVED":
                approved.add(name)
        return approved


__all__ = ["WhatsAppTemplateRegistry", "resolve_welcome_template"]


def resolve_welcome_template(settings: Settings | None = None) -> str:
    """Convenience accessor with no configuration plumbing required."""
    return WhatsAppTemplateRegistry(settings=settings).resolve_welcome_template()