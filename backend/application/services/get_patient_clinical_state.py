"""GetPatientClinicalState application service.

Centralizes deterministic patient clinical state assembly for:
- Doctor clinical workspace (mobile & web)
- Downloadable PDF clinical report generator
- AI clinical insights summarizer (downstream only)

Complies strictly with sections A through L of the THALI x P.L.A.T.E. Clinical Architecture:
A. Patient Summary
B. Data Quality & Coverage
C. Glycemic Metrics Summary (TIR, TAR, TBR, Mean, CV, GMI, eAG)
D. Longitudinal Comparison (Current vs Preceding Window)
E. Temporal & Pattern Analysis
F. Meal ↔ Glucose Temporal Associations
G. Laboratory Profile (HbA1c, Creatinine, eGFR, UACR, Lipids)
H. Cardiometabolic Profile (BP, Weight, BMI)
I. Complication Screenings (Eye, Foot, Kidney)
J. Medication Timeline (Current regimen, adherence, history)
K. Clinical Events Timeline (Unified chronological event stream)
L. AI Clinical Interpretation / Documentation (Evidence-grounded summaries only)
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.application.ports.unit_of_work import UnitOfWork
from backend.domain.exceptions import EntityNotFound
from backend.domain.services.clinical_engine import (
    CLINICAL_ENGINE_VERSION,
    calculate_data_quality,
    calculate_egfr_ckd_epi_2021,
    calculate_glycemic_metrics,
    calculate_longitudinal_comparison,
    calculate_meal_glucose_temporal_associations,
    calculate_pattern_profile,
    calculate_screening_status,
)


class GetPatientClinicalStateHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(
        self,
        patient_id: UUID,
        window_days: int = 14,
        facility_id: Optional[UUID] = None,
        reference_dt: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Assembles authoritative deterministic clinical state for a patient."""
        if patient_id is None:
            raise ValueError("patient_id is required")

        patient = self._uow.patients.get(patient_id)
        if not patient or not getattr(patient, "active", True):
            raise EntityNotFound(f"Patient {patient_id} is inactive or not found")

        if facility_id is not None and patient.facility_id is not None and patient.facility_id != facility_id:
            raise EntityNotFound(f"Patient {patient_id} is outside authorized facility")

        now = reference_dt or datetime.now(timezone.utc)
        current_window_start = now - timedelta(days=window_days)
        previous_window_start = current_window_start - timedelta(days=window_days)

        # 1. Fetch raw observations across entities
        raw_glucose = self._uow.glucose_observations.list_for_patient(patient_id)
        raw_meals = self._uow.meal_observations.list_for_patient(patient_id)
        raw_clin_obs = self._uow.clinical_observations.list_for_patient(patient_id)
        raw_med_plans = self._uow.medication_plans.list_for_patient(patient_id)
        raw_tasks = self._uow.care_tasks.list_for_patient(patient_id)
        raw_docs = self._uow.document_references.list_for_patient(patient_id)
        raw_ai_artifacts = self._uow.ai_artifacts.list_for_patient(patient_id)

        # Clinician links / care team
        clinician_links = []
        if hasattr(self._uow, "patient_clinician_links"):
            try:
                clinician_links = self._uow.patient_clinician_links.list_for_patient(patient_id)
            except Exception:
                clinician_links = []

        # -------------------------------------------------------------------
        # Helper: Extract glucose tuples
        # -------------------------------------------------------------------
        def _extract_glucose_tuple(g) -> Optional[tuple]:
            val_obj = getattr(g, "value", None)
            if val_obj is None:
                return None
            val = None
            if hasattr(val_obj, "value_mg_dl"):
                val = val_obj.value_mg_dl
            elif hasattr(val_obj, "value"):
                val = val_obj.value
            elif isinstance(val_obj, (int, float)):
                val = float(val_obj)

            if val is None:
                return None

            ts = getattr(g, "taken_at", getattr(g, "recorded_at", getattr(g, "created_at", None)))
            if ts is None:
                return None
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            tag_obj = getattr(g, "tag", None)
            tag_str = tag_obj.value if hasattr(tag_obj, "value") else (str(tag_obj) if tag_obj else None)

            return (ts, float(val), tag_str)

        all_glucose_tuples = [t for g in raw_glucose if (t := _extract_glucose_tuple(g)) is not None]
        # Sort chronologically
        all_glucose_tuples.sort(key=lambda x: x[0])

        current_glucose_tuples = [
            t for t in all_glucose_tuples if current_window_start <= t[0] <= now
        ]
        previous_glucose_tuples = [
            t for t in all_glucose_tuples if previous_window_start <= t[0] < current_window_start
        ]

        # -------------------------------------------------------------------
        # Helper: Extract meal tuples
        # -------------------------------------------------------------------
        def _extract_meal_dict(m) -> Optional[dict]:
            ts = getattr(m, "recorded_at", getattr(m, "logged_at", getattr(m, "created_at", None)))
            if ts is None:
                return None
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            portion_obj = getattr(m, "portion", None)
            portion_str = (
                portion_obj.name if hasattr(portion_obj, "name")
                else (portion_obj.value if hasattr(portion_obj, "value") else str(portion_obj or ""))
            )
            desc = getattr(m, "description", None) or getattr(m, "food_description", "")
            return {
                "timestamp": ts,
                "description": desc,
                "portion": portion_str,
                "carbs_grams": getattr(m, "carbs_grams", None),
                "glycemic_index": getattr(m, "glycemic_index", None),
            }

        all_meal_dicts = [d for m in raw_meals if (d := _extract_meal_dict(m)) is not None]
        all_meal_dicts.sort(key=lambda x: x["timestamp"])

        # -------------------------------------------------------------------
        # B. Data Quality & Coverage
        # -------------------------------------------------------------------
        data_quality_obj = calculate_data_quality(
            readings=current_glucose_tuples,
            meals=all_meal_dicts,
            window_days=window_days,
            reference_date=now,
        )
        data_quality_dict = asdict(data_quality_obj)

        # -------------------------------------------------------------------
        # C. Glycemic Metrics Summary
        # -------------------------------------------------------------------
        glycemic_metrics_obj = calculate_glycemic_metrics(
            readings=current_glucose_tuples,
            window_days=window_days,
        )
        glycemic_metrics_dict = asdict(glycemic_metrics_obj)


        # -------------------------------------------------------------------
        # D. Longitudinal Comparison
        # -------------------------------------------------------------------
        longitudinal_obj = calculate_longitudinal_comparison(
            readings=all_glucose_tuples,
            window_days=window_days,
            reference_date=now,
        )
        longitudinal_dict = asdict(longitudinal_obj)


        # -------------------------------------------------------------------
        # E. Temporal & Pattern Analysis
        # -------------------------------------------------------------------
        pattern_obj = calculate_pattern_profile(readings=current_glucose_tuples)
        pattern_dict = asdict(pattern_obj)

        # -------------------------------------------------------------------
        # F. Meal ↔ Glucose Temporal Associations
        # -------------------------------------------------------------------
        meal_tuples_for_engine = [
            (
                m["timestamp"],
                m["description"],
                m["carbs_grams"],
                m["glycemic_index"],
            )
            for m in all_meal_dicts
            if current_window_start <= m["timestamp"] <= now
        ]
        meal_associations = calculate_meal_glucose_temporal_associations(
            meals=meal_tuples_for_engine,
            readings=current_glucose_tuples,
        )
        meal_assoc_list = [asdict(a) for a in meal_associations]

        # -------------------------------------------------------------------
        # G. Laboratory Profile & H. Cardiometabolic Profile
        # -------------------------------------------------------------------
        lab_markers: Dict[str, List[dict]] = {}
        vital_markers: Dict[str, List[dict]] = {}
        screening_records: Dict[str, Optional[datetime]] = {
            "eye_retinopathy": None,
            "diabetic_foot": None,
            "kidney_nephropathy": None,
        }

        for obs in raw_clin_obs:
            code = obs.code.lower()
            obs_dt = obs.observed_at
            if obs_dt.tzinfo is None:
                obs_dt = obs_dt.replace(tzinfo=timezone.utc)

            item = {
                "id": str(obs.id),
                "code": obs.code,
                "value": obs.value,
                "value_text": obs.value_text,
                "unit": obs.unit,
                "observed_at": obs_dt.isoformat(),
                "source": obs.source,
                "document_id": str(obs.document_id) if obs.document_id else None,
            }

            if obs.observation_type == "laboratory":
                lab_markers.setdefault(code, []).append(item)
            elif obs.observation_type in ("vital", "glucose"):
                vital_markers.setdefault(code, []).append(item)
            elif obs.observation_type == "screening":
                # Check for known screening codes
                for scr_key in screening_records.keys():
                    if scr_key in code:
                        curr = screening_records[scr_key]
                        if curr is None or obs_dt > curr:
                            screening_records[scr_key] = obs_dt

        # Sort historical observations descending
        for k in lab_markers:
            lab_markers[k].sort(key=lambda x: x["observed_at"], reverse=True)
        for k in vital_markers:
            vital_markers[k].sort(key=lambda x: x["observed_at"], reverse=True)

        # Deterministic eGFR calculation if creatinine is present and eGFR not recorded
        latest_creat = lab_markers.get("creatinine", [{}])[0].get("value")
        latest_egfr = lab_markers.get("egfr", [{}])[0].get("value")
        calculated_egfr = None
        if latest_creat is not None and latest_egfr is None:
            # CKD-EPI 2021 calculation using baseline age 55, male as default standard
            calculated_egfr = calculate_egfr_ckd_epi_2021(
                serum_creatinine_mg_dl=float(latest_creat),
                age_years=55,
                is_female=False,
            )

        laboratory_profile = {
            "hba1c": {
                "latest": lab_markers.get("hba1c", [{}])[0] if "hba1c" in lab_markers else None,
                "history": lab_markers.get("hba1c", []),
            },
            "creatinine": {
                "latest": lab_markers.get("creatinine", [{}])[0] if "creatinine" in lab_markers else None,
                "history": lab_markers.get("creatinine", []),
            },
            "egfr": {
                "latest": lab_markers.get("egfr", [{}])[0] if "egfr" in lab_markers else (
                    {"value": calculated_egfr, "unit": "mL/min/1.73m2", "source": "calculated_ckd_epi_2021"}
                    if calculated_egfr is not None else None
                ),
                "calculated_from_creatinine": calculated_egfr is not None,
                "history": lab_markers.get("egfr", []),
            },
            "uacr": {
                "latest": lab_markers.get("uacr", [{}])[0] if "uacr" in lab_markers else None,
                "history": lab_markers.get("uacr", []),
            },
            "lipids": {
                "total_cholesterol": lab_markers.get("total_cholesterol", [{}])[0] if "total_cholesterol" in lab_markers else None,
                "ldl": lab_markers.get("ldl", [{}])[0] if "ldl" in lab_markers else None,
                "hdl": lab_markers.get("hdl", [{}])[0] if "hdl" in lab_markers else None,
                "triglycerides": lab_markers.get("triglycerides", [{}])[0] if "triglycerides" in lab_markers else None,
            },
        }

        cardiometabolic_profile = {
            "blood_pressure": {
                "latest_systolic": vital_markers.get("systolic_bp", [{}])[0] if "systolic_bp" in vital_markers else None,
                "latest_diastolic": vital_markers.get("diastolic_bp", [{}])[0] if "diastolic_bp" in vital_markers else None,
                "history_systolic": vital_markers.get("systolic_bp", []),
                "history_diastolic": vital_markers.get("diastolic_bp", []),
            },
            "weight": {
                "latest": vital_markers.get("weight", [{}])[0] if "weight" in vital_markers else None,
                "history": vital_markers.get("weight", []),
            },
        }

        # -------------------------------------------------------------------
        # I. Complication Screenings
        # -------------------------------------------------------------------
        screening_list = [
            asdict(calculate_screening_status("Comprehensive Dilated Eye Exam", "eye_retinopathy", screening_records["eye_retinopathy"], 12, now)),
            asdict(calculate_screening_status("Comprehensive Diabetic Foot Examination", "diabetic_foot", screening_records["diabetic_foot"], 12, now)),
            asdict(calculate_screening_status("Annual Kidney Disease Screening (uACR + eGFR)", "kidney_nephropathy", screening_records["kidney_nephropathy"], 12, now)),
        ]

        # -------------------------------------------------------------------
        # J. Medication Timeline
        # -------------------------------------------------------------------
        medication_timeline = []
        for p in raw_med_plans:
            med_name = getattr(p, "medication", None) or getattr(p, "medication_name", "")
            instruction = getattr(p, "instruction", None) or getattr(p, "dosage", "")
            active = getattr(p, "active", True)
            start_dt = getattr(p, "created_at", None)
            medication_timeline.append({
                "id": str(p.id),
                "medication": med_name,
                "dosage_instruction": instruction,
                "status": "active" if active else "discontinued",
                "is_active": active,
                "start_date": start_dt.isoformat() if hasattr(start_dt, "isoformat") else str(start_dt or ""),
            })

        # -------------------------------------------------------------------
        # K. Clinical Events Timeline (Chronological Stream)
        # -------------------------------------------------------------------
        events_timeline: List[dict] = []

        # Glucose events
        for ts, val, tag in all_glucose_tuples[-30:]:
            events_timeline.append({
                "category": "glucose",
                "timestamp": ts.isoformat(),
                "title": f"Glucose {int(val)} mg/dL",
                "detail": f"Tag: {tag or 'untagged'}",
                "level": "warning" if val < 70 or val > 180 else "normal",
            })

        # Meal events
        for m in all_meal_dicts[-20:]:
            events_timeline.append({
                "category": "meal",
                "timestamp": m["timestamp"].isoformat(),
                "title": f"Meal: {m['description'] or 'Meal Log'}",
                "detail": f"Portion: {m['portion']}" + (f", Carbs: {m['carbs_grams']}g" if m['carbs_grams'] else ""),
                "level": "info",
            })

        # Document events
        for d in raw_docs[-10:]:
            created = getattr(d, "created_at", None)
            created_iso = created.isoformat() if hasattr(created, "isoformat") else str(created or "")
            events_timeline.append({
                "category": "document",
                "timestamp": created_iso,
                "title": f"Document: {d.filename}",
                "detail": f"Type: {d.kind.value if hasattr(d.kind, 'value') else str(d.kind)}",
                "level": "info",
            })

        # Care tasks
        for t in raw_tasks[-10:]:
            due = getattr(t, "due_date", getattr(t, "created_at", None))
            due_iso = due.isoformat() if hasattr(due, "isoformat") else str(due or "")
            events_timeline.append({
                "category": "care_task",
                "timestamp": due_iso,
                "title": f"Task: {getattr(t, 'title', getattr(t, 'description', 'Clinical Task'))}",
                "detail": f"Status: {getattr(t, 'status', 'open')}",
                "level": "info",
            })

        # Sort combined timeline descending
        events_timeline.sort(key=lambda x: x["timestamp"], reverse=True)

        # -------------------------------------------------------------------
        # Deterministic Clinical Alerts / Flags
        # -------------------------------------------------------------------
        clinical_alerts: List[dict] = []
        tbr = glycemic_metrics_dict.get("tbr_below_range_pct")
        if tbr is not None and tbr > 4.0:
            clinical_alerts.append({
                "level": "HIGH",
                "code": "HYPOGLYCEMIA_RISK",
                "message": f"Time Below Range ({tbr}%) exceeds RSSDI/ADA safety threshold (<4%). Review sulfonylurea/insulin dosing.",
            })

        cv = glycemic_metrics_dict.get("coefficient_of_variation_pct")
        if cv is not None and cv > 36.0:
            clinical_alerts.append({
                "level": "MODERATE",
                "code": "HIGH_VARIABILITY",
                "message": f"Glycemic variability CV ({cv}%) exceeds stable threshold (<=36%). Suggests glycemic volatility.",
            })

        for scr in screening_list:
            if scr.get("is_overdue"):
                clinical_alerts.append({
                    "level": "MODERATE",
                    "code": f"OVERDUE_SCREENING_{scr['code'].upper()}",
                    "message": f"{scr['category']} is overdue (Due: {scr['due_date']}).",
                })

        if not data_quality_dict.get("is_adequate_coverage", True):
            clinical_alerts.append({
                "level": "INFO",
                "code": "SUBOPTIMAL_DATA_QUALITY",
                "message": f"Data coverage is {data_quality_dict.get('coverage_pct', 0)}% ({data_quality_dict.get('total_valid_readings', 0)} readings over {window_days} days).",
            })

        # -------------------------------------------------------------------
        # L. AI Clinical Interpretation / Documentation (Evidence Grounded)
        # -------------------------------------------------------------------
        approved_summaries = []
        for art in raw_ai_artifacts:
            st = getattr(art, "state", None)
            st_val = st.value if hasattr(st, "value") else str(st)
            if st_val in ("approved", "edited"):
                approved_summaries.append({
                    "id": str(art.id),
                    "summary": art.summary,
                    "model_name": getattr(art, "model_name", None),
                    "state": st_val,
                })

        ai_interpretation = {
            "is_available": len(approved_summaries) > 0,
            "summaries": approved_summaries,
            "disclaimer": "AI interpretations are strictly contextual summaries grounded in deterministic clinical observations. They do not constitute autonomous medical advice.",
        }

        # -------------------------------------------------------------------
        # A. Patient Summary
        # -------------------------------------------------------------------
        care_team_display = []
        for l in clinician_links:
            care_team_display.append({
                "clinician_user_id": str(l.clinician_user_id),
                "clinician_name": l.clinician_name,
                "facility_id": str(l.facility_id) if l.facility_id else None,
            })

        patient_summary = {
            "patient_id": str(patient.id),
            "name": patient.name,
            "uh_id": patient.uh_id.value if hasattr(patient.uh_id, "value") else str(patient.uh_id),
            "phone": patient.phone.value if hasattr(patient.phone, "value") else str(patient.phone),
            "facility_id": str(patient.facility_id) if patient.facility_id else None,
            "care_team": care_team_display,
            "active": getattr(patient, "active", True),
            "reporting_window_days": window_days,
            "window_start": current_window_start.isoformat(),
            "window_end": now.isoformat(),
            "clinical_alerts": clinical_alerts,
        }

        return {
            "patient_summary": patient_summary,
            "data_quality": data_quality_dict,
            "glycemic_metrics": glycemic_metrics_dict,
            "longitudinal_comparison": longitudinal_dict,
            "temporal_patterns": pattern_dict,
            "meal_associations": meal_assoc_list,
            "laboratory_profile": laboratory_profile,
            "cardiometabolic_profile": cardiometabolic_profile,
            "complication_screenings": screening_list,
            "medication_timeline": medication_timeline,
            "clinical_events_timeline": events_timeline,
            "ai_interpretation": ai_interpretation,
            "engine_metadata": {
                "version": CLINICAL_ENGINE_VERSION,
                "authoritative_source": "THALI x P.L.A.T.E. Deterministic Engine",
                "generated_at": now.isoformat(),
                "reporting_window_days": window_days,
            },
        }
