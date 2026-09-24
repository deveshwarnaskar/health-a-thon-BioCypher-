"""CreateMedicationPlan command (Gate 04).

CLINICIAN-AUTHORED ONLY (frozen authority model):

- The acting clinician's role is resolved from the authoritative
  ``CareTeamMember`` record in the application handler.
- The domain ``MedicationPlan`` construction enforces
  ``CareTeamRole.can_author_medication`` as the invariant; a non-clinician actor
  is rejected by the domain and the transaction rolls back.

No AI, patient, caregiver, or automated model may create a plan.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CreateMedicationPlan:
    patient_id: UUID
    prescribed_by_user_id: UUID
    medication: str
    instruction: str
    correlation_id: UUID | None = None