"""GetAIReviewArtifact query handler (Gate 10F-B).

Resolves ONE AI review artifact. The patient must exist, be active, and belong
to the authenticated member's facility; otherwise the artifact is treated as
not found so cross-facility/deactivated reads never leak existence.
"""

from __future__ import annotations

from ..dtos.clinician_reads import AIReviewArtifactRecord
from ..ports.unit_of_work import UnitOfWork
from ..queries import GetAIReviewArtifact
from ...domain.exceptions import EntityNotFound


class GetAIReviewArtifactHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, q: GetAIReviewArtifact) -> AIReviewArtifactRecord:
        artifact = self._uow.ai_artifacts.get(q.artifact_id)
        patient = self._uow.patients.get(artifact.patient_id)
        if not getattr(patient, "active", True):
            raise EntityNotFound(f"ai_artifact {q.artifact_id} not found")
        if patient.facility_id != q.facility_id:
            raise EntityNotFound(f"ai_artifact {q.artifact_id} not found")
        return AIReviewArtifactRecord(
            artifact_id=artifact.id,
            patient_id=artifact.patient_id,
            artifact_kind=artifact.artifact_kind,
            state=artifact.state.value,
            summary=artifact.summary,
            created_at=artifact.created_at,
        )