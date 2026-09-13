"""HTTP security boundary exports (Gate 06).

The FastAPI v2 boundary is a thin adapter. It reuses Gate 05's
``KeycloakTokenValidator`` for claim-level validation and adds the HS256 JWT
signature verification this boundary requires. PHI/PII redaction is delegated
to ``backend.infrastructure.observability.logging``.
"""

from .jwt import Hs256Result, JwtSignatureError, verify_hs256
from .roles import role_tokens

__all__ = [
    "Hs256Result",
    "JwtSignatureError",
    "verify_hs256",
    "role_tokens",
]
