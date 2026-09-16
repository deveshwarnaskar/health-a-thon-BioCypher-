"""Security boundary exports (Gate 06 + Gate 07 + Gate 10C-R).

Gate 06 primitives: HS256 JWT signature verification, role token normalization.
Gate 07 additions: AuthenticatedContext, AuthorizationPolicy, authentication
dependency wiring.
Gate 10C-R additions: RS256 verification and Keycloak JWKS retrieval/caching for
the production trust boundary.
"""

from .jwt import (
    Hs256Result,
    JwtSignatureError,
    TokenVerificationError,
    jwt_header,
    verify_hs256,
    verify_rs256,
)
from .jwks import JwksClient, SigningKey
from .roles import role_tokens
from .authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    DefaultAuthorizationPolicy,
    Operation,
)

__all__ = [
    "AuthenticatedContext",
    "AuthorizationPolicy",
    "DefaultAuthorizationPolicy",
    "Hs256Result",
    "JwtSignatureError",
    "JwksClient",
    "Operation",
    "SigningKey",
    "TokenVerificationError",
    "jwt_header",
    "role_tokens",
    "verify_hs256",
    "verify_rs256",
]
