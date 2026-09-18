"""Observability and privacy-preserving structured logging (Gate 10P-D).

Enforces strict redaction of PHI/PII, credentials, tokens, and raw payloads.
Ensures zero medical record or secret leakage into log sinks.
Implements canonical machine-readable JSON log format with correlation ID propagation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from .context import get_correlation_id, get_request_id

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "verify_token",
        "client_secret",
        "api_key",
        "phone",
        "patient_name",
        "uh_id",
        "carbs_grams",
        "carbs",
        "glycemic_index",
        "gi",
        "medication",
        "instruction",
        "payload",
        "authorization",
        "cookie",
        "jwt",
        "evidence",
        "reading",
        "glucose",
        "value",
        "patient",
        "caregiver",
        "doctor",
        "request_body",
        "body",
    }
)


def sanitize_log_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive keys from dictionary data."""
    clean: dict[str, Any] = {}
    for k, v in data.items():
        key_lower = k.lower()
        if any(s in key_lower for s in _SENSITIVE_KEYS):
            clean[k] = "[REDACTED]"
        elif isinstance(v, dict):
            clean[k] = sanitize_log_dict(v)
        elif isinstance(v, list):
            clean[k] = [
                sanitize_log_dict(item) if isinstance(item, dict)
                else "[REDACTED]" if isinstance(item, str) and any(s in item.lower() for s in _SENSITIVE_KEYS)
                else str(item) if isinstance(item, UUID)
                else item
                for item in v
            ]
        elif isinstance(v, UUID):
            clean[k] = str(v)
        else:
            clean[k] = v
    return clean


def sanitize_exception(exc: BaseException) -> dict[str, Any]:
    """Sanitize an exception object to avoid leaking request bodies or credentials."""
    exc_type = type(exc).__name__
    raw_msg = str(exc)
    # Check if raw_msg contains common sensitive patterns
    lower = raw_msg.lower()
    if any(s in lower for s in _SENSITIVE_KEYS):
        msg = f"{exc_type}: [SANITIZED - POTENTIAL PHI/CREDENTIAL CONTENT DETECTED]"
    else:
        msg = f"{exc_type}: {raw_msg}"
    return {
        "type": exc_type,
        "message": msg,
    }


class StructuredJsonFormatter(logging.Formatter):
    """Canonical machine-readable JSON logging formatter (Gate 10P-D).

    Produces one line of valid JSON per log entry containing:
    timestamp, level, service, environment, event, correlation_id, request_id,
    and optional duration_ms, status, error_code, plus sanitized extra attributes.
    """

    def __init__(
        self,
        service: str = "thali-plate",
        environment: str = "development",
    ) -> None:
        super().__init__()
        self.service = service
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        now = datetime.now(timezone.utc).isoformat()

        # Resolve correlation_id and request_id
        cid = getattr(record, "correlation_id", None) or get_correlation_id()
        rid = getattr(record, "request_id", None) or get_request_id() or cid

        log_payload: dict[str, Any] = {
            "timestamp": now,
            "level": record.levelname,
            "service": getattr(record, "service", self.service),
            "environment": getattr(record, "environment", self.environment),
            "event": getattr(record, "event", record.getMessage()),
            "correlation_id": cid,
            "request_id": rid,
        }

        # Optional canonical fields
        if hasattr(record, "duration_ms") and record.duration_ms is not None:
            try:
                log_payload["duration_ms"] = round(float(record.duration_ms), 2)
            except (ValueError, TypeError):
                pass

        if hasattr(record, "status") and record.status is not None:
            log_payload["status"] = record.status

        if hasattr(record, "error_code") and record.error_code is not None:
            log_payload["error_code"] = record.error_code

        # Exception information (sanitized)
        if record.exc_info and record.exc_info[1]:
            log_payload["exception"] = sanitize_exception(record.exc_info[1])

        # Extra attributes attached to the LogRecord (sanitized)
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "service", "environment", "event",
            "correlation_id", "request_id", "duration_ms", "status", "error_code",
        }
        extra = {k: v for k, v in record.__dict__.items() if k not in standard_attrs and not k.startswith("_")}
        if extra:
            log_payload["extra"] = sanitize_log_dict(extra)

        return json.dumps(log_payload, default=str)


class InfrastructureLogger:
    """Structured infrastructure logger with automatic PHI/secret redaction."""

    def __init__(self, name: str = "thali.infrastructure") -> None:
        self._logger = logging.getLogger(name)

    def info(self, event: str, **kwargs: Any) -> None:
        safe_data = sanitize_log_dict(kwargs)
        cid = get_correlation_id()
        if cid and "correlation_id" not in safe_data:
            safe_data["correlation_id"] = cid
        self._logger.info(event, extra={"event": event, **safe_data})

    def warning(self, event: str, **kwargs: Any) -> None:
        safe_data = sanitize_log_dict(kwargs)
        cid = get_correlation_id()
        if cid and "correlation_id" not in safe_data:
            safe_data["correlation_id"] = cid
        self._logger.warning(event, extra={"event": event, **safe_data})

    def error(self, event: str, **kwargs: Any) -> None:
        safe_data = sanitize_log_dict(kwargs)
        cid = get_correlation_id()
        if cid and "correlation_id" not in safe_data:
            safe_data["correlation_id"] = cid
        self._logger.error(event, extra={"event": event, **safe_data})


def configure_logging(
    service: str = "thali-plate",
    environment: str = "development",
    level: str = "INFO",
    structured: bool = True,
) -> None:
    """Configure the root logging handler with StructuredJsonFormatter."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicate log lines
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler()
    if structured:
        handler.setFormatter(StructuredJsonFormatter(service=service, environment=environment))
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
        )
    root.addHandler(handler)
