"""AI Review Artifact persistence model (Gate 05).

Tenant-scoped relational model for AI-generated artifacts requiring human clinical review.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AIReviewArtifactModel(Base):
    """Relational model for AIReviewArtifact entity."""

    __tablename__ = "ai_review_artifacts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_kind: Mapped[str] = mapped_column(
        String(64),
        default="extracted_observation",
        nullable=False,
    )
    authority: Mapped[str] = mapped_column(
        String(32),
        default="clinician_review",
        nullable=False,
    )
    state: Mapped[str] = mapped_column(
        String(32),
        default="generated",
        nullable=False,
    )
    generated_by: Mapped[str] = mapped_column(
        String(64),
        default="ai",
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    original_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evidence_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_ai_artifacts_tenant_patient", "tenant_id", "patient_id"),
        Index("ix_ai_artifacts_tenant_state", "tenant_id", "state"),
    )
