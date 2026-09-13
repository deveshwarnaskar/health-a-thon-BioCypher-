"""Patient confirmation authority for patient-originated observations (Gate 03).

Distinct from the clinician review state machine used for AI artifacts: patient
confirmation applies to extracted observations (meals, glucose, voice/self
reports), and can never be collapsed into a generic "approved" flag.
"""

from enum import Enum


class PatientConfirmationState(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    REJECTED = "rejected"