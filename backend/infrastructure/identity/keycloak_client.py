"""Keycloak / OIDC identity foundation adapter (Gate 05).

Provides configuration and token claim validation primitives.
Does NOT implement FastAPI middleware or HTTP endpoints (deferred to Gate 06).
No external network calls on import or execution without explicit config.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class KeycloakConfig:
    """Keycloak OIDC configuration."""
    issuer_url: str = ""
    realm: str = "thali"
    client_id: str = "thali-backend"
    client_secret: str = ""


@dataclass(frozen=True)
class KeycloakUserClaims:
    """Validated OIDC token claims."""
    user_id: UUID
    username: str
    roles: list[str] = field(default_factory=list)
    tenant_id: UUID | None = None
    email: str | None = None


class KeycloakTokenValidator:
    """Offline / local token validation helper."""

    def __init__(self, config: KeycloakConfig) -> None:
        self.config = config

    def decode_unverified_claims(self, token: str) -> dict:
        """Extract payload from JWT without external signature verification."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("Malformed JWT structure")
            # Base64url decode payload
            payload_b64 = parts[1]
            padded = payload_b64 + "=" * (-len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(padded)
            return json.loads(payload_bytes.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Failed to decode token payload: {e}")

    def validate_claims(self, token: str) -> KeycloakUserClaims:
        """Validate token standard claims (expiry, issuer) and extract user identity."""
        claims = self.decode_unverified_claims(token)

        # Check expiration
        exp = claims.get("exp")
        if exp is not None and time.time() > exp:
            raise ValueError("Token has expired")

        # Check issuer if configured
        iss = claims.get("iss")
        if self.config.issuer_url and iss != self.config.issuer_url:
            raise ValueError(f"Issuer mismatch: expected {self.config.issuer_url}, got {iss}")

        sub = claims.get("sub")
        if not sub:
            raise ValueError("Token missing 'sub' claim")

        user_id = UUID(str(sub))
        username = claims.get("preferred_username", str(sub))
        roles = claims.get("realm_access", {}).get("roles", [])
        
        tenant_id_claim = claims.get("tenant_id")
        tenant_id = UUID(str(tenant_id_claim)) if tenant_id_claim else None

        return KeycloakUserClaims(
            user_id=user_id,
            username=username,
            roles=roles,
            tenant_id=tenant_id,
            email=claims.get("email"),
        )
