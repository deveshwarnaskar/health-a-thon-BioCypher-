"""SqlAlchemyConversationSessionStore (Gate 11, spec §5).

Durable implementation of the conversational layer's session pointer so an
unconfirmed draft survives a worker restart. Follows the same RLS discipline
as ``SqlAlchemyChannelTenantResolver``: a short-lived, bounded session per
call, with ``app.current_tenant_id`` bound before any query/upsert so the
FORCE RLS policy (migration 0012) isolates the row to the caller's tenant.
"""

from __future__ import annotations

from typing import Callable
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from backend.application.ops.conversation.state import (
    ConversationSession,
    ConversationState,
    DraftKind,
)
from ..models.conversation_models import ConversationSessionModel


class SqlAlchemyConversationSessionStore:
    """Session-factory-backed durable store conforming to ``SessionStore``."""

    def __init__(self, session_factory: sessionmaker[Session] | Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # -- RLS binding -------------------------------------------------------
    def _apply_tenant_context(self, session: Session, tenant_id: UUID) -> None:
        bind = session.get_bind()
        if bind and bind.dialect.name == "postgresql":
            session.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )

    # -- SessionStore port -------------------------------------------------
    def get(self, tenant_id: UUID, patient_id: UUID) -> ConversationSession:
        session = self._session_factory()
        try:
            self._apply_tenant_context(session, tenant_id)
            row = session.execute(
                select(ConversationSessionModel).where(
                    ConversationSessionModel.tenant_id == tenant_id,
                    ConversationSessionModel.patient_id == patient_id,
                )
            ).scalar_one_or_none()
        except Exception:
            session.rollback()
            row = None
        finally:
            session.close()

        if row is None:
            return ConversationSession(tenant_id=tenant_id, patient_id=patient_id)
        try:
            state = ConversationState(row.state)
        except ValueError:
            state = ConversationState.IDLE
        try:
            kind = DraftKind(row.draft_kind)
        except ValueError:
            kind = DraftKind.NONE
        return ConversationSession(
            tenant_id=tenant_id,
            patient_id=patient_id,
            state=state,
            draft_kind=kind,
            draft_fingerprint=row.draft_fingerprint or "",
            context=dict(row.context or {}),
            updated_at=row.updated_at,
        )

    def save(self, conversation: ConversationSession) -> None:
        session = self._session_factory()
        try:
            self._apply_tenant_context(session, conversation.tenant_id)
            row = session.execute(
                select(ConversationSessionModel).where(
                    ConversationSessionModel.tenant_id == conversation.tenant_id,
                    ConversationSessionModel.patient_id == conversation.patient_id,
                )
            ).scalar_one_or_none()
            if row is None:
                row = ConversationSessionModel(
                    tenant_id=conversation.tenant_id,
                    patient_id=conversation.patient_id,
                )
                session.add(row)
            row.state = conversation.state.value
            row.draft_kind = conversation.draft_kind.value
            row.draft_fingerprint = conversation.draft_fingerprint or ""
            row.context = conversation.context or {}
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


__all__ = ["SqlAlchemyConversationSessionStore"]