"""Gate 09 — WhatsApp free-text intake transform.

A pure, infrastructure-free interpretation of a verified WhatsApp message body
into a standard Gate 04 application command:

- ``"180"`` / ``"180 fasting"``-style payloads  → ``IngestGlucoseReading``
- anything else                                  → ``LogMealDraft``

All domain invariants (20–600 mg/dL glucose boundary, phone validation, meal
confirmation state) are enforced downstream by the domain value objects — this
module performs NO clinical interpretation.
"""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from backend.application.commands import (
    IngestGlucoseReading,
    LogMealDraft,
)
from backend.domain.value_objects import GlucoseValue, ReadingTag

# e.g. "180", "180 fasting", "190  after dinner", "185 fasting"
_GLUCOSE_RE = re.compile(
    r"^\s*(?P<value>\d{1,3})(?:\s+(?P<tag>[a-z]+(?:\s+[a-z]+)*))?\s*$",
    re.IGNORECASE,
)

_TAG_ALIASES: dict[str, ReadingTag] = {
    "fasting": ReadingTag.FASTING,
    "premeal": ReadingTag.PRE_MEAL,
    "pre meal": ReadingTag.PRE_MEAL,
    "before meal": ReadingTag.PRE_MEAL,
    "beforemeals": ReadingTag.PRE_MEAL,
    "postbreakfast": ReadingTag.POST_BREAKFAST,
    "post breakfast": ReadingTag.POST_BREAKFAST,
    "after breakfast": ReadingTag.POST_BREAKFAST,
    "postlunch": ReadingTag.POST_LUNCH,
    "post lunch": ReadingTag.POST_LUNCH,
    "after lunch": ReadingTag.POST_LUNCH,
    "postdinner": ReadingTag.POST_DINNER,
    "post dinner": ReadingTag.POST_DINNER,
    "after dinner": ReadingTag.POST_DINNER,
}


def _normalize_tag(raw: str | None) -> ReadingTag | None:
    if not raw:
        return None
    return _TAG_ALIASES.get(raw.strip().lower())


def parse_intake_text(
    text: str,
    *,
    patient_id: UUID,
    correlation_id: UUID | None,
    recorded_at: datetime,
) -> IngestGlucoseReading | LogMealDraft:
    """Turn one verified message body into a command.

    Raises the domain ``InvalidGlucoseValue`` when a glucose-shaped payload
    falls outside the safe 20–600 mg/dL boundary, preserving the domain
    invariant as the authoritative gate.
    """
    match = _GLUCOSE_RE.match(text)
    if match:
        tag_text = match.groupdict().get("tag")
        tag = _normalize_tag(tag_text)
        if tag is not None or not tag_text:
            return IngestGlucoseReading(
                patient_id=patient_id,
                value=GlucoseValue(int(match.group("value"))),
                taken_at=recorded_at,
                tag=tag,
                correlation_id=correlation_id,
            )
    return LogMealDraft(
        patient_id=patient_id,
        description=text.strip(),
        recorded_at=recorded_at,
        correlation_id=correlation_id,
    )


def dispatch_hint(cmd: IngestGlucoseReading | LogMealDraft) -> str:
    """Coarse resource-kind hint for audit purposes (GLUCOSE | MEAL)."""
    if isinstance(cmd, IngestGlucoseReading):
        return "GLUCOSE"
    return "MEAL"