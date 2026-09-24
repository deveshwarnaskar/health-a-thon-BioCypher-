"""IdentityPatientResolver (Gate 08).

Resolves a verified platform identity (``actor_id``) to a tenant patient via
the explicit identity-patient mapping. Absent, inactive, or cross-tenanted
mappings resolve to a non-active result — they NEVER yield a patient grant.

Rules:

- No mapping   → denied
- Inactive mapping → denied
- Patient deactivated → denied
- The tenant scoping of the mapping is guaranteed by the tenant-bound UoW/RLS.
- Phone-number changes never alter identity mappings (keyed on user_id).
"""

from dataclasses import dataclass
from uuid import UUID

from ...domain.exceptions import EntityNotFound
from ..ports.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class ResolvedPatientAccess:
    """Outcome of identity → patient resolution.

    ``active`` is True only when a mapping exists, the mapping is active, and
    the mapped patient is itself active. ``patient_id`` may be present even
    when ``active`` is False so callers can render a precise denial.
    """

    patient_id: UUID | None
    actor_id: UUID
    active: bool


class IdentityPatientResolver:
    """Application service that resolves identity to patient access."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def resolve(self, actor_id: UUID) -> ResolvedPatientAccess:
        mapping = self._uow.identity_mappings.get_by_user_id(actor_id)
        if mapping is None:
            return ResolvedPatientAccess(patient_id=None, actor_id=actor_id, active=False)
        if not mapping.active:
            return ResolvedPatientAccess(
                patient_id=mapping.patient_id, actor_id=actor_id, active=False
            )
        try:
            patient = self._uow.patients.get(mapping.patient_id)
        except EntityNotFound:
            return ResolvedPatientAccess(
                patient_id=mapping.patient_id, actor_id=actor_id, active=False
            )
        return ResolvedPatientAccess(
            patient_id=mapping.patient_id, actor_id=actor_id, active=patient.active
        )