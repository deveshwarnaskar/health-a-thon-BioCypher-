"""SqlAlchemyNotificationRepository (Gate 10L).

Concrete infrastructure implementation of NotificationRepository port.
Enforces multi-tenant scoping and persists notification state transitions.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.domain.entities import Notification, NotificationStatus
from backend.domain.exceptions import EntityNotFound
from ..mappings.mappers import notification_to_domain, notification_to_model
from ..models.notification_models import NotificationModel


class SqlAlchemyNotificationRepository:
    """SQLAlchemy-backed repository for Notification entities."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyNotificationRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, notification: Notification) -> None:
        model = notification_to_model(notification, self.tenant_id)
        self.session.add(model)

    def get(self, notification_id: UUID) -> Notification:
        stmt = select(NotificationModel).where(
            NotificationModel.id == notification_id,
            NotificationModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"notification {notification_id} not found")
        return notification_to_domain(model)

    def save(self, notification: Notification) -> None:
        stmt = select(NotificationModel).where(
            NotificationModel.id == notification.id,
            NotificationModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"notification {notification.id} not found")
        model.status = notification.status.value if hasattr(notification.status, "value") else str(notification.status)
        model.delivered_at = notification.delivered_at
        model.failed_at = notification.failed_at
        model.failure_reason = notification.failure_reason
        model.retry_count = notification.retry_count
        model.scheduled_at = notification.scheduled_at

    def list_for_recipient(
        self, recipient_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[Notification]:
        stmt = (
            select(NotificationModel)
            .where(
                NotificationModel.tenant_id == self.tenant_id,
                NotificationModel.recipient_id == recipient_id,
            )
            .order_by(NotificationModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [notification_to_domain(m) for m in self.session.scalars(stmt).all()]

    def list_for_patient(
        self, patient_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[Notification]:
        stmt = (
            select(NotificationModel)
            .where(
                NotificationModel.tenant_id == self.tenant_id,
                NotificationModel.patient_id == patient_id,
            )
            .order_by(NotificationModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [notification_to_domain(m) for m in self.session.scalars(stmt).all()]

    def list_due(self, before: datetime, limit: int = 50) -> list[Notification]:
        stmt = (
            select(NotificationModel)
            .where(
                NotificationModel.tenant_id == self.tenant_id,
                NotificationModel.status == NotificationStatus.PENDING.value,
                NotificationModel.scheduled_at <= before,
            )
            .order_by(NotificationModel.scheduled_at.asc())
            .limit(limit)
        )
        return [notification_to_domain(m) for m in self.session.scalars(stmt).all()]

    def list_for_tenant(
        self, status: NotificationStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[Notification]:
        stmt = select(NotificationModel).where(NotificationModel.tenant_id == self.tenant_id)
        if status is not None:
            status_val = status.value if hasattr(status, "value") else str(status)
            stmt = stmt.where(NotificationModel.status == status_val)
        stmt = stmt.order_by(NotificationModel.created_at.desc()).limit(limit).offset(offset)
        return [notification_to_domain(m) for m in self.session.scalars(stmt).all()]

    def count_for_tenant(self, status: NotificationStatus | None = None) -> int:
        stmt = (
            select(func.count())
            .select_from(NotificationModel)
            .where(NotificationModel.tenant_id == self.tenant_id)
        )
        if status is not None:
            status_val = status.value if hasattr(status, "value") else str(status)
            stmt = stmt.where(NotificationModel.status == status_val)
        return int(self.session.scalar(stmt) or 0)
