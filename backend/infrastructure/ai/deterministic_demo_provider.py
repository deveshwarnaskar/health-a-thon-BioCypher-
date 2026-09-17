"""Deterministic Demo AI Provider (Gate 10M).

Provides reproducible, offline, deterministic draft generation for development,
testing, and CI without external network calls or cloud dependencies.

Maintains strict assistive posture:
- Summarizes authorized evidence
- Rebuffs prompt injection attempts
- Never prescribes, titrates, or diagnoses
"""

from __future__ import annotations

import logging
from typing import Any

from backend.application.ports.ai import (
    AIProvider,
    AIProviderResult,
    AITaskDefinition,
    AITaskType,
    EvidencePackage,
)

logger = logging.getLogger(__name__)


class DeterministicDemoProvider:
    """Deterministic AI Provider for automated tests and development."""

    def __init__(self, model_name: str = "deterministic-demo-v1") -> None:
        self.model_name = model_name
        self.provider_name = "deterministic_demo"

    def generate(self, task: AITaskDefinition, evidence: EvidencePackage) -> AIProviderResult:
        """Synthesize a deterministic draft summary from authorized evidence."""
        obs_count = len(evidence.observations)
        meal_count = len(evidence.meals)
        task_count = len(evidence.care_tasks)
        med_count = len(evidence.medication_context)

        # Compute summary metrics deterministically if glucose readings present
        if obs_count > 0:
            readings = [o.get("value_mg_dl", 0) for o in evidence.observations if isinstance(o.get("value_mg_dl"), (int, float))]
            avg_glucose = round(sum(readings) / len(readings), 1) if readings else 0
            glucose_desc = f"{obs_count} glucose readings recorded (mean {avg_glucose} mg/dL)."
        else:
            glucose_desc = "No recent glucose readings recorded."

        meal_desc = f"{meal_count} meal(s) logged." if meal_count else "No recent meals logged."
        task_desc = f"{task_count} care task(s) on file." if task_count else "No pending care tasks."
        med_desc = f"{med_count} active medication regimen(s) on record (adherence context only)." if med_count else "No active medication plans."

        # Scan untrusted notes for adversarial instructions and neutralize
        user_notes_summary = ""
        if evidence.untrusted_user_notes:
            sanitized_notes: list[str] = []
            for note in evidence.untrusted_user_notes:
                # Flag injection attempts
                lower = note.lower()
                if any(x in lower for x in ["ignore", "prescribe", "titrate", "dosage", "bypass", "system"]):
                    sanitized_notes.append("[User comment containing non-clinical instruction discarded]")
                else:
                    sanitized_notes.append(note[:60])
            user_notes_summary = f" Patient notes referenced: {'; '.join(sanitized_notes)}."

        if task.task_type == AITaskType.CLINICAL_SUMMARY:
            summary = (
                f"Clinical Summary Draft (Assistive Only):\n"
                f"- Glycemic status: {glucose_desc}\n"
                f"- Nutrition: {meal_desc}\n"
                f"- Workflow: {task_desc}\n"
                f"- Medication context: {med_desc}"
                f"{user_notes_summary}\n"
                f"Note: This synthesis is an unreviewed draft requiring clinician review."
            )
        elif task.task_type == AITaskType.OBSERVATION_SYNTHESIS:
            summary = (
                f"Observation Synthesis Draft:\n"
                f"{glucose_desc} {meal_desc} Regimens: {med_count} active."
                f"{user_notes_summary}"
            )
        else:
            summary = (
                f"Care Task Review Draft:\n"
                f"{task_desc} Glycemic context: {glucose_desc}"
                f"{user_notes_summary}"
            )

        return AIProviderResult(
            success=True,
            summary=summary,
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=5.0,
            usage={"prompt_tokens": 100, "completion_tokens": 50},
        )
