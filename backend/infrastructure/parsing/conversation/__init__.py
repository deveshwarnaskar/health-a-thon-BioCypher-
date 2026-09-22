"""Deterministic multilingual conversation parsing (spec §6–§11).

Like ``hinglish_parser`` / ``nutrition_taxonomy``, deterministic parsing lives in
``infrastructure.parsing``; the application conversational layer consumes it
(faithful to the existing ``intake_text`` carve-out in the import-boundary
audit).
"""

from .extractors import (
    normalize_digits,
    extract_glucose,
    extract_meal,
    extract_medication,
    extract_task,
    extract_language,
    extract_time_offset,
)
from .schema import (
    Confidence,
    ProvenanceSource,
    SafetyFlag,
    EntityRef,
    GlucoseEntity,
    MealEntity,
    MedicationEntity,
    TaskEntity,
    LanguageEntity,
    HandoffEntity,
    StructuredIntent,
)
from .taxonomy import ConversationIntent, DidResolvedIntent, LEGACY_HANDLED, to_legacy

__all__ = [
    "normalize_digits",
    "extract_glucose",
    "extract_meal",
    "extract_medication",
    "extract_task",
    "extract_language",
    "extract_time_offset",
    "Confidence",
    "ProvenanceSource",
    "SafetyFlag",
    "EntityRef",
    "GlucoseEntity",
    "MealEntity",
    "MedicationEntity",
    "TaskEntity",
    "LanguageEntity",
    "HandoffEntity",
    "StructuredIntent",
    "ConversationIntent",
    "DidResolvedIntent",
    "LEGACY_HANDLED",
    "to_legacy",
]