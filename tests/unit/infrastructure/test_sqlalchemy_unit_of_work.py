"""Tests for SqlAlchemyUnitOfWork transaction boundaries (Gate 05).

Verifies:
1. Conformance to the application UnitOfWork protocol.
2. Successful use-case transaction -> commits all repositories.
3. Exception in transaction -> rolls back all staged entities (no partial commits).
4. Session lifecycle management and clean teardown.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.application.commands import IngestGlucoseReading
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services.ingest_glucose import IngestGlucoseHandler
from backend.domain.entities import Patient
from backend.domain.exceptions import EntityNotFound
from backend.domain.value_objects import GlucoseValue, ReadingTag, UHID
from backend.infrastructure.config.clock import SystemClock
from backend.infrastructure.config.id_generator import Uuid4IdGenerator
from backend.infrastructure.persistence.models import (
    Base,
    GlucoseObservationModel,
    OrganizationModel,
    PatientModel,
)
from backend.infrastructure.persistence.uow import (
    SqlAlchemyOutboxDomainEventPublisher,
    SqlAlchemyUnitOfWork,
)


@pytest.fixture
def uow_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    tenant_id = uuid4()
    with session_factory() as init_session:
        init_session.add(
            OrganizationModel(
                id=tenant_id,
                name="Main Hospital",
                slug="main-hospital",
                created_at=datetime.now(timezone.utc),
            )
        )
        init_session.commit()

    def _make_uow():
        return SqlAlchemyUnitOfWork(session_factory, tenant_id)

    yield _make_uow, session_factory, tenant_id

    Base.metadata.drop_all(engine)


def test_sqlalchemy_uow_implements_port_protocol(uow_factory):
    make_uow, _, _ = uow_factory
    uow = make_uow()
    assert isinstance(uow, UnitOfWork)
    uow.close()


def test_sqlalchemy_uow_commit_persists_changes(uow_factory):
    make_uow, session_factory, tenant_id = uow_factory
    uow = make_uow()

    patient_id = uuid4()
    with uow:
        patient = Patient(id=patient_id, uh_id=UHID("UH-01"), name="Test Patient")
        uow.patients.add(patient)
        uow.commit()

    # Verify directly in a new session
    with session_factory() as verify_session:
        stmt = select(PatientModel).where(PatientModel.id == patient_id)
        row = verify_session.scalars(stmt).first()
        assert row is not None
        assert row.name == "Test Patient"


def test_sqlalchemy_uow_rollback_discards_changes(uow_factory):
    make_uow, session_factory, tenant_id = uow_factory
    uow = make_uow()

    patient_id = uuid4()
    with uow:
        patient = Patient(id=patient_id, uh_id=UHID("UH-02"), name="Transient Patient")
        uow.patients.add(patient)
        uow.rollback()

    with session_factory() as verify_session:
        stmt = select(PatientModel).where(PatientModel.id == patient_id)
        row = verify_session.scalars(stmt).first()
        assert row is None


def test_use_case_success_commits_all_repositories(uow_factory):
    make_uow, session_factory, tenant_id = uow_factory
    uow = make_uow()

    # Seed patient first
    patient_id = uuid4()
    with uow:
        uow.patients.add(Patient(id=patient_id, uh_id=UHID("UH-03"), name="Seeded Patient"))
        uow.commit()

    clock = SystemClock()
    id_gen = Uuid4IdGenerator()
    events = SqlAlchemyOutboxDomainEventPublisher(uow.session, tenant_id)
    handler = IngestGlucoseHandler(uow, events, clock, id_gen)

    cmd = IngestGlucoseReading(
        patient_id=patient_id,
        value=GlucoseValue(135),
        taken_at=datetime.now(timezone.utc),
        tag=ReadingTag.FASTING,
    )

    result = handler.handle(cmd)
    assert result.patient_id == patient_id
    assert result.value_mg_dl == 135

    # Verify persistence
    with session_factory() as verify_session:
        stmt = select(GlucoseObservationModel).where(
            GlucoseObservationModel.id == result.observation_id
        )
        obs = verify_session.scalars(stmt).first()
        assert obs is not None
        assert obs.value_mg_dl == 135


def test_use_case_failure_rolls_back_without_partial_commit(uow_factory):
    make_uow, session_factory, tenant_id = uow_factory
    uow = make_uow()

    clock = SystemClock()
    id_gen = Uuid4IdGenerator()
    events = SqlAlchemyOutboxDomainEventPublisher(uow.session, tenant_id)
    handler = IngestGlucoseHandler(uow, events, clock, id_gen)

    # Ingest for non-existent patient (should fail and rollback)
    missing_patient_id = uuid4()
    cmd = IngestGlucoseReading(
        patient_id=missing_patient_id,
        value=GlucoseValue(140),
        taken_at=datetime.now(timezone.utc),
    )

    with pytest.raises(EntityNotFound):
        handler.handle(cmd)

    # Verify no orphan observations were committed
    with session_factory() as verify_session:
        stmt = select(GlucoseObservationModel).where(
            GlucoseObservationModel.patient_id == missing_patient_id
        )
        rows = verify_session.scalars(stmt).all()
        assert rows == []
