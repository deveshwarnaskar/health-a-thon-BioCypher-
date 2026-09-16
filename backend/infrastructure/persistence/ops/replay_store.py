"""SqlAlchemyWebhookReceiptStore (Gate 09 §8).

Relational implementation of the ``WebhookReceiptStore`` port. The provider
message id is the deduplication key: a delivery whose id was recorded within the
retention window is a duplicate (the caller acknowledges it and drops the
payload); an older, stale receipt is refreshed and treated as fresh so a
provider's retransmission outside the window still becomes real work.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.application.ops.contracts import WebhookReceipt
from ..models.ops_models import WebhookReceiptModel

DEFAULT_WEBHOOK_RETENTION_SECONDS = 7 * 24 * 60 * 60


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class SqlAlchemyWebhookReceiptStore:
    """SQLAlchemy-backed provider-replay deduplication store."""

    def __init__(self, session: Session, retention_seconds: int = DEFAULT_WEBHOOK_RETENTION_SECONDS) -> None:
        self.session = session
        self.retention_seconds = retention_seconds

    def record(self, receipt: WebhookReceipt) -> bool:
        now = _utcnow()

        if self._insert_or_nothing(receipt, now):
            return True

        row = self._existing(receipt.provider, receipt.provider_message_id)
        if row is None:
            return True  # concurrent insert elsewhere → treat as fresh

        received_at = _aware(row.received_at) or now
        if now - received_at <= timedelta(seconds=self.retention_seconds):
            return False  # duplicate within the retention window

        # Stale receipt → refresh, treat as a fresh delivery.
        row.received_at = now
        row.status = "received"
        row.source_phone = receipt.source_phone
        return True

    def _insert_or_nothing(self, receipt: WebhookReceipt, now: datetime) -> bool:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        values = {
            "receipt_id": receipt.receipt_id,
            "provider": receipt.provider,
            "provider_message_id": receipt.provider_message_id,
            "event_type": receipt.event_type,
            "source_phone": receipt.source_phone,
            "received_at": now,
            "status": "received",
        }
        dialect = self.session.get_bind().dialect.name
        insert = pg_insert(WebhookReceiptModel) if dialect == "postgresql" else sqlite_insert(WebhookReceiptModel)
        stmt = insert.values(**values).on_conflict_do_nothing(
            index_elements=["provider", "provider_message_id"]
        ).returning(WebhookReceiptModel.receipt_id)
        return self.session.execute(stmt).first() is not None

    def _existing(self, provider: str, provider_message_id: str) -> WebhookReceiptModel | None:
        stmt = select(WebhookReceiptModel).where(
            WebhookReceiptModel.provider == provider,
            WebhookReceiptModel.provider_message_id == provider_message_id,
        )
        return self.session.scalars(stmt).first()


__all__ = ["SqlAlchemyWebhookReceiptStore"]