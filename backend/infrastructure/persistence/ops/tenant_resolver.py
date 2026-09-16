"""SqlAlchemyChannelTenantResolver (Gate 09 §19.2/§20).

Resolves a verified channel sender phone to a (tenant_id, patient_id) routing
anchor. On PostgreSQL this is deliberately routed through a narrow
``SECURITY DEFINER`` function (``public.resolve_channel_tenant``) created in
migration 0003: a plain cross-tenant SELECT would return zero rows under the
force-enabled row-level security used by the application role. The function
returns ONLY UUIDs — never clinical data — and the caller must re-confirm the
patient inside the tenant's RLS scope before touching domain state.

On non-PostgreSQL dialects (development/in-memory) the direct patient lookup is
used; there is no RLS to bypass there.
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.application.ops.contracts import ResolvedChannelPatient
from backend.application.ops.ports import ChannelTenantResolver
from backend.domain.value_objects.phone_number import normalize_raw
from ..models.patient_models import PatientModel


class SqlAlchemyChannelTenantResolver:
    """SQLAlchemy-backed phone → (tenant, patient) routing anchor."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def resolve(self, phone: str) -> ResolvedChannelPatient | None:
        try:
            normalized = normalize_raw(phone)
        except Exception:
            return None

        if self.session.get_bind().dialect.name == "postgresql":
            row = self._resolve_via_routing_function(normalized)
            if row is not None:
                return row

        # Non-PostgreSQL fallback (also used if the routing function is absent).
        stmt = (
            select(PatientModel.id, PatientModel.tenant_id)
            .where(PatientModel.phone == normalized)
            .limit(1)
        )
        result = self.session.execute(stmt).first()
        if result is None:
            return None
        return ResolvedChannelPatient(
            tenant_id=UUID(str(result.tenant_id)),
            patient_id=UUID(str(result.id)),
        )

    def _resolve_via_routing_function(self, normalized: str) -> ResolvedChannelPatient | None:
        try:
            stmt = text("SELECT tenant_id, patient_id FROM public.resolve_channel_tenant(:phone)")
            row = self.session.execute(stmt, {"phone": normalized}).first()
        except Exception:
            self.session.rollback()
            return None
        if row is None:
            return None
        return ResolvedChannelPatient(
            tenant_id=UUID(str(row[0])),
            patient_id=UUID(str(row[1])),
        )


__all__ = ["SqlAlchemyChannelTenantResolver"]