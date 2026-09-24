"""BuildClinicalReportContext query handler (Gate 10N).

Assembles server-side evidence and clinical observations into a structured
report context with strict information asymmetry guarantees:
- Patient summary omits carbs_grams, glycemic_index, and AI internal hashes.
- Clinician summary preserves full clinical depth and review states.
- MedicationPlan is strictly read-only representation (no mutation/titration).
"""

from __future__ import annotations

from typing import Any
from ..ports.unit_of_work import UnitOfWork
from ..queries.build_clinical_report_context import BuildClinicalReportContext
from ...domain.exceptions import EntityNotFound
from ...domain.services.glycemic_metrics import compute_window_metrics


class BuildClinicalReportContextHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, q: BuildClinicalReportContext) -> dict[str, Any]:
        if q.patient_id is None:
            raise ValueError("patient_id is required to build report context")

        patient = self._uow.patients.get(q.patient_id)
        if not getattr(patient, "active", True):
            raise EntityNotFound(f"patient {q.patient_id} is inactive or not found")

        if q.facility_id is not None and patient.facility_id != q.facility_id:
            raise EntityNotFound(f"patient {q.patient_id} is outside authorized facility")

        glucose_obs = self._uow.glucose_observations.list_for_patient(q.patient_id)
        meal_obs = self._uow.meal_observations.list_for_patient(q.patient_id)
        med_plans = self._uow.medication_plans.list_for_patient(q.patient_id)
        ai_artifacts = self._uow.ai_artifacts.list_for_patient(q.patient_id)

        def _glucose_int(obs) -> int | None:
            if obs is None or obs.value is None:
                return None
            val = obs.value
            if hasattr(val, "value_mg_dl"):
                return val.value_mg_dl
            if hasattr(val, "value"):
                return val.value
            if isinstance(val, (int, float)):
                return int(val)
            return None

        values = [v for o in glucose_obs if (v := _glucose_int(o)) is not None]
        mean_glucose = round(sum(values) / len(values), 1) if values else None
        min_glucose = min(values) if values else None
        max_glucose = max(values) if values else None

        sorted_glucose = sorted(
            glucose_obs,
            key=lambda x: getattr(x, "taken_at", getattr(x, "recorded_at", getattr(x, "created_at", None))),
            reverse=True,
        )
        readings_list = []
        for g in sorted_glucose[:20]:
            ts = getattr(g, "taken_at", getattr(g, "recorded_at", getattr(g, "created_at", None)))
            ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            tag_str = g.tag.value if hasattr(getattr(g, "tag", None), "value") else str(getattr(g, "tag", "") or "")
            readings_list.append({
                "timestamp": ts_str,
                "value": _glucose_int(g),
                "tag": tag_str,
            })

        sorted_meals = sorted(
            meal_obs,
            key=lambda x: getattr(x, "recorded_at", getattr(x, "logged_at", getattr(x, "created_at", None))),
            reverse=True,
        )
        meals_list = []
        for m in sorted_meals[:20]:
            ts = getattr(m, "recorded_at", getattr(m, "logged_at", getattr(m, "created_at", None)))
            ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            portion_obj = getattr(m, "portion", None)
            portion_str = (
                portion_obj.name if hasattr(portion_obj, "name")
                else (portion_obj.value if hasattr(portion_obj, "value") else str(portion_obj or ""))
            )
            desc_str = getattr(m, "description", None) or getattr(m, "food_description", "")
            if q.report_type == "patient_summary":
                # Strict DTO asymmetry: NO carbs_grams, NO glycemic_index
                meals_list.append({
                    "timestamp": ts_str,
                    "description": desc_str,
                    "portion": portion_str,
                })
            else:
                meals_list.append({
                    "timestamp": ts_str,
                    "description": desc_str,
                    "portion": portion_str,
                    "carbs_grams": getattr(m, "carbs_grams", None),
                    "glycemic_index": getattr(m, "glycemic_index", None),
                })

        plans_list = []
        for p in med_plans:
            med_name = getattr(p, "medication", None) or getattr(p, "medication_name", "")
            instruction = getattr(p, "instruction", None) or getattr(p, "dosage", "")
            active = getattr(p, "active", True)
            plans_list.append({
                "id": str(p.id),
                "medication": med_name,
                "medication_name": med_name,
                "instruction": instruction,
                "dosage": instruction,
                "schedule": "",
                "status": "active" if active else "inactive",
                "active": active,
            })

        artifacts_list = []
        for a in ai_artifacts:
            state_val = a.state.value if hasattr(a.state, "value") else str(a.state)
            if q.report_type == "patient_summary":
                # Only approved or edited summaries exposed to patient; zero internal provenance hashes
                if state_val in ("approved", "edited"):
                    artifacts_list.append({
                        "summary": a.summary,
                    })
            else:
                artifacts_list.append({
                    "id": str(a.id),
                    "artifact_kind": a.artifact_kind,
                    "state": state_val,
                    "summary": a.summary,
                    "model_name": getattr(a, "model_name", None),
                })

        # Compute window metrics
        metric_readings = []
        for g in sorted_glucose:
            val = _glucose_int(g)
            if val is not None:
                ts = getattr(g, "taken_at", getattr(g, "recorded_at", getattr(g, "created_at", None)))
                ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
                tag_str = g.tag.value if hasattr(getattr(g, "tag", None), "value") else str(getattr(g, "tag", "") or "")
                metric_readings.append({
                    "value": float(val),
                    "tag": tag_str,
                    "taken_at": ts_str,
                })

        metric_meals = []
        for m in sorted_meals:
            ts = getattr(m, "recorded_at", getattr(m, "logged_at", getattr(m, "created_at", None)))
            ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            conf_val = getattr(getattr(m, "confirmation", None), "value", str(getattr(m, "confirmation", "") or ""))
            metric_meals.append({
                "carbs_grams": getattr(m, "carbs_grams", None),
                "gi_category": getattr(m, "glycemic_index", None),
                "recorded_at": ts_str,
                "confirmation": conf_val,
            })

        window_metrics = compute_window_metrics(metric_readings, metric_meals, window_days=14)

        if q.report_type == "patient_summary":
            metrics_payload = {
                "total_readings": window_metrics.get("total_readings", 0),
                "adherence_index": window_metrics.get("adherence_index", 0.0),
                "tir_in_range_pct": window_metrics.get("tir_in_range_pct", 0.0),
                "tir_above_range_pct": window_metrics.get("tir_above_range_pct", 0.0),
                "tir_below_range_pct": window_metrics.get("tir_below_range_pct", 0.0),
                "mean_glucose": window_metrics.get("mean_glucose"),
            }
        else:
            metrics_payload = window_metrics

        return {
            "patient": {
                "id": str(patient.id),
                "name": patient.name,
                "uh_id": patient.uh_id.value if hasattr(patient.uh_id, "value") else str(patient.uh_id),
                "facility_id": str(patient.facility_id) if patient.facility_id else None,
                "active": getattr(patient, "active", True),
            },
            "report_type": q.report_type,
            "glucose_summary": {
                "total_readings": len(values),
                "mean_glucose": mean_glucose,
                "min_glucose": min_glucose,
                "max_glucose": max_glucose,
                "readings": readings_list,
                "tir_in_range_pct": window_metrics.get("tir_in_range_pct"),
                "tir_above_range_pct": window_metrics.get("tir_above_range_pct"),
                "tir_below_range_pct": window_metrics.get("tir_below_range_pct"),
                "adherence_index": window_metrics.get("adherence_index"),
            },
            "meals": meals_list,
            "medication_plans": plans_list,
            "ai_artifacts": artifacts_list,
            "metrics": metrics_payload,
        }
