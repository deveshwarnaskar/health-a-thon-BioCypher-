"""ListAIReviewArtifacts query handler (Gate 10F-B).

Returns the clinician's pending-review queue restricted to the authenticated
member's facility:

    artifact.state == PENDING_REVIEW        (repository)
    AND artifact.tenant_id == ctx.tenant_id (repository + RLS)
    AND patient.facility_id == facility_id  (handler)
    AND patient.active == true              (handler)

Deactivated patients and patients outside the member's facility never surface
in the clinician queue.
"""

from __future__ import annotations

from ..dtos.clinician_reads import AIReviewArtifactList, AIReviewArtifactRecord
from ..ports.unit_of_work import UnitOfWork
from ..queries import ListAIReviewArtifacts
from ...domain.entities.ai_artifact import ReviewState
from ...domain.exceptions import EntityNotFound


class ListAIReviewArtifactsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, q: ListAIReviewArtifacts) -> AIReviewArtifactList:
        artifacts = self._uow.ai_artifacts.list_by_state(ReviewState.PENDING_REVIEW)
        items = [
            record
            for record in (self._maybe_record(q, a) for a in artifacts)
            if record is not None
        ]
        items.sort(key=lambda r: (r.created_at, r.artifact_id))
        items = items[: q.limit]
        return AIReviewArtifactList(artifact_count=len(items), items=items)

    def _maybe_record(
        self, q: ListAIReviewArtifacts, artifact
    ) -> AIReviewArtifactRecord | None:
        try:
            patient = self._uow.patients.get(artifact.patient_id)
        except EntityNotFound:
            return None
        if not getattr(patient, "active", True):
            return None
        if patient.facility_id != q.facility_id:
            return None
        return AIReviewArtifactRecord(
            artifact_id=artifact.id,
            patient_id=artifact.patient_id,
            artifact_kind=artifact.artifact_kind,
            state=artifact.state.value,
            summary=artifact.summary,
            created_at=artifact.created_at,
        )