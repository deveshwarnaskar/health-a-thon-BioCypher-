"""HTTP middleware boundary (Gate 07).

Hosts security headers, correlation IDs, and request observability.
"""

from .observability import HttpObservabilityMiddleware
from .security import (
    CORRELATION_ID_HEADER,
    CorrelationIDMiddleware,
    SecurityHeadersMiddleware,
    register_middleware,
)

__all__ = [
    "CORRELATION_ID_HEADER",
    "CorrelationIDMiddleware",
    "SecurityHeadersMiddleware",
    "HttpObservabilityMiddleware",
    "register_middleware",
]