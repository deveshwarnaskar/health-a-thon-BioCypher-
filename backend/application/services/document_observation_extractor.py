"""Document observation extraction and clinical validation pipeline.

Extracts text from medical documents (e.g., PDF lab reports) and parses structured
clinical observations (HbA1c, eGFR, Creatinine, UACR, Lipids, Vitals).
Enforces deterministic range validation before saving to clinical_observations.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from backend.domain.entities.clinical_observation import ClinicalObservation, ObservationType
from backend.application.ports.unit_of_work import UnitOfWork

logger = logging.getLogger("thali.document_extractor")

# Clinical validation ranges for deterministic observation ingestion
CLINICAL_BOUNDS = {
    "hba1c": {"min": 3.0, "max": 22.0, "unit": "%", "type": ObservationType.LABORATORY},
    "creatinine": {"min": 0.2, "max": 18.0, "unit": "mg/dL", "type": ObservationType.LABORATORY},
    "egfr": {"min": 1.0, "max": 200.0, "unit": "mL/min/1.73m2", "type": ObservationType.LABORATORY},
    "uacr": {"min": 0.0, "max": 6000.0, "unit": "mg/g", "type": ObservationType.LABORATORY},
    "total_cholesterol": {"min": 50.0, "max": 650.0, "unit": "mg/dL", "type": ObservationType.LABORATORY},
    "ldl": {"min": 15.0, "max": 450.0, "unit": "mg/dL", "type": ObservationType.LABORATORY},
    "hdl": {"min": 10.0, "max": 160.0, "unit": "mg/dL", "type": ObservationType.LABORATORY},
    "triglycerides": {"min": 20.0, "max": 2000.0, "unit": "mg/dL", "type": ObservationType.LABORATORY},
    "systolic_bp": {"min": 60.0, "max": 260.0, "unit": "mmHg", "type": ObservationType.VITAL},
    "diastolic_bp": {"min": 30.0, "max": 160.0, "unit": "mmHg", "type": ObservationType.VITAL},
    "weight": {"min": 20.0, "max": 350.0, "unit": "kg", "type": ObservationType.VITAL},
    "fasting_glucose": {"min": 30.0, "max": 600.0, "unit": "mg/dL", "type": ObservationType.GLUCOSE},
    "postprandial_glucose": {"min": 30.0, "max": 600.0, "unit": "mg/dL", "type": ObservationType.GLUCOSE},
}


def extract_text_from_payload(payload: bytes, mime_type: str) -> str:
    """Extract text from document payload using available parsers."""
    clean_mime = (mime_type or "").strip().lower()

    if clean_mime == "application/pdf":
        try:
            import pymupdf  # type: ignore
            doc = pymupdf.open(stream=payload, filetype="pdf")
            extracted = []
            for page in doc:
                text = page.get_text()
                if text:
                    extracted.append(text)
            doc.close()
            return "\n".join(extracted)
        except Exception as e:
            logger.warning("pymupdf extraction failed: %s", e)

    # Plain text fallback
    try:
        return payload.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def parse_and_validate_observations(
    text: str,
    patient_id: UUID,
    facility_id: Optional[UUID],
    document_id: UUID,
    observed_at: Optional[datetime] = None,
    source: str = "laboratory_document",
) -> list[ClinicalObservation]:
    """Parse text for clinical metrics, validate bounds, and produce ClinicalObservation objects."""
    if not text:
        return []

    timestamp = observed_at or datetime.now(timezone.utc)
    observations: list[ClinicalObservation] = []

    # Patterns for structured extraction
    patterns = [
        ("hba1c", r"(?:HbA1c|Hemoglobin\s*A1c|Glycated\s*Hemoglobin|A1C)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:%|percent)?"),
        ("creatinine", r"(?:Serum\s+Creatinine|Creatinine|S\.Cr)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mg/dL|mg/dl)?"),
        ("egfr", r"(?:eGFR|Estimated\s+GFR|GFR)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mL/min(?:/1\.73m2)?|ml/min)?"),
        ("uacr", r"(?:UACR|Urine\s+Albumin[- ]to[- ]Creatinine\s+Ratio|Microalbumin/Creatinine\s+Ratio)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mg/g|mg/gm)?"),
        ("total_cholesterol", r"(?:Total\s+Cholesterol|Cholesterol\s+Total)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mg/dL|mg/dl)?"),
        ("ldl", r"(?:LDL(?:\s+Cholesterol)?|LDL-C)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mg/dL|mg/dl)?"),
        ("hdl", r"(?:HDL(?:\s+Cholesterol)?|HDL-C)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mg/dL|mg/dl)?"),
        ("triglycerides", r"(?:Triglycerides|TG)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mg/dL|mg/dl)?"),
        ("weight", r"(?:Weight|Body\s+Weight|Wt)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:kg|kgs)?"),
        ("fasting_glucose", r"(?:Fasting\s+(?:Blood\s+)?(?:Sugar|Glucose)|FBS)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mg/dL|mg/dl)?"),
        ("postprandial_glucose", r"(?:PPBS|Post[- ]?Prandial\s+(?:Blood\s+)?(?:Sugar|Glucose))\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mg/dL|mg/dl)?"),
    ]

    seen_codes: set[str] = set()

    for code, pat in patterns:
        if code in seen_codes:
            continue
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            try:
                val = float(match.group(1))
                spec = CLINICAL_BOUNDS.get(code)
                if spec and spec["min"] <= val <= spec["max"]:
                    seen_codes.add(code)
                    obs = ClinicalObservation(
                        id=uuid4(),
                        patient_id=patient_id,
                        facility_id=facility_id,
                        observation_type=spec["type"],
                        code=code,
                        value=val,
                        value_text=str(val),
                        unit=spec["unit"],
                        observed_at=timestamp,
                        recorded_at=datetime.now(timezone.utc),
                        source=source,
                        document_id=document_id,
                        metadata_json={
                            "extracted_pattern": pat,
                            "raw_matched_string": match.group(0),
                            "validation_rule": f"{spec['min']} <= val <= {spec['max']}",
                        },
                    )
                    observations.append(obs)
            except (ValueError, TypeError):
                continue

    # Blood pressure pair
    bp_match = re.search(r"(?:BP|Blood\s+Pressure)\s*[:=]?\s*([0-9]{2,3})\s*/\s*([0-9]{2,3})", text, re.IGNORECASE)
    if bp_match:
        try:
            sys_val = float(bp_match.group(1))
            dia_val = float(bp_match.group(2))
            sys_spec = CLINICAL_BOUNDS["systolic_bp"]
            dia_spec = CLINICAL_BOUNDS["diastolic_bp"]
            if sys_spec["min"] <= sys_val <= sys_spec["max"]:
                observations.append(
                    ClinicalObservation(
                        id=uuid4(),
                        patient_id=patient_id,
                        facility_id=facility_id,
                        observation_type=sys_spec["type"],
                        code="systolic_bp",
                        value=sys_val,
                        value_text=str(int(sys_val)),
                        unit=sys_spec["unit"],
                        observed_at=timestamp,
                        recorded_at=datetime.now(timezone.utc),
                        source=source,
                        document_id=document_id,
                        metadata_json={"raw_matched_string": bp_match.group(0)},
                    )
                )
            if dia_spec["min"] <= dia_val <= dia_spec["max"]:
                observations.append(
                    ClinicalObservation(
                        id=uuid4(),
                        patient_id=patient_id,
                        facility_id=facility_id,
                        observation_type=dia_spec["type"],
                        code="diastolic_bp",
                        value=dia_val,
                        value_text=str(int(dia_val)),
                        unit=dia_spec["unit"],
                        observed_at=timestamp,
                        recorded_at=datetime.now(timezone.utc),
                        source=source,
                        document_id=document_id,
                        metadata_json={"raw_matched_string": bp_match.group(0)},
                    )
                )
        except (ValueError, TypeError):
            pass

    return observations


def ingest_document_observations(
    uow: UnitOfWork,
    patient_id: UUID,
    facility_id: Optional[UUID],
    document_id: UUID,
    payload: bytes,
    mime_type: str,
    observed_at: Optional[datetime] = None,
) -> list[ClinicalObservation]:
    """Extract text from uploaded document payload and ingest validated clinical observations."""
    text = extract_text_from_payload(payload, mime_type)
    if not text:
        return []

    observations = parse_and_validate_observations(
        text=text,
        patient_id=patient_id,
        facility_id=facility_id,
        document_id=document_id,
        observed_at=observed_at,
    )

    for obs in observations:
        uow.clinical_observations.add(obs)

    return observations
