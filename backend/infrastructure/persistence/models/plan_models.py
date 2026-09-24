"""Clinical plan and task persistence models: MedicationPlan and CareTask (Gate 05).

Tenant-scoped relational models for clinician-authored plans and care team tasks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MedicationPlanModel(Base):
    """Relational model for clinician-authored MedicationPlan."""

    __tablename__ = "medication_plans"

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
    prescribed_by_user_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    prescribed_by_role: Mapped[str] = mapped_column(String(32), nullable=False)
    medication: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    instruction: Mapped[str] = mapped_column(Text, default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_medication_plans_tenant_patient", "tenant_id", "patient_id"),
    )


class CareTaskModel(Base):
    """Relational model for CareTask entity."""

    __tablename__ = "care_tasks"

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
    assigned_to_user_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_care_tasks_tenant_patient", "tenant_id", "patient_id"),
        Index("ix_care_tasks_tenant_assigned", "tenant_id", "assigned_to_user_id"),
        Index("ix_care_tasks_tenant_assigned_status", "tenant_id", "assigned_to_user_id", "status"),
    )
