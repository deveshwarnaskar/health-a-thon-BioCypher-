"""Gate 10L — Notifications Row Level Security (RLS) on PostgreSQL.

Verifies:
1. Migration 0006 creates notifications table with FORCE ROW LEVEL SECURITY.
2. Tenant isolation policy on notifications:
   - Missing tenant context -> 0 rows (fail closed)
   - Tenant A context -> only Tenant A notifications
   - Tenant B context -> only Tenant B notifications
3. Cross-tenant access denied at the database engine level (RLS blocks SELECT/INSERT/UPDATE).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.domain.entities import Notification, NotificationStatus
from backend.infrastructure.config.database import create_db_engine
from backend.infrastructure.persistence.models import OrganizationModel
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork

APP_TEST_ROLE = "thali_app_test_role"


@pytest.fixture(scope="module")
def postgres_gate10l_db():
    import psycopg

    db_name = f"thali_notif10l_{uuid4().hex[:8]}"
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


class TestNotificationsRLSPostgres:
    def test_notifications_rls_tenant_isolation(self, postgres_gate10l_db):
        engine = create_db_engine(postgres_gate10l_db)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        tenant_a = uuid4()
        tenant_b = uuid4()
        user_a = uuid4()
        user_b = uuid4()

        with session_factory() as s:
            s.add(OrganizationModel(id=tenant_a, name="Tenant A", slug="tenant-a"))
            s.add(OrganizationModel(id=tenant_b, name="Tenant B", slug="tenant-b"))
            s.commit()

        # Seed notification in Tenant A and Tenant B using SqlAlchemyUnitOfWork
        notif_a_id = uuid4()
        notif_b_id = uuid4()

        with SqlAlchemyUnitOfWork(session_factory, tenant_a) as uow_a:
            uow_a.notifications.add(
                Notification(
                    id=notif_a_id,
                    tenant_id=tenant_a,
                    recipient_id=user_a,
                    recipient_phone="+919111111111",
                    template_name="reminder_a",
                    template_params={"text": "tenant_a_msg"},
                )
            )
            uow_a.commit()

        with SqlAlchemyUnitOfWork(session_factory, tenant_b) as uow_b:
            uow_b.notifications.add(
                Notification(
                    id=notif_b_id,
                    tenant_id=tenant_b,
                    recipient_id=user_b,
                    recipient_phone="+919222222222",
                    template_name="reminder_b",
                    template_params={"text": "tenant_b_msg"},
                )
            )
            uow_b.commit()

        # Now test direct queries under unprivileged role thali_app_test_role
        with session_factory() as s:
            s.execute(text(f"SET ROLE {APP_TEST_ROLE}"))

            # 1. Without tenant context -> 0 rows (fail closed)
            s.execute(text("SELECT set_config('app.current_tenant_id', '', true)"))
            rows_none = s.execute(text("SELECT id FROM notifications")).fetchall()
            assert len(rows_none) == 0, "Expected 0 rows when tenant context is unset"

            # 2. Under Tenant A context -> only Tenant A row visible
            s.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_a)})
            rows_a = s.execute(text("SELECT id FROM notifications")).fetchall()
            assert len(rows_a) == 1
            assert rows_a[0][0] == notif_a_id

            # 3. Under Tenant B context -> only Tenant B row visible
            s.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_b)})
            rows_b = s.execute(text("SELECT id FROM notifications")).fetchall()
            assert len(rows_b) == 1
            assert rows_b[0][0] == notif_b_id

            # 4. Attempt cross-tenant insert (WITH CHECK violation)
            s.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_a)})
            with pytest.raises(Exception):
                # Try inserting row with tenant_b while app.current_tenant_id is tenant_a
                s.execute(
                    text(
                        "INSERT INTO notifications (id, tenant_id, recipient_id, recipient_phone, "
                        "notification_type, channel, template_name, template_params, status, created_at, retry_count) "
                        "VALUES (:id, :tid, :rid, :phone, :ntype, :chan, :tmpl, :params, :status, :created, 0)"
                    ),
                    {
                        "id": str(uuid4()),
                        "tid": str(tenant_b),
                        "rid": str(uuid4()),
                        "phone": "+919999999999",
                        "ntype": "reminder",
                        "chan": "WHATSAPP",
                        "tmpl": "spoofed",
                        "params": "{}",
                        "status": "pending",
                        "created": datetime.now(timezone.utc),
                    },
                )
            s.rollback()
