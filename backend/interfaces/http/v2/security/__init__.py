"""Security boundary exports (Gate 06 + Gate 07).

Gate 06 primitives: HS256 JWT signature verification, role token normalization.
Gate 07 additions: AuthenticatedContext, AuthorizationPolicy, authentication
dependency wiring.
"""

from .jwt import Hs256Result, JwtSignatureError, verify_hs256
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
    "Operation",
    "verify_hs256",
    "role_tokens",
]
