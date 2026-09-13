"""Observability and privacy-preserving structured logging (Gate 05).

Enforces strict redaction of PHI/PII, credentials, tokens, and raw payloads.
Ensures zero medical record or secret leakage into log sinks.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

_SENSITIVE_KEYS = {
    "password",
    "secret",
    "token",
    "access_token",
    "verify_token",
    "client_secret",
    "api_key",
    "phone",
    "patient_name",
    "uh_id",
    "carbs_grams",
    "glycemic_index",
    "medication",
    "instruction",
    "payload",
    "authorization",
}


def sanitize_log_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive keys from dictionary data."""
    clean: dict[str, Any] = {}
    for k, v in data.items():
        key_lower = k.lower()
        if any(s in key_lower for s in _SENSITIVE_KEYS):
            clean[k] = "[REDACTED]"
        elif isinstance(v, dict):
            clean[k] = sanitize_log_dict(v)
        elif isinstance(v, (UUID,)):
            clean[k] = str(v)
        else:
            clean[k] = v
    return clean


class InfrastructureLogger:
    """Structured infrastructure logger with automatic PHI/secret redaction."""

    def __init__(self, name: str = "thali.infrastructure") -> None:
        self._logger = logging.getLogger(name)

    def info(self, event: str, **kwargs: Any) -> None:
        safe_data = sanitize_log_dict(kwargs)
        self._logger.info(f"{event} | {json.dumps(safe_data)}")

    def warning(self, event: str, **kwargs: Any) -> None:
        safe_data = sanitize_log_dict(kwargs)
        self._logger.warning(f"{event} | {json.dumps(safe_data)}")

    def error(self, event: str, **kwargs: Any) -> None:
        safe_data = sanitize_log_dict(kwargs)
        self._logger.error(f"{event} | {json.dumps(safe_data)}")
