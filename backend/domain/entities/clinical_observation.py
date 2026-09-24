"""ClinicalObservation domain entity.

Stores structured clinical observations beyond glycemic/meal records:
- laboratory values (HbA1c, serum creatinine, eGFR, UACR, lipid panel)
- cardiometabolic vitals (blood pressure systolic/diastolic, body weight, BMI)
- clinical screening records (diabetic retinopathy eye screening, foot exam, nephropathy)
- symptoms and contextual events
- document-extracted observations preserving original document provenance
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4


class ObservationType(str, Enum):
    LABORATORY = "lab"
    CARDIOMETABOLIC = "vital"
    VITAL = "vital"
    SCREENING = "screening"
    SYMPTOM = "symptom"
    CONTEXT = "context"
    GLUCOSE = "glucose"


@dataclass
class ClinicalObservation:
    id: UUID = field(default_factory=uuid4)
    patient_id: UUID = field(default_factory=uuid4)
    facility_id: UUID | None = None
    observation_type: ObservationType = ObservationType.LABORATORY
    code: str = ""  # e.g. "hba1c", "creatinine", "egfr", "uacr", "blood_pressure_systolic", "blood_pressure_diastolic", "weight", "bmi", "eye_screening", "foot_screening", "kidney_screening"
    value: float | None = None
    value_text: str | None = None
    unit: str | None = None  # e.g. "%", "mg/dL", "mL/min/1.73m2", "mg/g", "mmHg", "kg", "kg/m2"
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "laboratory"  # "laboratory", "document_extraction", "device", "clinician_entry", "patient_reported"
    document_id: UUID | None = None
    metadata_json: dict | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
