"""Transactional domain event outbox model (Gate 05).

Guarantees atomic persistence of domain state changes and canonical events
in the same database transaction boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DomainEventOutboxModel(Base):
    """Transactional outbox table for canonical domain events."""

    __tablename__ = "domain_event_outbox"

    event_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    correlation_id: Mapped[UUID | None] = mapped_column(nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_outbox_unpublished", "event_type", "published_at"),
    )
