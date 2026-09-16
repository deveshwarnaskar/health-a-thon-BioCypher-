"""Gate 09 operational resiliency models.

- ``IdempotencyRecordModel``  — client idempotency reservations
- ``WebhookReceiptModel``     — provider delivery deduplication
- ``AuditEventModel``         — append-only compliance trail

The audit table intentionally carries NO update/delete capability: mutation is
revoked at the database layer and blocked by the ``prevent_audit_mutation``
trigger created in migration 0003. PHI is prohibited from every column
description that follows; these tables are metadata and identities only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IdempotencyRecordModel(Base):
    """One scoped idempotency reservation (tenant ‖ actor ‖ key)."""

    __tablename__ = "idempotency_records"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[UUID] = mapped_column(nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="in_progress",
    )
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "actor_id", "idempotency_key", name="uq_idempotency_scope"
        ),
        Index("ix_idempotency_exploration", "expires_at"),
    )


class WebhookReceiptModel(Base):
    """Deduplication receipt for one verified provider delivery (Gate 09 §8).

    No tenant column by design: the receipt is a global, provider-keyed
    deduplication ledger surfaced before the payload is routed to a tenant.
    RLS does not apply to this table.
    """

    __tablename__ = "webhook_receipts"

    receipt_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    source_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="received",
        server_default="received",
    )

    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_message_id", name="uq_webhook_receipt_provider_msg"
        ),
        Index("ix_webhook_receipt_received", "received_at"),
    )


class AuditEventModel(Base):
    """Append-only compliance record (Gate 09 §10).

    Columns are PHI-minimal by contract: no clinical values, addresses,
    passwords, tokens, or raw channel payloads may ever be written here.
    """

    __tablename__ = "audit_events"

    audit_event_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[UUID] = mapped_column(nullable=False)
    actor_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="SYSTEM_WORKER",
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="SUCCESS")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_metadata: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )

    __table_args__ = (
        Index("ix_audit_tenant_occurred", "tenant_id", "occurred_at"),
    )