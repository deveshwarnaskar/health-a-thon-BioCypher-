"""ListCaregiverPatients query handler (Gate 10E-B).

Returns only relationships that are CURRENTLY authorized for the authenticated
caregiver within the authenticated tenant:

    relationship.tenant_id == ctx.tenant_id            (repository + RLS)
    AND relationship.caregiver_user_id == ctx.actor_id (repository)
    AND status == VERIFIED
    AND revoked_at IS NULL
    AND (expires_at IS NULL OR now < expires_at)
    AND patient exists
    AND patient.active == true

The query never trusts client-controlled relationship_id or patient_id — the
discovery derives authorized relationships from the authenticated actor only.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..dtos.caregiver import CaregiverAuthorizedPatient, CaregiverPatientList
from ..ports.clock import Clock
from ..ports.unit_of_work import UnitOfWork
from ..queries import ListCaregiverPatients
from ...domain.entities import CaregiverRelationshipStatus
from ...domain.exceptions import EntityNotFound


class ListCaregiverPatientsHandler:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def handle(self, q: ListCaregiverPatients) -> CaregiverPatientList:
        relationships = self._uow.caregiver_relationships.list_for_caregiver(
            q.caregiver_user_id
        )
        now = self._clock.now()
        items: list[CaregiverAuthorizedPatient] = []
        for rel in relationships:
            if not self._currently_authorized(rel, now):
                continue
            try:
                patient = self._uow.patients.get(rel.patient_id)
            except EntityNotFound:
                # Relationship points at a patient that no longer exists in the
                # tenant: never discover it.
                continue
            if not getattr(patient, "active", False):
                # Deactivated-patient invariant: a VERIFIED relationship never
                # yields a deactivated patient in caregiver discovery.
                continue
            items.append(
                CaregiverAuthorizedPatient(
                    relationship_id=rel.id,
                    patient_id=rel.patient_id,
                    relationship_label=rel.relationship,
                    status=rel.status.value,
                    capabilities=tuple(sorted(rel.capabilities)),
                    expires_at=rel.expires_at,
                    name=getattr(patient, "name", ""),
                )
            )
        return CaregiverPatientList(patient_count=len(items), items=items)

    @staticmethod
    def _currently_authorized(rel, now: datetime) -> bool:
        if rel.status is not CaregiverRelationshipStatus.VERIFIED:
            return False
        if rel.revoked_at is not None:
            return False
        expires_at = rel.expires_at
        if expires_at is not None:
            # Storage adapters may return naive datetimes; normalize so the
            # comparison is tz-safe regardless of the backend dialect.
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            if now >= expires_at:
                return False
        return True