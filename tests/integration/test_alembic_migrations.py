"""Integration tests for Alembic schema migrations (Gate 05).

Verifies:
1. Upgrade from empty database to latest schema (head).
2. Downgrade from latest schema back to base.
3. Clean reproducible migrations without manual editing.
"""

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from backend.infrastructure.config.database import create_db_engine


def test_alembic_migration_upgrade_and_downgrade_sqlite():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    with engine.connect() as conn:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.attributes["connection"] = conn

        # 1. Upgrade to head
        command.upgrade(alembic_cfg, "head")

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        expected_tables = {
            "organizations",
            "facilities",
            "patients",
            "care_team_members",
            "caregiver_relationships",
            "identity_patient_mappings",
            "glucose_observations",
            "meal_observations",
            "medication_plans",
            "care_tasks",
            "ai_review_artifacts",
            "domain_event_outbox",
            "idempotency_records",
            "webhook_receipts",
            "audit_events",
            "notifications",
            "alembic_version",
        }
        assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

        # 2. Downgrade back to base
        command.downgrade(alembic_cfg, "base")

        inspector_after = inspect(conn)
        remaining_tables = set(inspector_after.get_table_names()) - {"alembic_version"}
        assert len(remaining_tables) == 0, f"Remaining tables after downgrade: {remaining_tables}"


def test_alembic_migration_postgres_if_available():
    import psycopg
    try:
        with psycopg.connect("dbname=postgres", autocommit=True, connect_timeout=1) as conn:
            with conn.cursor() as cur:
                cur.execute("DROP DATABASE IF EXISTS thali_integ_test_mig WITH (FORCE);")
                cur.execute("CREATE DATABASE thali_integ_test_mig;")
    except Exception:
        pytest.skip("Local PostgreSQL not accessible for integration testing")

    pg_url = "postgresql+psycopg://@localhost:5432/thali_integ_test_mig"
    engine = create_db_engine(pg_url)

    try:
        with engine.connect() as conn:
            alembic_cfg = Config("alembic.ini")
            alembic_cfg.attributes["connection"] = conn

            # Upgrade to head (including PostgreSQL RLS policies)
            command.upgrade(alembic_cfg, "head")

            inspector = inspect(conn)
            tables = set(inspector.get_table_names())
            assert "patients" in tables
            assert "domain_event_outbox" in tables

            # Downgrade to base
            command.downgrade(alembic_cfg, "base")

            inspector_after = inspect(conn)
            remaining = set(inspector_after.get_table_names()) - {"alembic_version"}
            assert len(remaining) == 0
    finally:
        engine.dispose()
        with psycopg.connect("dbname=postgres", autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("DROP DATABASE IF EXISTS thali_integ_test_mig WITH (FORCE);")
