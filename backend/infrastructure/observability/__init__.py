"""Observability infrastructure package (Gate 05)."""

from .logging import InfrastructureLogger, sanitize_log_dict

__all__ = [
    "InfrastructureLogger",
    "sanitize_log_dict",
]
