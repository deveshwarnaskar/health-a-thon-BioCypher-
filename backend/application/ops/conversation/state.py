"""Resumable conversation session state machine (spec §5).

Goals:
- Never lose an unconfirmed draft: if the worker restarts mid-confirmation the
  patient's pending observation (already persisted by the domain handler in
  PENDING state) is recovered from the unit of work, not from memory.
- Deterministic transitions only. AI never mutates the session.
- Skeletons: a session row is a thin, tenant-scoped pointer to state plus a
  fingerprint of the draft that is still awaiting confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class DraftKind(str, Enum):
    """What kind of clinical draft awaits confirmation in this session."""

    GLUCOSE = "glucose"
    MEAL = "meal"
    MEDICATION = "medication"
    CARE_TASK = "care_task"
    NONE = "none"


class ConversationState(str, Enum):
    """Spec §5 state machine (tenant-scoped, non-PHI)."""

    IDLE = "idle"                       # no open draft
    AWAITING_GLUCOSE_CONFIRM = "awaiting_glucose_confirm"
    AWAITING_MEAL_CONFIRM = "awaiting_meal_confirm"
    AWAITING_MEDICATION_CONFIRM = "awaiting_medication_confirm"
    AWAITING_TASK_CONFIRM = "awaiting_task_confirm"
    AWAITING_DOCUMENT_UPLOAD = "awaiting_document_upload"
    HANDOFF_OPEN = "handoff_open"
    BLOCKED = "blocked"                 # a safety flag is active for this session


# Session rows carry NO PHI: only state + a fingerprint pointing at the draft.
@dataclass
class ConversationSession:
    tenant_id: UUID
    patient_id: UUID
    state: ConversationState = ConversationState.IDLE
    draft_kind: DraftKind = DraftKind.NONE
    draft_fingerprint: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime | None = None

    def reset(self, now: datetime | None = None) -> None:
        self.state = ConversationState.IDLE
        self.draft_kind = DraftKind.NONE
        self.draft_fingerprint = ""
        self.context = {}
        self.updated_at = now

    def mark_draft(
        self,
        kind: DraftKind,
        fingerprint: str,
        context: dict[str, Any],
        now: datetime | None = None,
    ) -> None:
        self.draft_kind = kind
        self.draft_fingerprint = fingerprint
        self.context = context
        self.updated_at = now
        mapping = {
            DraftKind.GLUCOSE: ConversationState.AWAITING_GLUCOSE_CONFIRM,
            DraftKind.MEAL: ConversationState.AWAITING_MEAL_CONFIRM,
            DraftKind.MEDICATION: ConversationState.AWAITING_MEDICATION_CONFIRM,
            DraftKind.CARE_TASK: ConversationState.AWAITING_TASK_CONFIRM,
        }
        self.state = mapping.get(kind, ConversationState.IDLE)

    def is_awaiting(self, kind: DraftKind) -> bool:
        return self.draft_kind == kind and self.state != ConversationState.IDLE


def fingerprint_glucose(*, value_mg_dl: int, tag: str | None) -> str:
    return f"g:{value_mg_dl}:{tag or '-'}"


def fingerprint_meal(*, description: str, portion_letter: str | None) -> str:
    norm = " ".join((description or "").strip().lower().split())
    return f"m:{norm}:{portion_letter or '-'}"


def fingerprint_medication(*, medication: str, when: str | None) -> str:
    return f"med:{medication or ''}:{when or '-'}"


def fingerprint_task(*, description: str) -> str:
    norm = " ".join((description or "").strip().lower().split())
    return f"t:{norm}"


__all__ = [
    "ConversationSession",
    "ConversationState",
    "DraftKind",
    "fingerprint_glucose",
    "fingerprint_meal",
    "fingerprint_medication",
    "fingerprint_task",
]