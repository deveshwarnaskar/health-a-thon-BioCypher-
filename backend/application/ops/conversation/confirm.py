"""Confirmation & correction engine (spec §15, §17).

Draft lifecycle:
    extract → confirm prompt (/ no draft hint) → CONFIRM / CORRECT / CANCEL

Neutral wording: prompts and acknowledgements quote the patient's own values
verbatim and never label them (no "normal", "high", "dangerous", "diabetes",
carbs/GI words) — see §17-b wording requirements and the
``contains_forbidden_interpretation`` guard in ``safety.py``.

The engine never persists anything the patient has not confirmed; the domain
entities (MealObservation/GlucoseObservation) are the single writers of their
confirmation state.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from backend.domain.entities import MealObservation
from backend.domain.value_objects import PatientConfirmationState

from .safety import contains_forbidden_interpretation
from .state import DraftKind, fingerprint_glucose, fingerprint_meal

_CONFIRM_PROMPT_SUFFIX = (
    "\n\nKya yeh sahi hai? Reply karein: 'Haan' (theek hai) ya "
    "'Cancel' — ya galat ho toh dobara likhein."
)


def build_glucose_confirm_prompt(value_mg_dl: int, tag: str | None) -> str:
    tag_line = f" ({tag})" if tag else ""
    msg = f"Aapne sugar {value_mg_dl} mg/dL{tag_line} darz kiya tha."
    assert not contains_forbidden_interpretation(msg)
    return msg + _CONFIRM_PROMPT_SUFFIX


def build_meal_confirm_prompt(description: str, portion_label: str | None) -> str:
    portion = f" ({portion_label})" if portion_label else ""
    msg = f"Aapne khana darz kiya: {description}{portion}."
    assert not contains_forbidden_interpretation(msg)
    return msg + _CONFIRM_PROMPT_SUFFIX


def build_medication_confirm_prompt(medication: str | None, when: str | None, dose: str | None) -> str:
    when_line = f" {when}" if when else ""
    dose_line = f" ({dose})" if dose else ""
    msg = f"Medicine darz kiya jayega: {medication or 'dawai'}{dose_line}{when_line}."
    assert not contains_forbidden_interpretation(msg)
    return msg + _CONFIRM_PROMPT_SUFFIX


def build_task_confirm_prompt(description: str, due_label: str | None) -> str:
    due = f" ({due_label})" if due_label else ""
    msg = f"Reminder bana jayega: {description}{due}."
    assert not contains_forbidden_interpretation(msg)
    return msg + _CONFIRM_PROMPT_SUFFIX


def build_confirm_ack(kind: DraftKind, display: str) -> str:
    """Confirmation acknowledgement — neutral, quotes patient's own words."""
    if kind == DraftKind.MEAL:
        return f"Dhanyavaad! Khana darz ho gaya: {display}. ✅ Record your care team dashboard par save ho gaya hai."
    if kind == DraftKind.GLUCOSE:
        return f"Dhanyavaad! Sugar reading save ho gayi: {display}. ✅"
    if kind == DraftKind.MEDICATION:
        return f"Dhanyavaad! Medicine record ho gaya: {display}. ✅"
    if kind == DraftKind.CARE_TASK:
        return f"Reminder set ho gaya: {display}. ✅"
    return "Dhanyavaad! Record save kar diya gaya hai. ✅"


def build_cancel_ack(kind: DraftKind) -> str:
    if kind == DraftKind.MEAL:
        return "Theek hai, khane ka record cancel kar diya gaya hai."
    if kind == DraftKind.GLUCOSE:
        return "Theek hai, sugar reading cancel kar di gayi hai."
    if kind == DraftKind.MEDICATION:
        return "Theek hai, medicine record ho nahi sakta — koi baat nahi."
    if kind == DraftKind.CARE_TASK:
        return "Theek hai, reminder cancel kar diya gaya hai."
    return "Theek hai, cancel kar diya gaya hai."


def find_pending_meal_by_fingerprint(
    *,
    meals: list[MealObservation],
    description: str,
    portion_letter: str | None,
    now: datetime,
) -> MealObservation | None:
    """Locate the pending meal draft matching a fingerprint (newest first)."""
    fp = fingerprint_meal(description=description, portion_letter=portion_letter)
    pending = [
        m for m in meals
        if getattr(m, "confirmation", None) == PatientConfirmationState.PENDING
    ]
    for candidate in sorted(
        pending,
        key=lambda m: getattr(m, "recorded_at", getattr(m, "created_at", now)) or now,
        reverse=True,
    ):
        if fingerprint_meal(
            description=getattr(candidate, "description", description),
            portion_letter=(getattr(candidate, "portion", None).katori
                            and ("l" if candidate.portion.katori.volume_ml >= 350
                                 else "s" if candidate.portion.katori.volume_ml <= 150
                                 else "m")),
        ) == fp:
            return candidate
    return None


def find_pending_glucose_by_fingerprint(
    *,
    glucose_rows,
    value_mg_dl: int,
    tag: str | None,
) -> object | None:
    """Locate the pending glucose observation matching a fingerprint."""
    fp = fingerprint_glucose(value_mg_dl=value_mg_dl, tag=tag)
    candidates = [
        g for g in glucose_rows
        if getattr(g, "confirmation", None) == PatientConfirmationState.PENDING
        and (
            fingerprint_glucose(
                value_mg_dl=getattr(getattr(g, "value", None), "value_mg_dl", None) or 0,
                tag=getattr(g, "tag", None),
            )
            == fp
        )
    ]
    candidates.sort(key=lambda g: getattr(g, "created_at", None), reverse=True)
    return candidates[0] if candidates else None


__all__ = [
    "build_glucose_confirm_prompt",
    "build_meal_confirm_prompt",
    "build_medication_confirm_prompt",
    "build_task_confirm_prompt",
    "build_confirm_ack",
    "build_cancel_ack",
    "find_pending_meal_by_fingerprint",
    "find_pending_glucose_by_fingerprint",
]