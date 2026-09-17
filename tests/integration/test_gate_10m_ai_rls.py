"""Gate 10M — AI Review Artifacts Row Level Security (RLS) on PostgreSQL.

Verifies:
1. Migration 0007 upgrades cleanly to head.
2. Tenant isolation policy on ai_review_artifacts:
   - Missing tenant context -> 0 rows (fail closed)
   - Tenant A context -> only Tenant A artifacts visible
   - Tenant B context -> only Tenant B artifacts visible
3. Cross-tenant insert/select denied at the database engine level by PostgreSQL RLS.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.domain.entities import AIReviewArtifact, ReviewAuthority, ReviewState
from backend.infrastructure.config.database import create_db_engine
from backend.infrastructure.persistence.models import OrganizationModel
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork

APP_TEST_ROLE = "thali_app_test_role"


@pytest.fixture(scope="module")
def postgres_gate10m_db():
    import psycopg

    db_name = f"thali_airls10m_{uuid4().hex[:8]}"
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


class TestAIArtifactsRLSPostgres:
    def test_ai_artifacts_rls_tenant_isolation(self, postgres_gate10m_db):
        engine = create_db_engine(postgres_gate10m_db)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        tenant_a = uuid4()
        tenant_b = uuid4()
        patient_a = uuid4()
        patient_b = uuid4()

        from backend.infrastructure.persistence.models.patient_models import PatientModel

        with session_factory() as s:
            s.add(OrganizationModel(id=tenant_a, name="Tenant A", slug="tenant-a"))
            s.add(OrganizationModel(id=tenant_b, name="Tenant B", slug="tenant-b"))
            s.commit()

        with session_factory() as s:
            s.add(PatientModel(id=patient_a, tenant_id=tenant_a, uh_id="UHID-A", name="Patient A"))
            s.add(PatientModel(id=patient_b, tenant_id=tenant_b, uh_id="UHID-B", name="Patient B"))
            s.commit()

        # Seed AI artifact in Tenant A and Tenant B using SqlAlchemyUnitOfWork
        art_a_id = uuid4()
        art_b_id = uuid4()

        with SqlAlchemyUnitOfWork(session_factory, tenant_a) as uow_a:
            uow_a.ai_artifacts.add(
                AIReviewArtifact(
                    id=art_a_id,
                    tenant_id=tenant_a,
                    patient_id=patient_a,
                    artifact_kind="clinical_summary",
                    authority=ReviewAuthority.CLINICIAN_REVIEW,
                    state=ReviewState.PENDING_REVIEW,
                    generated_by="ai:demo",
                    summary="Tenant A summary",
                    model_name="demo-v1",
                    evidence_hash="hash-a",
                )
            )
            uow_a.commit()

        with SqlAlchemyUnitOfWork(session_factory, tenant_b) as uow_b:
            uow_b.ai_artifacts.add(
                AIReviewArtifact(
                    id=art_b_id,
                    tenant_id=tenant_b,
                    patient_id=patient_b,
                    artifact_kind="clinical_summary",
                    authority=ReviewAuthority.CLINICIAN_REVIEW,
                    state=ReviewState.PENDING_REVIEW,
                    generated_by="ai:demo",
                    summary="Tenant B summary",
                    model_name="demo-v1",
                    evidence_hash="hash-b",
                )
            )
            uow_b.commit()

        # Direct queries under unprivileged role thali_app_test_role
        with session_factory() as s:
            s.execute(text(f"SET ROLE {APP_TEST_ROLE}"))

            # 1. Unset tenant context -> 0 rows
            s.execute(text("SELECT set_config('app.current_tenant_id', '', true)"))
            rows_none = s.execute(text("SELECT id FROM ai_review_artifacts")).fetchall()
            assert len(rows_none) == 0

            # 2. Under Tenant A context -> only Tenant A row visible
            s.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_a)})
            rows_a = s.execute(text("SELECT id, summary, model_name FROM ai_review_artifacts")).fetchall()
            assert len(rows_a) == 1
            assert rows_a[0][0] == art_a_id
            assert rows_a[0][1] == "Tenant A summary"
            assert rows_a[0][2] == "demo-v1"

            # 3. Under Tenant B context -> only Tenant B row visible
            s.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_b)})
            rows_b = s.execute(text("SELECT id, summary, model_name FROM ai_review_artifacts")).fetchall()
            assert len(rows_b) == 1
            assert rows_b[0][0] == art_b_id
            assert rows_b[0][1] == "Tenant B summary"

            # 4. Attempt cross-tenant insert (WITH CHECK violation)
            s.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_a)})
            with pytest.raises(Exception):
                s.execute(
                    text(
                        "INSERT INTO ai_review_artifacts (id, tenant_id, patient_id, artifact_kind, "
                        "authority, state, generated_by, summary, created_at) "
                        "VALUES (:id, :tid, :pid, 'clinical_summary', 'clinician_review', 'generated', 'ai', 'spoof', NOW())"
                    ),
                    {"id": str(uuid4()), "tid": str(tenant_b), "pid": str(patient_a)},
                )
            s.rollback()
