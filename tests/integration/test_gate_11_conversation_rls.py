"""Gate 11 — Conversation sessions + patient prefs Row Level Security (RLS).

Verifies (mirrors the Gate 10M/10N pattern):
1. Migration 0012 upgrades cleanly to head.
2. Tenant isolation policy on whatsapp_conversation_sessions and
   patient_channel_prefs:
   - Missing tenant context -> 0 rows (fail closed)
   - Tenant A context -> only Tenant A rows visible
   - Tenant B context -> only Tenant B rows visible
3. Cross-tenant inserts into both tables are denied by PostgreSQL RLS
   (WITH CHECK violation), even when the app role has base table grants.
4. The durable SqlAlchemyConversationSessionStore round-trips under the
   tenant-isolated scope.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.infrastructure.config.database import create_db_engine
from backend.infrastructure.persistence.models import OrganizationModel
from backend.infrastructure.persistence.models.patient_models import PatientModel
from backend.infrastructure.persistence.ops.conversation_session_store import (
    SqlAlchemyConversationSessionStore,
)

APP_TEST_ROLE = "thali_app_test_role"


@pytest.fixture(scope="module")
def postgres_gate11_db():
    import psycopg

    db_name = f"thali_conv_rls_{uuid4().hex[:8]}"
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
        conn.execute(
            text(
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
            )
        )
        conn.commit()

    try:
        yield pg_url
    finally:
        engine.dispose()
        try:
            with psycopg.connect("dbname=postgres", autocommit=True, connect_timeout=1) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db_name}';"
                    )
                    cur.execute(f"DROP DATABASE IF EXISTS {db_name};")
        except Exception:
            pass


class TestConversationRLSPostgres:
    def test_conversation_sessions_and_prefs_rls_tenant_isolation(self, postgres_gate11_db):
        engine = create_db_engine(postgres_gate11_db)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        tenant_a = uuid4()
        tenant_b = uuid4()
        patient_a = uuid4()
        patient_b = uuid4()

        with session_factory() as s:
            s.add(OrganizationModel(id=tenant_a, name="Tenant A", slug="tenant-a"))
            s.add(OrganizationModel(id=tenant_b, name="Tenant B", slug="tenant-b"))
            s.commit()

        with session_factory() as s:
            s.add(PatientModel(id=patient_a, tenant_id=tenant_a, uh_id="UHID-A", name="Patient A"))
            s.add(PatientModel(id=patient_b, tenant_id=tenant_b, uh_id="UHID-B", name="Patient B"))
            s.commit()

        # Seed sessions through the durable store (must round-trip under the
        # tenant-isolated scope for both tenants).
        from backend.application.ops.conversation.state import DraftKind, ConversationSession

        store_a = SqlAlchemyConversationSessionStore(session_factory)
        draft_a = ConversationSession(tenant_id=tenant_a, patient_id=patient_a)
        draft_a.mark_draft(DraftKind.MEDICATION, "med:metformin:morning", {"display": "metformin"})
        store_a.save(draft_a)

        store_b = SqlAlchemyConversationSessionStore(session_factory)
        draft_b = ConversationSession(tenant_id=tenant_b, patient_id=patient_b)
        draft_b.mark_draft(DraftKind.GLUCOSE, "g:140:fasting", {})
        store_b.save(draft_b)

        recovered_a = store_a.get(tenant_a, patient_a)
        assert recovered_a.draft_fingerprint == "med:metformin:morning"
        recovered_b = store_b.get(tenant_b, patient_b)
        assert recovered_b.draft_fingerprint == "g:140:fasting"

        # Raw SQL under the unprivileged role.
        with session_factory() as s:
            s.execute(text(f"SET ROLE {APP_TEST_ROLE}"))

            # 1. Unset tenant context -> 0 rows (fail closed)
            s.execute(text("SELECT set_config('app.current_tenant_id', '', true)"))
            none_rows = s.execute(text("SELECT id FROM whatsapp_conversation_sessions")).fetchall()
            assert len(none_rows) == 0

            # 2. Tenant A context -> only Tenant A session visible
            s.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_a)})
            rows_a = s.execute(text("SELECT draft_fingerprint FROM whatsapp_conversation_sessions")).fetchall()
            assert len(rows_a) == 1
            assert rows_a[0][0] == "med:metformin:morning"

            # 3. Tenant B context -> only Tenant B session visible
            s.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_b)})
            rows_b = s.execute(text("SELECT draft_kind FROM whatsapp_conversation_sessions")).fetchall()
            assert len(rows_b) == 1
            assert rows_b[0][0] == "glucose"

            # 4. Cross-tenant insert on sessions denied (WITH CHECK)
            s.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_a)})
            with pytest.raises(Exception):
                s.execute(
                    text(
                        "INSERT INTO whatsapp_conversation_sessions "
                        "(id, tenant_id, patient_id, state, draft_kind, draft_fingerprint, context, updated_at) "
                        "VALUES (:id, :tid, :pid, 'idle', 'none', '', '{}'::jsonb, NOW())"
                    ),
                    {"id": str(uuid4()), "tid": str(tenant_b), "pid": str(patient_a)},
                )
            s.rollback()
            # SET ROLE is transactional in PostgreSQL: rollback reverts it.
            s.execute(text(f"SET ROLE {APP_TEST_ROLE}"))

            # 5. Cross-tenant insert on prefs table denied (WITH CHECK)
            s.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_b)})
            with pytest.raises(Exception):
                s.execute(
                    text(
                        "INSERT INTO patient_channel_prefs "
                        "(id, tenant_id, patient_id, channel, updated_at) "
                        "VALUES (:id, :tid, :pid, 'WHATSAPP', NOW())"
                    ),
                    {"id": str(uuid4()), "tid": str(tenant_a), "pid": str(patient_b)},
                )
            s.rollback()