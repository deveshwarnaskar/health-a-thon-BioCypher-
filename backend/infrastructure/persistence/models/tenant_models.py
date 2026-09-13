"""Multi-tenancy models: Organizations and Facilities (Gate 05).

Provides the physical root for organizational tenancy and facilities.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class OrganizationModel(Base):
    """Authoritative tenant organization root."""

    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    facilities: Mapped[list[FacilityModel]] = relationship(
        "FacilityModel", back_populates="organization", cascade="all, delete-orphan"
    )


class FacilityModel(Base):
    """Clinical facility belonging to an organization."""

    __tablename__ = "facilities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    organization: Mapped[OrganizationModel] = relationship(
        "OrganizationModel", back_populates="facilities"
    )
