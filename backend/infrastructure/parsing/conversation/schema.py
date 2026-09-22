"""Structured intent contract (spec §7, §19, §22).

The single output contract between the conversation layer and the AI provider.
Every provider (Sarvam, future LLMs, or the deterministic fallback) must return
a ``StructuredIntent``; nothing below relies on free-form prompts for state
declisions. Entities carry provenance and confidence so the deterministic
safety engine can audit AI-originated values (§22, §32).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .taxonomy import ConversationIntent


class Confidence(str, Enum):
    HIGH = "high"
    MID = "mid"
    LOW = "low"


class ProvenanceSource(str, Enum):
    DETERMINISTIC = "deterministic"       # regex/parser derived
    AI_ASSISTED = "ai_assisted"           # AI corroborated a deterministic extract
    AI_ORIGINATED = "ai_originated"       # AI proposed a value with no deterministic anchor
    NONE = "none"


class SafetyFlag(str, Enum):
    EMERGENCY = "emergency"
    DIAGNOSIS_REQUEST = "diagnosis_request"
    DOSAGE_CHANGE = "dosage_change"
    NON_HEALTH_REQUEST = "non_health_request"
    PROMPT_INJECTION = "prompt_injection"
    CROSS_PATIENT_REQUEST = "cross_patient_request"
    PHI_PERSISTENCE_REQUEST = "phi_persistence_request"
    OUT_OF_RANGE_VALUE = "out_of_range_value"
    UNKNOWN_VALUE = "unknown_value"


class EntityRef(BaseModel):
    source_text: str = ""
    value: Any
    confidence: Confidence = Confidence.LOW
    provenance: ProvenanceSource = ProvenanceSource.NONE


class GlucoseEntity(BaseModel):
    value_mg_dl: int | None = None
    tag: str | None = None          # fasting/pre_meal/post_meal/post_lunch/...
    taken_at: datetime | None = None
    raw_occurred_at: str | None = None
    confidence: Confidence = Confidence.LOW
    provenance: ProvenanceSource = ProvenanceSource.NONE

    @field_validator("value_mg_dl")
    @classmethod
    def _validate_range(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if not (10 <= v <= 1000):
            raise ValueError(f"glucose value {v} outside plausible 10-1000 range")
        return v


class MealEntity(BaseModel):
    description: str = ""
    items: list[dict[str, Any]] = Field(default_factory=list)
    portion_letter: str | None = None   # s/m/l
    confidence: Confidence = Confidence.LOW
    provenance: ProvenanceSource = ProvenanceSource.NONE


class MedicationEntity(BaseModel):
    medication: str | None = None
    plan_id: str | None = None
    dose_units: str | None = None
    taken: bool | None = None
    when: str | None = None             # morning/evening/night
    confidence: Confidence = Confidence.LOW
    provenance: ProvenanceSource = ProvenanceSource.NONE


class TaskEntity(BaseModel):
    description: str = ""
    due_label: str | None = None        # human label: "kal subah 8 baje"
    due_at: datetime | None = None
    confidence: Confidence = Confidence.LOW
    provenance: ProvenanceSource = ProvenanceSource.NONE


class LanguageEntity(BaseModel):
    code: str = ""                      # iso 639-1
    display_name: str = ""
    confidence: Confidence = Confidence.LOW


class HandoffEntity(BaseModel):
    reason: str = ""
    is_emergency: bool = False
    confidence: Confidence = Confidence.LOW


class StructuredIntent(BaseModel):
    """Canonical AI/parser output for one inbound message."""

    intent: ConversationIntent
    is_supported: bool = True
    confidence: Confidence = Confidence.MID
    raw_text: str = ""
    normalized_text: str = ""
    interactive_reply_id: str | None = None

    glucose: GlucoseEntity = Field(default_factory=GlucoseEntity)
    meal: MealEntity = Field(default_factory=MealEntity)
    medication: MedicationEntity = Field(default_factory=MedicationEntity)
    task: TaskEntity = Field(default_factory=TaskEntity)
    language: LanguageEntity = Field(default_factory=LanguageEntity)
    handoff: HandoffEntity = Field(default_factory=HandoffEntity)

    requires_confirmation: bool = False
    safety_flags: list[SafetyFlag] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        return not self.safety_flags

    def add_flag(self, flag: SafetyFlag, note: str | None = None) -> None:
        if flag not in self.safety_flags:
            self.safety_flags.append(flag)
        if note:
            self.notes.append(note)

    @property
    def any_entity(self) -> bool:
        return bool(
            self.glucose.value_mg_dl
            or self.meal.description
            or self.medication.medication
            or self.task.description
            or self.language.code
            or self.handoff.reason
        )


__all__ = [
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
    "utcnow",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)