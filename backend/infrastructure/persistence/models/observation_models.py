"""Observation persistence models: Glucose and Meal observations (Gate 05).

Tenant-scoped relational models for patient observations.
Preserves clinician-only analytics in storage while enforcing timeline indexes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class GlucoseObservationModel(Base):
    """Relational model for GlucoseObservation entity."""

    __tablename__ = "glucose_observations"

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
    taken_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    value_mg_dl: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tag: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confirmation: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_glucose_obs_tenant_patient_taken", "tenant_id", "patient_id", "taken_at"),
    )


class MealObservationModel(Base):
    """Relational model for MealObservation entity."""

    __tablename__ = "meal_observations"

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
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    portion_food_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    portion_volume_ml: Mapped[int | None] = mapped_column(Integer, nullable=True)
    portion_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbs_grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    glycemic_index: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confirmation: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_meal_obs_tenant_patient_recorded", "tenant_id", "patient_id", "recorded_at"),
    )
