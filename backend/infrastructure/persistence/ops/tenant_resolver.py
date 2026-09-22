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

from typing import Callable
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from backend.application.ops.contracts import ResolvedChannelPatient
from backend.application.ops.ports import ChannelTenantResolver
from backend.domain.value_objects.phone_number import normalize_raw
from ..models.patient_models import PatientModel


class SqlAlchemyChannelTenantResolver:
    """SQLAlchemy-backed phone → (tenant, patient) routing anchor.

    Accepts either a Session or a session factory/sessionmaker. When initialized
    with a factory, each resolve() call uses a short-lived, bounded session that
    is immediately closed, ensuring resilient recovery after database/network disconnects.
    """

    def __init__(
        self,
        session_factory_or_session: sessionmaker[Session] | Session | Callable[[], Session],
    ) -> None:
        if isinstance(session_factory_or_session, Session):
            self._session_factory: Callable[[], Session] = lambda: session_factory_or_session
            self._owns_session = False
        else:
            self._session_factory = session_factory_or_session
            self._owns_session = True

    def resolve(self, phone: str) -> ResolvedChannelPatient | None:
        try:
            normalized = normalize_raw(phone)
        except Exception:
            return None

        session = self._session_factory()
        try:
            if session.get_bind().dialect.name == "postgresql":
                row = self._resolve_via_routing_function(session, normalized)
                if row is not None:
                    return row

            # Non-PostgreSQL fallback (also used if the routing function is absent).
            plus_normalized = "+" + normalized.lstrip("+")
            plain_digits = normalized.lstrip("+")
            last10 = plain_digits[-10:] if len(plain_digits) >= 10 else plain_digits
            stmt = (
                select(PatientModel.id, PatientModel.tenant_id)
                .where(
                    (PatientModel.phone == normalized)
                    | (PatientModel.phone == plus_normalized)
                    | (PatientModel.phone.endswith(last10)),
                    PatientModel.active.is_(True),
                )
                .order_by(PatientModel.created_at.desc())
                .limit(1)
            )
            result = session.execute(stmt).first()
            if result is None:
                try:
                    from config.settings import Settings

                    s = Settings()
                    if s.whatsapp.test_number_mode:
                        test_stmt = (
                            select(PatientModel.id, PatientModel.tenant_id)
                            .where(PatientModel.active.is_(True))
                            .order_by(PatientModel.created_at.desc())
                            .limit(1)
                        )
                        test_result = session.execute(test_stmt).first()
                        if test_result is not None:
                            return ResolvedChannelPatient(
                                tenant_id=UUID(str(test_result.tenant_id)),
                                patient_id=UUID(str(test_result.id)),
                            )
                except Exception:
                    pass
                return None
            return ResolvedChannelPatient(
                tenant_id=UUID(str(result.tenant_id)),
                patient_id=UUID(str(result.id)),
            )
        except Exception:
            session.rollback()
            return None
        finally:
            if self._owns_session:
                session.close()

    def _resolve_via_routing_function(
        self, session: Session, normalized: str
    ) -> ResolvedChannelPatient | None:
        try:
            stmt = text("SELECT tenant_id, patient_id FROM public.resolve_channel_tenant(:phone)")
            row = session.execute(stmt, {"phone": normalized}).first()
            if row is None and not normalized.startswith("+"):
                row = session.execute(stmt, {"phone": "+" + normalized}).first()
        except Exception:
            session.rollback()
            return None
        if row is None:
            try:
                from config.settings import Settings

                s = Settings()
                if s.whatsapp.test_number_mode:
                    stmt2 = text(
                        "SELECT tenant_id, id AS patient_id FROM public.patients WHERE active = true ORDER BY created_at DESC LIMIT 1"
                    )
                    test_row = session.execute(stmt2).first()
                    if test_row is not None:
                        return ResolvedChannelPatient(
                            tenant_id=UUID(str(test_row[0])),
                            patient_id=UUID(str(test_row[1])),
                        )
            except Exception:
                pass
            return None
        return ResolvedChannelPatient(
            tenant_id=UUID(str(row[0])),
            patient_id=UUID(str(row[1])),
        )


__all__ = ["SqlAlchemyChannelTenantResolver"]