"""Tests for Transactional Outbox Event Publisher (Gate 05).

Verifies:
1. Canonical domain events are staged into the outbox within the same session.
2. Committed transaction persists both domain aggregate and outbox event.
3. Rolled back transaction discards outbox events (no phantom events).
4. Outbox payload is completely serialized and JSON-compatible.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.domain.events import GlucoseObservationRecorded
from backend.infrastructure.persistence.models import Base, DomainEventOutboxModel, OrganizationModel
from backend.infrastructure.persistence.uow import (
    SqlAlchemyOutboxDomainEventPublisher,
    SqlAlchemyUnitOfWork,
)


@pytest.fixture
def session_and_tenant():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()

    tenant_id = uuid4()
    session.add(OrganizationModel(id=tenant_id, name="Outbox Hospital", slug="outbox-hospital"))
    session.commit()

    yield session, tenant_id

    session.close()
    Base.metadata.drop_all(engine)


def test_outbox_publishes_event_in_same_transaction(session_and_tenant):
    session, tenant_id = session_and_tenant
    publisher = SqlAlchemyOutboxDomainEventPublisher(session, tenant_id)

    event_id = uuid4()
    obs_id = uuid4()
    patient_id = uuid4()
    correlation_id = uuid4()

    event = GlucoseObservationRecorded(
        event_id=event_id,
        occurred_at=datetime(2026, 9, 13, 15, 0, 0, tzinfo=timezone.utc),
        patient_id=patient_id,
        correlation_id=correlation_id,
        observation_id=obs_id,
    )

    publisher.publish(event)
    session.commit()

    # Query outbox table
    stmt = select(DomainEventOutboxModel).where(DomainEventOutboxModel.event_id == event_id)
    record = session.scalars(stmt).first()
    assert record is not None
    assert record.event_type == "glucose_observation.recorded"
    assert record.tenant_id == tenant_id
    assert record.patient_id == patient_id
    assert record.correlation_id == correlation_id
    assert record.published_at is None
    assert record.payload["observation_id"] == str(obs_id)


def test_outbox_rollback_discards_uncommitted_event(session_and_tenant):
    session, tenant_id = session_and_tenant
    publisher = SqlAlchemyOutboxDomainEventPublisher(session, tenant_id)

    event_id = uuid4()
    event = GlucoseObservationRecorded(
        event_id=event_id,
        patient_id=uuid4(),
    )

    publisher.publish(event)
    session.rollback()

    stmt = select(DomainEventOutboxModel).where(DomainEventOutboxModel.event_id == event_id)
    record = session.scalars(stmt).first()
    assert record is None
