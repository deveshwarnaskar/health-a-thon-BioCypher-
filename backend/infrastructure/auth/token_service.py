"""RS256 JWT token issuance and verification using our own key pair.

The backend owns its private key and issues tokens directly — no Keycloak,
no JWKS endpoint, no external identity provider required.
"""
from __future__ import annotations

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
    ) -> None:
        # Normalise escaped newlines that may arrive from env vars
        self._private_key = private_key_pem.replace("\\n", "\n")
        self._public_key = public_key_pem.replace("\\n", "\n")
        self._access_expire = timedelta(minutes=access_expire_minutes)
        self._refresh_expire = timedelta(days=refresh_expire_days)
        self._hs256_secret = hs256_secret or "test-secret"

    # ------------------------------------------------------------------
    # Issuance
    # ------------------------------------------------------------------

    def issue_access_token(
        self,
        user_id: str,
        tenant_id: str,
        role: str,
        facility_id: str | None = None,
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
        return pyjwt.encode(payload, self._private_key, algorithm="RS256")

    def issue_refresh_token(self, user_id: str, tenant_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "iat": now,
            "exp": now + self._refresh_expire,
            "jti": str(uuid.uuid4()),
            "typ": "refresh",
        }
        return pyjwt.encode(payload, self._private_key, algorithm="RS256")

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify RS256 signature (or HS256 in tests) and return claims.

        Raises ``TokenVerificationError`` on any failure — expired,
        invalid signature, wrong algorithm, etc.
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
            return pyjwt.decode(
                token,
                self._public_key,
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
