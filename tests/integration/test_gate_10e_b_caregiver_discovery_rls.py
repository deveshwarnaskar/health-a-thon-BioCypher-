"""Gate 10E-B — caregiver patient discovery on live PostgreSQL + RLS.

Verifies §13 with a REAL PostgreSQL engine (alembic head, including the Gate 08
RLS policies on ``caregiver_relationships``):

1. Caregiver relationship repository tenant scoping (UoW + tenant context).
2. Caregiver discovery query returns ONLY the authenticated tenant's
   authorized patients (identity/tenant derived from context, never client).
3. Database-level RLS on ``caregiver_relationships``:
   - missing tenant context  → 0 rows (fail closed)
   - tenant A context        → only tenant A rows
   - tenant B context        → only tenant B rows
4. Deactivated patient: RLS still exposes the row to its own tenant (the
   exclusion is enforced at the authorization boundary, NOT faked by RLS),
   and the discovery query excludes it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.application.services.list_caregiver_patients import ListCaregiverPatientsHandler
from backend.application.queries import ListCaregiverPatients
from backend.domain.entities import (
    CaregiverRelationship,
    CaregiverRelationshipStatus,
    Patient,
)
from backend.domain.value_objects import UHID
from backend.infrastructure.config.clock import SystemClock
from backend.infrastructure.config.database import create_db_engine
from backend.infrastructure.persistence.models import OrganizationModel
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork

CAREGIVER_ROLE = "thali_app_test_role"


@pytest.fixture(scope="module")
def postgres_gate10e_db():
    import psycopg

    db_name = f"thali_cg10e_{uuid4().hex[:8]}"
    try:
        with psycopg.connect("dbname=postgres", autocommit=True, connect_timeout=1) as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE {db_name};")
    except Exception:
        pytest.skip("Local PostgreSQL not accessible for integration testing")

    pg_url = f"postgresql+psycopg://@localhost:5432/{db_name}"
    engine = create_db_engine(pg_url)

    with engine.connect() as conn:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.attributes["connection"] = conn
        command.upgrade(alembic_cfg, "head")

        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'thali_app_test_role') THEN
                    CREATE ROLE thali_app_test_role WITH NOSUPERUSER NOBYPASSRLS;
                END IF;
            END
            $$;
            GRANT USAGE ON SCHEMA public TO thali_app_test_role;
            GRANT ALL ON ALL TABLES IN SCHEMA public TO thali_app_test_role;
        """))
        conn.commit()

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    yield engine, session_factory

    engine.dispose()
    with psycopg.connect("dbname=postgres", autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE);")


def _seed_rel(
    session_factory,
    tenant_id,
    patient_id,
    caregiver_user_id,
    *,
    status=CaregiverRelationshipStatus.VERIFIED,
    active_patient: bool = True,
):
    now = datetime.now(timezone.utc)
    with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
        uow.patients.add(
            Patient(
                id=patient_id,
                uh_id=UHID(f"UH-{str(patient_id)[:8]}"),
                name=f"Patient-{str(patient_id)[:6]}",
                active=active_patient,
            )
        )
        uow.commit()
    with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
        uow.caregiver_relationships.add(
            CaregiverRelationship(
                patient_id=patient_id,
                caregiver_user_id=caregiver_user_id,
                relationship="test-caregiver",
                status=status,
                capabilities=frozenset(["read_glucose", "read_meal"]),
                verified_at=now,
            )
        )
        uow.commit()


def test_cg10e_rls_relationship_tenant_isolation_and_discovery(postgres_gate10e_db):
    engine, session_factory = postgres_gate10e_db
    tenant_a, tenant_b = uuid4(), uuid4()
    caregiver = uuid4()
    pid_a, pid_b = uuid4(), uuid4()

    with session_factory() as session:
        session.add_all([
            OrganizationModel(id=tenant_a, name="Org A", slug="cg10e-a"),
            OrganizationModel(id=tenant_b, name="Org B", slug="cg10e-b"),
        ])
        session.commit()

    _seed_rel(session_factory, tenant_a, pid_a, caregiver)
    _seed_rel(session_factory, tenant_b, pid_b, caregiver)

    # 1. Repository tenant scoping: same caregiver, isolated by tenant.
    with SqlAlchemyUnitOfWork(session_factory, tenant_a) as uow_a:
        rels_a = uow_a.caregiver_relationships.list_for_caregiver(caregiver)
        assert len(rels_a) == 1
        assert rels_a[0].patient_id == pid_a

    with SqlAlchemyUnitOfWork(session_factory, tenant_b) as uow_b:
        rels_b = uow_b.caregiver_relationships.list_for_caregiver(caregiver)
        assert len(rels_b) == 1
        assert rels_b[0].patient_id == pid_b

    # 2. Discovery query honors context: tenant A discovers ONLY its patient.
    clock = SystemClock()
    with SqlAlchemyUnitOfWork(session_factory, tenant_a) as uow_a:
        result_a = ListCaregiverPatientsHandler(uow_a, clock).handle(
            ListCaregiverPatients(caregiver_user_id=caregiver)
        )
    assert result_a.patient_count == 1
    assert result_a.items[0].patient_id == pid_a

    with SqlAlchemyUnitOfWork(session_factory, tenant_b) as uow_b:
        result_b = ListCaregiverPatientsHandler(uow_b, clock).handle(
            ListCaregiverPatients(caregiver_user_id=caregiver)
        )
    assert result_b.patient_count == 1
    assert result_b.items[0].patient_id == pid_b

    # 3. Database-level RLS on caregiver_relationships via non-superuser role.
    with engine.connect() as conn:
        conn.execute(text(f"SET ROLE {CAREGIVER_ROLE};"))
        try:
            no_ctx = conn.execute(
                text("SELECT count(*) FROM caregiver_relationships")
            ).scalar()
            assert no_ctx == 0, "RLS must fail closed without tenant context"

            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(tenant_a)},
            )
            only_a = conn.execute(
                text("SELECT count(*) FROM caregiver_relationships")
            ).scalar()
            assert only_a == 1, "RLS must return only tenant A rows"

            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(tenant_b)},
            )
            only_b = conn.execute(
                text("SELECT count(*) FROM caregiver_relationships")
            ).scalar()
            assert only_b == 1, "RLS must return only tenant B rows"
        finally:
            conn.execute(text("RESET ROLE;"))


def test_cg10e_rls_deactivated_patient_excluded_by_boundary_not_rls(postgres_gate10e_db):
    """RLS exposes the deactivated patient's row; the authorization boundary excludes it."""
    engine, session_factory = postgres_gate10e_db
    tenant = uuid4()
    caregiver = uuid4()
    pid = uuid4()

    with session_factory() as session:
        session.add(OrganizationModel(id=tenant, name="Org", slug="cg10e-deact"))
        session.commit()

    _seed_rel(session_factory, tenant, pid, caregiver, active_patient=True)
    clock = SystemClock()

    with SqlAlchemyUnitOfWork(session_factory, tenant) as uow:
        result = ListCaregiverPatientsHandler(uow, clock).handle(
            ListCaregiverPatients(caregiver_user_id=caregiver)
        )
    assert result.patient_count == 1

    # Deactivate the patient at the domain boundary.
    with SqlAlchemyUnitOfWork(session_factory, tenant) as uow:
        patient = uow.patients.get(pid)
        patient.deactivate()
        uow.patients.save(patient)
        uow.commit()

    # RLS still permits the tenant to read the deactivated patient's row.
    with engine.connect() as conn:
        conn.execute(text(f"SET ROLE {CAREGIVER_ROLE};"))
        try:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(tenant)},
            )
            visible = conn.execute(
                text("SELECT count(*) FROM patients WHERE id = :pid"),
                {"pid": str(pid)},
            ).scalar()
            assert visible == 1, "deactivated patient row remains visible under RLS"
        finally:
            conn.execute(text("RESET ROLE;"))

    # ...but the discovery query excludes it (active-patient invariant).
    with SqlAlchemyUnitOfWork(session_factory, tenant) as uow:
        result = ListCaregiverPatientsHandler(uow, clock).handle(
            ListCaregiverPatients(caregiver_user_id=caregiver)
        )
    assert result.patient_count == 0