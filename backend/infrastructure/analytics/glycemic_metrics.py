"""Glycemic analytics engine (infrastructure re-export).

Re-exports pure domain calculation service functions for backward compatibility.
"""
from backend.domain.services.glycemic_metrics import (
    GLUCOSE_HIGH,
    GLUCOSE_LOW,
    compute_window_metrics,
)

__all__ = ["compute_window_metrics", "GLUCOSE_LOW", "GLUCOSE_HIGH"]
