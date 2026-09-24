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

import base64
import time
from uuid import uuid4

import jwt as pyjwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
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
    reset_config_cache,
)
from backend.interfaces.http.v2.security import jwks as jwks_module
from backend.interfaces.http.v2.security.authorization import AuthenticatedContext
from tests.api.conftest import (
    TEST_CLIENT_ID,
    TEST_ISSUER,
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


# ─────────────────────────────────────────────────────────────────────────────
# Gate 10C-R: RS256 (Keycloak JWKS) → HTTP → UoW → PostgreSQL RLS
# ─────────────────────────────────────────────────────────────────────────────

RSA_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
RSA_PUBLIC = RSA_PRIVATE.public_key()
RS256_KID = "pg-rs256-kid"
RS256_JWKS_URL = "https://pg-rs256.example/jwks"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_jwk() -> dict:
    nums = RSA_PUBLIC.public_numbers()
    n_bytes = nums.n.to_bytes((nums.n.bit_length() + 7) // 8, "big")
    e_bytes = nums.e.to_bytes((nums.e.bit_length() + 7) // 8, "big")
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": RS256_KID,
        "n": _b64url(n_bytes),
        "e": _b64url(e_bytes),
    }


def _rs256_token(*, sub, tenant_id, roles=None, facility_id=None, private_key=None):
    payload: dict = {
        "iss": TEST_ISSUER,
        "aud": TEST_CLIENT_ID,
        "sub": str(sub),
        "tenant_id": str(tenant_id),
        "exp": int(time.time()) + 3600,
    }
    if roles:
        payload["realm_access"] = {"roles": roles}
    if facility_id:
        payload["facility_id"] = str(facility_id)
    return pyjwt.encode(payload, private_key or RSA_PRIVATE, algorithm="RS256", headers={"kid": RS256_KID})


@pytest.fixture
def rs256_policy(monkeypatch):
    """RS256-only trust boundary with a deterministic fake JWKS endpoint."""
    monkeypatch.setenv("THALI_IDENTITY__ALLOWED_ALGORITHMS", "RS256")
    monkeypatch.setenv("THALI_IDENTITY__JWKS_URI", RS256_JWKS_URL)
    reset_config_cache()

    async def fake_fetch(url: str):
        return {"keys": [_make_jwk()]}

    monkeypatch.setattr(jwks_module, "fetch_json", fake_fetch)
    reset_config_cache()
    yield fake_fetch
    reset_config_cache()


class TestHTTPToRLSChainRs256:
    """Gate 10C-R RS256 chain proof against real PostgreSQL RLS."""

    def test_rs256_tenant_reads_own_data_over_http(self, postgres_db, rs256_policy):
        session_factory, _ = postgres_db
        client = _build_app(session_factory)

        tid = uuid4()
        fid = uuid4()
        actor_id = uuid4()
        patient_id = uuid4()

        seed_org(session_factory, tid, f"pg-rs256-a-{tid.hex[:6]}")
        seed_facility(session_factory, tid, fid, "Facility A")
        seed_patient(session_factory, tid, patient_id, facility_id=fid, name="Alpha")
        seed_member(session_factory, tid, user_id=actor_id, role="doctor", facility_id=fid)
        seed_glucose(session_factory, tid, patient_id, value=125)

        token = _rs256_token(sub=actor_id, tenant_id=tid, roles=["doctor"], facility_id=fid)
        resp = client.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(i.get("value_mg_dl") == 125 for i in items if i.get("kind") == "glucose")

    def test_rs256_cross_tenant_blocked_by_rls(self, postgres_db, rs256_policy):
        session_factory, _ = postgres_db
        client = _build_app(session_factory)

        tid_a = uuid4()
        tid_b = uuid4()
        fid = uuid4()
        actor_a = uuid4()
        patient_b_id = uuid4()

        seed_org(session_factory, tid_a, f"pg-rs256-a-{tid_a.hex[:6]}")
        seed_org(session_factory, tid_b, f"pg-rs256-b-{tid_b.hex[:6]}")
        seed_facility(session_factory, tid_b, fid, "Facility B")
        seed_patient(session_factory, tid_b, patient_b_id, facility_id=fid, name="Beta")
        seed_member(session_factory, tid_a, user_id=actor_a, role="doctor", facility_id=fid)

        token = _rs256_token(sub=actor_a, tenant_id=tid_a, roles=["doctor"], facility_id=fid)
        resp = client.get(f"/api/v2/clinical/observations?patient_id={patient_b_id}", headers=bearer(token))
        assert resp.status_code in (403, 404)

    def test_rs256_bad_signature_rejected_before_touching_rls(self, rs256_policy):
        """An RS256 token signed by an unknown key must never reach the DB."""
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        client = TestClient(create_app(), raise_server_exceptions=False)

        tid = uuid4()
        actor_id = uuid4()
        token = _rs256_token(sub=actor_id, tenant_id=tid, roles=["admin"], private_key=other)
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401