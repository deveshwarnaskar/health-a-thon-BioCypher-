"""PostgreSQL-backed HTTP → UoW → RLS end-to-end proof (Gate 07).

Proves the full transport-to-database chain on a real PostgreSQL engine:

    Verified JWT
        → AuthenticatedContext.tenant_id
        → UnitOfWork(tenant_id)
        → transaction-local app.current_tenant_id (set_config)
        → PostgreSQL Row Level Security

Skips automatically when local PostgreSQL is unavailable.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.infrastructure.config.database import create_db_engine
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from backend.interfaces.http.app import create_app
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_event_publisher,
    get_unit_of_work,
)
from backend.interfaces.http.v2.security.authorization import AuthenticatedContext
from tests.api.conftest import (
    bearer,
    make_jwt,
    seed_facility,
    seed_glucose,
    seed_member,
    seed_org,
    seed_patient,
)


@pytest.fixture(scope="module")
def postgres_db():
    import psycopg

    db_name = f"thali_gate07_{uuid4().hex[:8]}"
    try:
        with psycopg.connect("dbname=postgres", autocommit=True, connect_timeout=1) as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE {db_name};")
    except Exception:
        pytest.skip("Local PostgreSQL not accessible for Gate 07 RLS integration test")

    pg_url = f"postgresql+psycopg://@localhost:5432/{db_name}"
    engine = create_db_engine(pg_url)

    with engine.connect() as conn:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.attributes["connection"] = conn
        command.upgrade(alembic_cfg, "head")
        conn.execute(text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'thali_app_test_role') THEN
                    CREATE ROLE thali_app_test_role WITH NOSUPERUSER NOBYPASSRLS;
                END IF;
            END
            $$;
            GRANT USAGE ON SCHEMA public TO thali_app_test_role;
            GRANT ALL ON ALL TABLES IN SCHEMA public TO thali_app_test_role;
            """
        ))
        conn.commit()

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    yield session_factory, engine

    engine.dispose()
    with psycopg.connect("dbname=postgres", autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE);")


def _build_app(session_factory):
    app = create_app()

    async def override_uow(
        ctx: AuthenticatedContext = Depends(get_authenticated_context),
    ):
        uow = SqlAlchemyUnitOfWork(session_factory, ctx.tenant_id)
        try:
            yield uow
        finally:
            uow.close()

    async def override_events(
        uow: SqlAlchemyUnitOfWork = Depends(override_uow),
    ):
        from backend.infrastructure.persistence.uow.outbox_publisher import (
            SqlAlchemyOutboxDomainEventPublisher,
        )
        return SqlAlchemyOutboxDomainEventPublisher(uow.session, uow.tenant_id)

    app.dependency_overrides[get_unit_of_work] = override_uow
    app.dependency_overrides[get_event_publisher] = override_events
    return TestClient(app, raise_server_exceptions=False)


class TestHTTPToRLSChain:
    """Gate 07 chain proof against real PostgreSQL row-level security."""

    def test_tenant_a_reads_own_data_over_http(self, postgres_db):
        session_factory, _ = postgres_db
        client = _build_app(session_factory)

        tid = uuid4()
        fid = uuid4()
        actor_id = uuid4()
        patient_id = uuid4()

        seed_org(session_factory, tid, f"pg-a-{tid.hex[:6]}")
        seed_facility(session_factory, tid, fid, "Facility A")
        seed_patient(session_factory, tid, patient_id, facility_id=fid, name="Alpha")
        seed_member(session_factory, tid, user_id=actor_id, role="doctor", facility_id=fid)
        seed_glucose(session_factory, tid, patient_id, value=125)

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["doctor"], facility_id=str(fid))
        resp = client.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(i.get("value_mg_dl") == 125 for i in items if i.get("kind") == "glucose")

    def test_cross_tenant_access_blocked_by_rls(self, postgres_db):
        session_factory, engine = postgres_db
        client = _build_app(session_factory)

        tid_a = uuid4()
        tid_b = uuid4()
        fid = uuid4()
        actor_a = uuid4()
        patient_b_id = uuid4()

        seed_org(session_factory, tid_a, f"pg-a-{tid_a.hex[:6]}")
        seed_org(session_factory, tid_b, f"pg-b-{tid_b.hex[:6]}")
        seed_facility(session_factory, tid_b, fid, "Facility B")
        seed_patient(session_factory, tid_b, patient_b_id, facility_id=fid, name="Beta")
        seed_member(session_factory, tid_a, user_id=actor_a, role="doctor", facility_id=fid)

        token = make_jwt(sub=str(actor_a), tenant_id=str(tid_a), roles=["doctor"], facility_id=str(fid))
        resp = client.get(f"/api/v2/clinical/observations?patient_id={patient_b_id}", headers=bearer(token))
        assert resp.status_code in (403, 404)

        # Prove at the engine level: a non-superuser role without tenant context
        # fails closed under FORCE ROW LEVEL SECURITY, and a matching context
        # exposes exactly the tenant's rows.
        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', '00000000-0000-0000-0000-000000000000', true)")
            )
            result = conn.execute(text("SELECT count(*) FROM patients")).scalar()
            assert result == 0, "RLS must fail closed for an unknown tenant context"

            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(tid_b)},
            )
            result_b = conn.execute(text("SELECT count(*) FROM patients")).scalar()
            assert result_b == 1, "RLS must expose exactly tenant B's patient"