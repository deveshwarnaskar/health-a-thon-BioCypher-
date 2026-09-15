"""Relational identity models: caregiver relationships + identity mappings (Gate 08).

Maps the pure domain relationships/mappings to tenant-scoped relational tables.
Both tables are RLS-protected multi-tenant rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CaregiverRelationshipModel(Base):
    """Relational model for CaregiverRelationship entity."""

    __tablename__ = "caregiver_relationships"

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
    caregiver_user_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    relationship_label: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    capabilities: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # One non-revoked relationship per (tenant, patient, caregiver) pair.
    # A revoked relationship does not block a fresh one.
    __table_args__ = (
        Index(
            "uq_caregiver_relationships_tenant_pair",
            "tenant_id",
            "patient_id",
            "caregiver_user_id",
            unique=True,
            postgresql_where=text("status != 'revoked'"),
            sqlite_where=text("status != 'revoked'"),
        ),
        Index(
            "ix_caregiver_relationships_tenant_caregiver",
            "tenant_id",
            "caregiver_user_id",
        ),
        Index(
            "ix_caregiver_relationships_tenant_patient",
            "tenant_id",
            "patient_id",
        ),
    )


class IdentityPatientMappingModel(Base):
    """Relational model for IdentityPatientMapping entity."""

    __tablename__ = "identity_patient_mappings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Active mappings are 1:1 in both directions: a user binds to at most one
    # patient and a patient binds to at most one user. Deactivated rows may
    # accumulate for auditability without blocking a fresh active mapping.
    __table_args__ = (
        Index(
            "uq_identity_mappings_tenant_user",
            "tenant_id",
            "user_id",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active"),
        ),
        Index(
            "uq_identity_mappings_tenant_patient",
            "tenant_id",
            "patient_id",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active"),
        ),
    )