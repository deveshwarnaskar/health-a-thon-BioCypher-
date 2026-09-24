"""Conversation persistence models (spec §5 / §20).

Maps the conversational layer's tenant-scoped session pointer and the
per-patient channel preferences to relational tables. Both are protected by
PostgreSQL Row-Level Security (migration 0012).

No PHI is stored on the session row — only state, draft kind and a
fingerprint pointing at the draft (already persisted by its domain handler).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.application.ops.conversation.state import ConversationState, DraftKind

from .base import Base


class ConversationSessionModel(Base):
    """Durable pointer to the §5 state machine for one (tenant, patient)."""

    __tablename__ = "whatsapp_conversation_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=ConversationState.IDLE.value,
        server_default=ConversationState.IDLE.value,
    )
    draft_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DraftKind.NONE.value,
        server_default=DraftKind.NONE.value,
    )
    draft_fingerprint: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
        server_default="",
    )
    context: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "patient_id",
            name="uq_conversation_sessions_tenant_patient",
        ),
        Index("ix_conversation_sessions_tenant_state", "tenant_id", "state"),
        Index("ix_conversation_sessions_patient", "tenant_id", "patient_id"),
    )


class PatientChannelPrefModel(Base):
    """Per-patient, per-channel preferences (language + reminder quiet hours)."""

    __tablename__ = "patient_channel_prefs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="WHATSAPP",
        server_default="WHATSAPP",
    )
    preferred_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    last_reminder_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "patient_id",
            "channel",
            name="uq_patient_channel_prefs_patient_channel",
        ),
        Index("ix_patient_channel_prefs_tenant_channel", "tenant_id", "channel"),
    )


__all__ = ["ConversationSessionModel", "PatientChannelPrefModel"]
