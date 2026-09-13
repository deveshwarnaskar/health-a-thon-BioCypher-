"""Legacy adapter contracts (Gate 02B placeholders).

Names only: implementations are intentionally deferred so the baseline
``app/*`` packages remain the single operational implementation.

- LegacyStoreAdapter    wraps ``app.core.datamodel.Store`` for repository ports.
- LegacyV1Router        exposes legacy ``app.server.main`` routes as-is.
- LegacyWhatsAppBridge  adapts ``app.server.whatsapp.CloudBackend``.
- LegacyReportBridge    adapts ``app.report.pdf`` / ``charts`` / ``html_preview``.
"""

class LegacyStoreAdapter:
    """Placeholder. Bridges app.core.datamodel.Store to domain repositories."""


class LegacyV1Router:
    """Placeholder. Preserves and mounts the existing FastAPI v1 routes."""


class LegacyWhatsAppBridge:
    """Placeholder. Wraps the legacy WhatsApp Cloud backend."""


class LegacyReportBridge:
    """Placeholder. Wraps the legacy PDF/chart/HTML report renderers."""