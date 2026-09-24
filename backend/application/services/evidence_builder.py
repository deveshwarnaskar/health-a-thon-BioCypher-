"""Deterministic Evidence Builder (Gate 10M).

Constructs an immutable, authorized, reproducible EvidencePackage for AI synthesis.
Enforces multi-tenant isolation, patient active check, and minimal necessary evidence principles.
Separates verified clinical evidence from untrusted user content.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from backend.application.ports.ai import EvidencePackage
from backend.application.ports.unit_of_work import UnitOfWork
from backend.domain.exceptions import EntityNotFound

logger = logging.getLogger(__name__)


class EvidenceBuilder:
    """Deterministic, server-authoritative evidence package builder."""

    def build(
        self,
        patient_id: UUID,
        tenant_id: UUID,
        uow: UnitOfWork,
        user_notes: str | None = None,
        max_observations: int = 20,
        max_meals: int = 10,
        max_tasks: int = 10,
    ) -> EvidencePackage:
        """Assembles verified clinical evidence into a deterministic package."""
        patient = uow.patients.get(patient_id)
        if patient is None:
            raise EntityNotFound(f"Patient {patient_id} not found")

        if not getattr(patient, "active", True):
            raise ValueError(f"Patient {patient_id} is deactivated — cannot generate evidence")

        # 1. Glucose observations (sorted deterministically by taken_at descending)
        raw_observations = uow.glucose_observations.list_for_patient(patient_id)
        def _get_ts(obs: Any) -> str:
            t = getattr(obs, "taken_at", None) or getattr(obs, "created_at", None)
            return t.isoformat() if hasattr(t, "isoformat") else str(t or "")

        sorted_observations = sorted(raw_observations, key=_get_ts, reverse=True)[:max_observations]
        formatted_observations: list[dict[str, Any]] = []
        for o in sorted_observations:
            val = getattr(o, "value", None)
            val_mg_dl = getattr(val, "value_mg_dl", getattr(val, "value", val))
            tag = getattr(o, "tag", None)
            tag_str = getattr(tag, "value", str(tag or "unknown"))
            formatted_observations.append({
                "id": str(o.id),
                "value_mg_dl": val_mg_dl,
                "tag": tag_str,
                "taken_at": _get_ts(o),
            })

        # 2. Meal observations
        raw_meals = uow.meal_observations.list_for_patient(patient_id)[:max_meals]
        formatted_meals: list[dict[str, Any]] = []
        for m in raw_meals:
            portion = getattr(m, "portion", None)
            portion_str = str(getattr(portion, "volume", portion or ""))
            formatted_meals.append({
                "id": str(m.id),
                "description": getattr(m, "description", ""),
                "portion_katori": portion_str,
                "logged_at": _get_ts(m),
            })

        # 3. Care tasks
        raw_tasks = uow.care_tasks.list_for_patient(patient_id)[:max_tasks]
        formatted_tasks: list[dict[str, Any]] = []
        for t in raw_tasks:
            st = getattr(t, "status", None)
            st_str = getattr(st, "value", str(st or ""))
            due = getattr(t, "due_at", None)
            formatted_tasks.append({
                "id": str(t.id),
                "title": getattr(t, "title", ""),
                "status": st_str,
                "due_at": due.isoformat() if hasattr(due, "isoformat") else (str(due) if due else None),
            })

        # 4. Medication plans (READ-ONLY context: AI CANNOT MODIFY)
        raw_plans = uow.medication_plans.list_for_patient(patient_id)
        formatted_medications: list[dict[str, Any]] = []
        for p in raw_plans:
            if getattr(p, "active", True):
                formatted_medications.append({
                    "id": str(p.id),
                    "medication_name": getattr(p, "medication_name", ""),
                    "dosage_text": getattr(p, "dosage_text", ""),
                    "instructions": getattr(p, "instructions", ""),
                })

        # 5. Untrusted user notes (isolated from instructions)
        untrusted_notes: list[str] = []
        if user_notes and user_notes.strip():
            # Clean control chars
            cleaned = "".join(ch for ch in user_notes.strip() if ch.isprintable() or ch in "\n\r\t")
            untrusted_notes.append(cleaned[:1000])

        # 6. Deterministic evidence hash (SHA-256 of canonical JSON)
        canonical_dict = {
            "patient_id": str(patient_id),
            "tenant_id": str(tenant_id),
            "observations": formatted_observations,
            "meals": formatted_meals,
            "care_tasks": formatted_tasks,
            "medication_context": formatted_medications,
            "untrusted_user_notes": untrusted_notes,
        }
        canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
        evidence_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        return EvidencePackage(
            patient_id=patient_id,
            tenant_id=tenant_id,
            observations=formatted_observations,
            meals=formatted_meals,
            care_tasks=formatted_tasks,
            medication_context=formatted_medications,
            untrusted_user_notes=untrusted_notes,
            evidence_hash=evidence_hash,
            created_at=datetime.now(timezone.utc),
        )
