"""WhatsApp inbound channel adapter (Gate 06).

Sequence: verify X-Hub-Signature-256 over the raw body → confirm verify-token
handshake → normalized neutral envelope → quick ACK. Replay protection and
idempotency are delegated to the dedup store in the calling boundary; no
duplicate messages are processed twice.
"""

from __future__ import annotations

from .envelope import WhatsAppInboundEnvelope
from .signature import verify_x_hub_signature_256
from .verify_token import challenge_response

__all__ = [
    "WhatsAppInboundEnvelope",
    "verify_x_hub_signature_256",
    "challenge_response",
]
