"""WhatsApp webhook verify-token handshake (Gate 06).

Meta sends a GET ``hub.challenge``/``hub.verify_token`` request to confirm the
webhook URL. The challenge must only be echoed when the verify token matches
the configured secret — constant-time, and never logged.
"""

from __future__ import annotations

import hmac


class VerifyTokenError(ValueError):
    """Raised when the webhook verify token does not match."""


def confirm_verify_token(query_token: str | None, configured_token: str) -> bool:
    """Return True only if the query token matches the configured token."""
    if not query_token:
        return False
    return hmac.compare_digest(query_token, configured_token)


def challenge_response(
    hub_mode: str | None,
    hub_verify_token: str | None,
    hub_challenge: str | None,
    configured_token: str,
) -> str:
    """Echo the challenge for a valid verification handshake.

    Raises ``VerifyTokenError`` when the handshake is not authorized.
    """
    if hub_mode != "subscribe" or hub_verify_token is None or hub_challenge is None:
        raise VerifyTokenError("unsupported verification handshake parameters")
    if not confirm_verify_token(hub_verify_token, configured_token):
        raise VerifyTokenError("verify token mismatch")
    return hub_challenge
