"""RS256 JWT token issuance and verification using our own key pair.

The backend owns its private key and issues tokens directly — no Keycloak,
no JWKS endpoint, no external identity provider required.
Supports key identifier (kid) and key rotation dictionaries.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt


class TokenService:
    def __init__(
        self,
        private_key_pem: str,
        public_key_pem: str,
        access_expire_minutes: int = 60,
        refresh_expire_days: int = 7,
        hs256_secret: str | None = None,
        kid: str = "thali-key-2026",
        rotation_public_keys: dict[str, str] | None = None,
    ) -> None:
        # Normalise escaped newlines that may arrive from env vars
        self._private_key = private_key_pem.replace("\\n", "\n")
        self._public_key = public_key_pem.replace("\\n", "\n")
        self._access_expire = timedelta(minutes=access_expire_minutes)
        self._refresh_expire = timedelta(days=refresh_expire_days)
        self._hs256_secret = hs256_secret or "test-secret"
        self._kid = kid
        self._rotation_public_keys: dict[str, str] = {
            kid: self._public_key
        }
        if rotation_public_keys:
            for k, pem in rotation_public_keys.items():
                self._rotation_public_keys[k] = pem.replace("\\n", "\n")

    @property
    def current_kid(self) -> str:
        return self._kid

    # ------------------------------------------------------------------
    # Cryptographic Secret Generation & Hashing Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_secure_secret(nbytes: int = 32) -> str:
        """Generate high-entropy cryptographically random URL-safe secret."""
        return secrets.token_urlsafe(nbytes)

    @staticmethod
    def hash_secret(secret: str) -> str:
        """Compute SHA-256 hex digest of a raw token/secret for storage."""
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Issuance
    # ------------------------------------------------------------------

    def issue_access_token(
        self,
        user_id: str,
        tenant_id: str,
        role: str,
        facility_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "facility_id": facility_id,
            "iat": now,
            "exp": now + self._access_expire,
            "jti": str(uuid.uuid4()),
            "typ": "access",
        }
        if session_id:
            payload["session_id"] = session_id

        headers = {"kid": self._kid}
        return pyjwt.encode(
            payload, self._private_key, algorithm="RS256", headers=headers
        )

    def issue_refresh_token(
        self,
        user_id: str,
        tenant_id: str,
        session_id: str | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "iat": now,
            "exp": now + self._refresh_expire,
            "jti": str(uuid.uuid4()),
            "typ": "refresh",
        }
        if session_id:
            payload["session_id"] = session_id

        headers = {"kid": self._kid}
        return pyjwt.encode(
            payload, self._private_key, algorithm="RS256", headers=headers
        )

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify RS256 signature (or HS256 in tests) and return claims.

        Supports key rotation through header 'kid'.
        Raises ``TokenVerificationError`` on any failure.
        """
        from backend.interfaces.http.v2.security.jwt import TokenVerificationError

        try:
            header = pyjwt.get_unverified_header(token)
        except Exception as exc:
            raise TokenVerificationError("token is invalid") from exc

        alg = header.get("alg")
        if alg not in ("RS256", "HS256"):
            raise TokenVerificationError("unsupported token algorithm")

        try:
            if alg == "HS256":
                return pyjwt.decode(
                    token,
                    self._hs256_secret,
                    algorithms=["HS256"],
                    options={"verify_aud": False},
                )

            kid = header.get("kid")
            pub_key = self._rotation_public_keys.get(kid, self._public_key)
            return pyjwt.decode(
                token,
                pub_key,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
        except pyjwt.ExpiredSignatureError as exc:
            raise TokenVerificationError("token has expired") from exc
        except pyjwt.InvalidTokenError as exc:
            raise TokenVerificationError("token is invalid") from exc

    def verify_refresh_token(self, token: str) -> dict[str, Any]:
        """Like ``verify_token`` but also asserts typ == 'refresh'."""
        from backend.interfaces.http.v2.security.jwt import TokenVerificationError

        claims = self.verify_token(token)
        if claims.get("typ") != "refresh":
            raise TokenVerificationError("not a refresh token")
        return claims
