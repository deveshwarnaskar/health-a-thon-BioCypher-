"""WhatsApp free-text intake transform — uses the full Hinglish parser.

Converts a verified WhatsApp message body into a standard application command:

- Glucose readings  ("fasting 138", "subah sugar 142", "180")
    → IngestGlucoseReading
- Everything else (meals, Hinglish food descriptions)
    → LogMealDraft  (with carbs_grams and gi_category pre-computed)
- Ambiguous readings ("shayad 230 or 330")
    → LogMealDraft with is_ambiguous=True  (handler sends clarification)

Domain invariants (20–600 mg/dL boundary, confirmation state) are enforced
downstream — this module performs NO clinical interpretation.
"""
from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from backend.application.commands import IngestGlucoseReading, LogMealDraft
from backend.domain.value_objects import GlucoseValue, KatoriVolume, MealPortion, ReadingTag
from backend.infrastructure.parsing.hinglish_parser import (
    ParsedInput,
    ambiguous_reading_values,
    parse_inbound,
)
from backend.infrastructure.parsing.intent_firewall import (
    IntentFirewall,
    IntentType,
    IntentVerdict,
)
from backend.infrastructure.parsing.nutrition_taxonomy import (
    classify_text,
    estimate_nutrition,
)

# Map Hinglish parser tag strings → domain ReadingTag enum
_TAG_TO_DOMAIN: dict[str, ReadingTag] = {
    "fasting":       ReadingTag.FASTING,
    "pre":           ReadingTag.PRE_MEAL,
    "postprandial":  ReadingTag.POST_MEAL,
    "postbreakfast": ReadingTag.POST_BREAKFAST,
    "postlunch":     ReadingTag.POST_LUNCH,
    "postdinner":    ReadingTag.POST_DINNER,
}


def _map_tag(tag: str | None) -> ReadingTag | None:
    if not tag:
        return None
    return _TAG_TO_DOMAIN.get(tag.lower())


_PORTION_VOLUMES: dict[str, int] = {"s": 150, "m": 220, "l": 350}


def _map_portion(letter: str | None, food_key: str = "meal") -> MealPortion | None:
    if not letter:
        return None
    vol = _PORTION_VOLUMES.get(letter.lower())
    if not vol:
        return None
    return MealPortion(food_key=food_key, katori=KatoriVolume(vol), quantity=1.0)


def parse_intake_text(
    text: str,
    *,
    patient_id: UUID,
    correlation_id: UUID | None,
    recorded_at: datetime,
    source_metadata: dict | None = None,
) -> IngestGlucoseReading | LogMealDraft:
    """Parse one verified WhatsApp message body into an application command.

    Raises ``InvalidGlucoseValue`` (domain) when a glucose-shaped payload
    is outside the safe 20–600 mg/dL boundary.
    """
    stripped = text.strip()

    # 1. Check for ambiguous reading first ("shayad 230 or 330")
    ambiguous = ambiguous_reading_values(stripped)
    if ambiguous:
        # Return a LogMealDraft flagged as ambiguous so the handler can send
        # a clarification prompt and skip the meal confirm loop.
        return LogMealDraft(
            patient_id=patient_id,
            description=stripped,
            recorded_at=recorded_at,
            correlation_id=correlation_id,
            source_metadata=source_metadata,
            is_ambiguous=True,
            ambiguous_candidates=ambiguous,
        )

    # 2. Full Hinglish parse
    parsed: ParsedInput = parse_inbound(stripped)
    effective_occurred_at = parsed.stated_time or recorded_at

    if parsed.is_reading and parsed.reading is not None:
        tag = _map_tag(parsed.reading_tag)
        return IngestGlucoseReading(
            patient_id=patient_id,
            value=GlucoseValue(int(parsed.reading)),
            taken_at=effective_occurred_at,
            tag=tag,
            correlation_id=correlation_id,
            source_metadata=source_metadata,
        )

    # 3. Meal — pre-compute nutrition
    items = classify_text(stripped)
    portion_letter = parsed.portion_letter
    nutrition = estimate_nutrition(items, portion_letter or "m")
    food_key = items[0]["item"] if items else "meal"
    portion = _map_portion(portion_letter, food_key) if portion_letter else None

    return LogMealDraft(
        patient_id=patient_id,
        description=stripped,
        portion=portion,
        carbs_grams=nutrition.carbs_grams if items else None,
        gi_category=nutrition.gi_category if items else None,
        classified_items=items,
        recorded_at=effective_occurred_at,
        correlation_id=correlation_id,
        source_metadata=source_metadata,
        is_ambiguous=False,
        ambiguous_candidates=[],
    )


def dispatch_hint(cmd: IngestGlucoseReading | LogMealDraft) -> str:
    """Coarse resource-kind hint for audit (GLUCOSE | MEAL)."""
    return "GLUCOSE" if isinstance(cmd, IngestGlucoseReading) else "MEAL"


__all__ = [
    "dispatch_hint",
    "parse_intake_text",
    "parse_inbound",
    "ambiguous_reading_values",
    "ParsedInput",
    "IntentFirewall",
    "IntentType",
    "IntentVerdict",
]
