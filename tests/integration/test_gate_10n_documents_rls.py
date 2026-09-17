"""Gate 10N — Document References Row Level Security (RLS) on PostgreSQL.

Verifies:
1. Migration 0008 upgrades cleanly to head.
2. Tenant isolation policy on document_references:
   - Missing tenant context -> 0 rows (fail closed)
   - Tenant A context -> only Tenant A document references visible
   - Tenant B context -> only Tenant B document references visible
3. Cross-tenant insert/mutation rejected at the database engine level by PostgreSQL RLS.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.domain.entities import DocumentKind, DocumentReference
from backend.infrastructure.config.database import create_db_engine
from backend.infrastructure.persistence.models import OrganizationModel
from backend.infrastructure.persistence.models.patient_models import PatientModel
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork

APP_TEST_ROLE = "thali_app_test_role"


@pytest.fixture(scope="module")
def postgres_gate10n_db():
    import psycopg

    db_name = f"thali_docrls10n_{uuid4().hex[:8]}"
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


class TestDocumentReferencesRLSPostgres:
    def test_document_references_rls_tenant_isolation(self, postgres_gate10n_db):
        engine = create_db_engine(postgres_gate10n_db)
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

        # Seed DocumentReference in Tenant A and Tenant B using SqlAlchemyUnitOfWork
        doc_a_id = uuid4()
        doc_b_id = uuid4()

        with SqlAlchemyUnitOfWork(session_factory, tenant_a) as uow_a:
            uow_a.document_references.add(
                DocumentReference(
                    id=doc_a_id,
                    tenant_id=tenant_a,
                    patient_id=patient_a,
                    kind=DocumentKind.CLINICAL_REPORT,
                    storage_key=f"tenants/{tenant_a}/patients/{patient_a}/clinical_report/{doc_a_id}.pdf",
                    mime_type="application/pdf",
                    filename="report_a.pdf",
                    file_size_bytes=1024,
                )
            )
            uow_a.commit()

        with SqlAlchemyUnitOfWork(session_factory, tenant_b) as uow_b:
            uow_b.document_references.add(
                DocumentReference(
                    id=doc_b_id,
                    tenant_id=tenant_b,
                    patient_id=patient_b,
                    kind=DocumentKind.PATIENT_SUMMARY,
                    storage_key=f"tenants/{tenant_b}/patients/{patient_b}/patient_summary/{doc_b_id}.pdf",
                    mime_type="application/pdf",
                    filename="report_b.pdf",
                    file_size_bytes=2048,
                )
            )
            uow_b.commit()

        # Direct queries under unprivileged role thali_app_test_role
        with session_factory() as s:
            s.execute(text(f"SET ROLE {APP_TEST_ROLE}"))

            # 1. Unset tenant context -> 0 rows (fail closed)
            s.execute(text("SELECT set_config('app.current_tenant_id', '', true)"))
            rows_none = s.execute(text("SELECT id FROM document_references")).fetchall()
            assert len(rows_none) == 0

            # 2. Under Tenant A context -> only Tenant A row visible
            s.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_a)})
            rows_a = s.execute(text("SELECT id, filename, mime_type FROM document_references")).fetchall()
            assert len(rows_a) == 1
            assert rows_a[0][0] == doc_a_id
            assert rows_a[0][1] == "report_a.pdf"
            assert rows_a[0][2] == "application/pdf"

            # 3. Under Tenant B context -> only Tenant B row visible
            s.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_b)})
            rows_b = s.execute(text("SELECT id, filename, mime_type FROM document_references")).fetchall()
            assert len(rows_b) == 1
            assert rows_b[0][0] == doc_b_id
            assert rows_b[0][1] == "report_b.pdf"
            assert rows_b[0][2] == "application/pdf"

            # 4. Attempt cross-tenant insert (WITH CHECK violation)
            s.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_a)})
            with pytest.raises(Exception):
                s.execute(
                    text(
                        "INSERT INTO document_references (id, tenant_id, patient_id, kind, "
                        "storage_key, mime_type, filename, file_size_bytes, created_at) "
                        "VALUES (:id, :tid, :pid, 'clinical_report', 'key1', 'application/pdf', 'f.pdf', 100, NOW())"
                    ),
                    {"id": str(uuid4()), "tid": str(tenant_b), "pid": str(patient_a)},
                )
            s.rollback()
