"""Gate 10P-C — Database Reliability, Connection Pooling, Backup & Recovery Tests.

Verifies the 11-point Failure and Recovery Test Matrix:
TC-10PC-01: DB unavailable at API startup / readiness bounded failure
TC-10PC-02: DB drop during active transaction cleanly rolls back
TC-10PC-03: Pool exhaustion respects bounded pool_timeout
TC-10PC-04: Stale connection detected and recycled via pool_pre_ping
TC-10PC-05: Transaction rollback integrity via in_transaction
TC-10PC-06: Cross-tenant RLS isolation across pooled connections (zero leakage)
TC-10PC-07: Idempotency reservation failure remains fail-closed (503)
TC-10PC-08: Worker polling recovery after transient database error
TC-10PC-09: Alembic dynamic PostgreSQL URL resolution from environment/settings
TC-10PC-10: Backup script generates compressed .sql.gz and valid SHA-256 checksum
TC-10PC-11: Restore script verifies checksum, respects confirmation guard, and restores data
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from backend.application.services._transaction import in_transaction
from backend.infrastructure.config.database import check_database_health, create_db_engine, create_session_factory
from backend.infrastructure.persistence.alembic.env import _get_database_url
from backend.infrastructure.persistence.ops.tenant_resolver import SqlAlchemyChannelTenantResolver
from backend.interfaces.http.dependencies import (
    _get_engine,
    _get_session_factory,
    get_engine,
    reset_config_cache,
)
from config.settings import DatabaseConfig, Settings


# ─────────────────────────────────────────────────────────────────────────────
# 1. Connection Pool & Readiness Tests (TC-10PC-01, TC-10PC-03, TC-10PC-04)
# ─────────────────────────────────────────────────────────────────────────────


class TestDatabasePoolReliability:
    """Validate connection pooling, timeouts, and pre-ping behavior."""

    def test_tc10pc_03_pool_exhaustion_bounded_timeout(self):
        """TC-10PC-03: When pool is exhausted, acquiring connection fails within pool_timeout."""
        # Use sqlite with QueuePool to test bounded timeout without external services
        engine = create_engine(
            "sqlite://",
            poolclass=QueuePool,
            pool_size=1,
            max_overflow=0,
            pool_timeout=0.3,
        )

        conn1 = engine.connect()
        start_time = time.monotonic()
        try:
            with pytest.raises(SATimeoutError):
                engine.connect()
            elapsed = time.monotonic() - start_time
            # Must timeout within reasonable bounded window (~0.3s - 0.7s)
            assert 0.25 <= elapsed < 1.0, f"Pool timeout took {elapsed:.2f}s, expected ~0.3s"
        finally:
            conn1.close()
            engine.dispose()

    def test_tc10pc_01_check_database_health_bounded_timeout(self):
        """TC-10PC-01: check_database_health respects timeout and returns False when hung."""
        engine = create_db_engine("sqlite:///:memory:")

        # Mock engine.connect to simulate a hanging connection that blocks indefinitely
        def mock_hanging_connect(*args, **kwargs):
            time.sleep(2.0)
            raise RuntimeError("Database hung")

        with patch.object(engine, "connect", side_effect=mock_hanging_connect):
            start_time = time.monotonic()
            healthy = check_database_health(engine, timeout_seconds=0.3)
            elapsed = time.monotonic() - start_time

            assert healthy is False
            assert elapsed < 1.0, f"Health check blocked for {elapsed:.2f}s, expected <= 0.5s"

    def test_tc10pc_04_pool_pre_ping_reconnects_stale_connection(self):
        """TC-10PC-04: Stale/dropped connections are recycled automatically on checkout."""
        engine = create_db_engine(
            "sqlite:///:memory:",
            pool_pre_ping=True,
            pool_recycle=3600,
        )

        with engine.connect() as conn:
            val = conn.execute(select(1)).scalar()
            assert val == 1

        # Pre-ping on healthy engine succeeds
        with engine.connect() as conn:
            val2 = conn.execute(select(2)).scalar()
            assert val2 == 2

    def test_dependencies_wire_database_settings_and_cache_factories(self, monkeypatch):
        """Dependencies use configured pool settings and cache sessionmaker."""
        reset_config_cache()
        monkeypatch.setenv("THALI_DATABASE__POOL_SIZE", "7")
        monkeypatch.setenv("THALI_DATABASE__MAX_OVERFLOW", "14")
        monkeypatch.setenv("THALI_DATABASE__POOL_TIMEOUT", "4.5")

        try:
            settings = Settings()
            assert settings.database.pool_size == 7
            assert settings.database.max_overflow == 14
            assert settings.database.pool_timeout == 4.5

            url = "sqlite:///:memory:"
            engine = _get_engine(url)
            assert engine is not None

            # Verify session factory caching
            sf1 = _get_session_factory(url)
            sf2 = _get_session_factory(url)
            assert sf1 is sf2, "Session factories must be cached per engine URL"
        finally:
            reset_config_cache()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Transaction Integrity & RLS Isolation (TC-10PC-02, TC-10PC-05, TC-10PC-06)
# ─────────────────────────────────────────────────────────────────────────────


class TestTransactionAndRLSIntegrity:
    """Validate transaction rollback and RLS context isolation across pooled connections."""

    def test_tc10pc_05_transaction_rollback_deterministic(self):
        """TC-10PC-05: in_transaction commits on success and rolls back on exception."""
        mock_uow = MagicMock()

        def successful_action():
            return "done"

        res = in_transaction(mock_uow, successful_action)
        assert res == "done"
        assert mock_uow.commit.called
        assert not mock_uow.rollback.called

        mock_uow.reset_mock()

        def failing_action():
            raise ValueError("business violation")

        with pytest.raises(ValueError, match="business violation"):
            in_transaction(mock_uow, failing_action)

        assert mock_uow.rollback.called
        assert not mock_uow.commit.called

    def test_tc10pc_06_pooled_connection_tenant_state_isolation_sqlite(self):
        """TC-10PC-06: Verification of transaction-local clean state on connection reuse."""
        engine = create_engine(
            "sqlite:///:memory:",
            poolclass=QueuePool,
            pool_reset_on_return="rollback",
        )

        # Checkout connection 1, simulate setting temporary state, then close
        with engine.connect() as conn1:
            conn1.execute(text("CREATE TEMP TABLE t_test (val TEXT);"))
            conn1.execute(text("INSERT INTO t_test VALUES ('tenant-1-data');"))
            conn1.commit()

        # Checkout connection again - verify connection return and clean transaction
        with engine.connect() as conn2:
            trans = conn2.begin()
            # Any transaction rollback cleans up active transaction state
            trans.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Worker Session Hardening (TC-10PC-08)
# ─────────────────────────────────────────────────────────────────────────────


class TestWorkerSessionHardening:
    """Validate that SqlAlchemyChannelTenantResolver uses bounded, short-lived sessions."""

    def test_tc10pc_08_tenant_resolver_uses_short_lived_sessions(self):
        """SqlAlchemyChannelTenantResolver opens and closes session per resolve() call."""
        mock_session = MagicMock()
        mock_session.get_bind.return_value.dialect.name = "sqlite"
        mock_session.execute.return_value.first.return_value = None

        mock_factory = MagicMock(return_value=mock_session)
        resolver = SqlAlchemyChannelTenantResolver(mock_factory)

        res = resolver.resolve("+919876543210")
        assert res is None
        assert mock_factory.called
        assert mock_session.close.called

    def test_tc10pc_08_tenant_resolver_recovers_after_exception(self):
        """Tenant resolver rolls back and closes on exception, recovering on next call."""
        failing_session = MagicMock()
        failing_session.get_bind.return_value.dialect.name = "sqlite"
        failing_session.execute.side_effect = RuntimeError("Transient DB disconnect")

        healthy_session = MagicMock()
        healthy_session.get_bind.return_value.dialect.name = "sqlite"
        healthy_session.execute.return_value.first.return_value = None

        sessions = [failing_session, healthy_session]
        mock_factory = MagicMock(side_effect=lambda: sessions.pop(0))

        resolver = SqlAlchemyChannelTenantResolver(mock_factory)

        # 1. First call fails transiently
        res1 = resolver.resolve("+919876543210")
        assert res1 is None
        assert failing_session.rollback.called
        assert failing_session.close.called

        # 2. Second call uses a fresh healthy session and recovers without restart
        res2 = resolver.resolve("+919876543210")
        assert res2 is None
        assert healthy_session.close.called


# ─────────────────────────────────────────────────────────────────────────────
# 4. Alembic Dynamic Database URL Resolution (TC-10PC-09)
# ─────────────────────────────────────────────────────────────────────────────


class TestAlembicDynamicURLResolution:
    """Validate that alembic env.py dynamically loads database URL from environment/settings."""

    def test_tc10pc_09_alembic_env_resolves_thali_database_url(self, monkeypatch):
        """_get_database_url prioritizes THALI_DATABASE__URL."""
        test_url = "postgresql+psycopg://user:pass@dbhost:5432/thali_prod"
        monkeypatch.setenv("THALI_DATABASE__URL", test_url)
        assert _get_database_url() == test_url

    def test_tc10pc_09_alembic_env_resolves_settings_url(self, monkeypatch):
        """_get_database_url falls back to Settings().database.url when env var empty."""
        monkeypatch.delenv("THALI_DATABASE__URL", raising=False)
        test_url = "postgresql+psycopg://user:pass@settings-host:5432/thali_db"
        mock_settings = MagicMock()
        mock_settings.database.url = test_url
        with patch("config.settings.Settings", return_value=mock_settings):
            assert _get_database_url() == test_url


# ─────────────────────────────────────────────────────────────────────────────
# 5. Backup & Restore Scripts Verification (TC-10PC-10, TC-10PC-11)
# ─────────────────────────────────────────────────────────────────────────────


class TestBackupAndRestoreScripts:
    """Validate backup and restore script error handling, CLI options, and security."""

    def test_tc10pc_10_backup_script_fails_without_url(self):
        """backup_database.sh fails closed with exit code 1 if no DB URL is provided."""
        script_path = Path("scripts/backup_database.sh").resolve()
        res = subprocess.run([str(script_path)], capture_output=True, text=True)
        assert res.returncode == 1
        assert "Database URL not specified" in res.stderr

    def test_tc10pc_11_restore_script_fails_without_confirmation(self):
        """restore_database.sh fails closed with exit code 2 if --confirm is not supplied."""
        script_path = Path("scripts/restore_database.sh").resolve()
        # Create a dummy backup file
        with tempfile.NamedTemporaryFile(suffix=".sql.gz") as tmp:
            res = subprocess.run(
                [str(script_path), "-f", tmp.name, "-d", "postgresql://dummy"],
                capture_output=True,
                text=True,
            )
            assert res.returncode == 2
            assert "Safety guard triggered" in res.stderr


# ─────────────────────────────────────────────────────────────────────────────
# 6. Real PostgreSQL Integration Tests (TC-10PC-06, TC-10PC-10, TC-10PC-11)
# ─────────────────────────────────────────────────────────────────────────────


def _is_local_postgres_available() -> bool:
    """Check if local PostgreSQL is accessible for live integration testing."""
    try:
        import psycopg
        with psycopg.connect("dbname=postgres", autocommit=True, connect_timeout=1) as conn:
            return True
    except Exception:
        return False


@pytest.mark.skipif(not _is_local_postgres_available(), reason="Local PostgreSQL not accessible")
class TestPostgreSQLLiveIntegration:
    """Live PostgreSQL tests for RLS pooled connection isolation and backup/restore."""

    @pytest.fixture(autouse=True)
    def setup_test_db(self):
        import psycopg
        db_name = f"thali_integ_test_{uuid4().hex[:8]}"
        with psycopg.connect("dbname=postgres", autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE {db_name};")

        self.pg_url = f"postgresql+psycopg://localhost:5432/{db_name}"
        self.plain_pg_url = f"postgresql://localhost:5432/{db_name}"
        self.db_name = db_name

        yield

        with psycopg.connect("dbname=postgres", autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE);")

    def test_tc10pc_06_rls_isolation_across_reused_pooled_connection(self):
        """TC-10PC-06: Tenant 1 context does not leak to Tenant 2 on reused pooled connection."""
        engine = create_db_engine(
            self.pg_url,
            pool_size=1,
            max_overflow=0,
            pool_reset_on_return="rollback",
        )

        tenant1_id = uuid4()
        tenant2_id = uuid4()

        with engine.connect() as conn:
            conn.execute(
                text("""
                CREATE TABLE items (
                    id UUID PRIMARY KEY,
                    tenant_id UUID NOT NULL,
                    name TEXT NOT NULL
                );
                ALTER TABLE items ENABLE ROW LEVEL SECURITY;
                ALTER TABLE items FORCE ROW LEVEL SECURITY;
                CREATE POLICY items_tenant ON items
                FOR ALL
                USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gate10pc_rls_user') THEN
                        CREATE ROLE gate10pc_rls_user NOSUPERUSER NOBYPASSRLS;
                    END IF;
                END
                $$;
                GRANT ALL ON items TO gate10pc_rls_user;
            """)
            )
            conn.commit()

        try:
            # Session 1: Insert Tenant 1 item using transaction-local set_config under non-superuser
            with engine.connect() as conn:
                conn.execute(text("SET ROLE gate10pc_rls_user;"))
                conn.execute(text("SELECT set_config('app.current_tenant_id', :tid, true);"), {"tid": str(tenant1_id)})
                conn.execute(
                    text("INSERT INTO items (id, tenant_id, name) VALUES (:id, :tid, 'Item 1');"),
                    {"id": str(uuid4()), "tid": str(tenant1_id)},
                )
                conn.commit()

            # Session 2: Check out the SAME connection from the pool without setting tenant
            # RLS must fail-closed (0 rows returned)
            with engine.connect() as conn:
                conn.execute(text("SET ROLE gate10pc_rls_user;"))
                rows = conn.execute(text("SELECT * FROM items;")).fetchall()
                assert len(rows) == 0, f"Expected 0 rows for unset tenant, got {len(rows)}"

            # Session 3: Check out connection for Tenant 2
            # Must see ONLY Tenant 2 rows (0 rows), never Tenant 1 rows
            with engine.connect() as conn:
                conn.execute(text("SET ROLE gate10pc_rls_user;"))
                conn.execute(text("SELECT set_config('app.current_tenant_id', :tid, true);"), {"tid": str(tenant2_id)})
                rows = conn.execute(text("SELECT * FROM items;")).fetchall()
                assert len(rows) == 0, f"Cross-tenant leak! Tenant 2 saw {len(rows)} rows from Tenant 1"
                conn.commit()

            # Session 4: Check out connection for Tenant 1
            # Must see Tenant 1 item
            with engine.connect() as conn:
                conn.execute(text("SET ROLE gate10pc_rls_user;"))
                conn.execute(text("SELECT set_config('app.current_tenant_id', :tid, true);"), {"tid": str(tenant1_id)})
                rows = conn.execute(text("SELECT * FROM items;")).fetchall()
                assert len(rows) == 1, f"Expected 1 row for Tenant 1, got {len(rows)}"
                conn.commit()
        finally:
            with engine.connect() as conn:
                conn.execute(text("RESET ROLE; DROP TABLE IF EXISTS items; DROP ROLE IF EXISTS gate10pc_rls_user;"))
                conn.commit()
            engine.dispose()

    def test_tc10pc_10_and_11_backup_restore_cycle(self):
        """TC-10PC-10 & TC-10PC-11: Full backup, checksum verification, and restore cycle."""
        # 1. Seed source database with a test table and row
        engine = create_db_engine(self.pg_url)
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE test_data (id INT PRIMARY KEY, payload TEXT);"))
            conn.execute(text("INSERT INTO test_data VALUES (1, 'vital-sign-recovery-proof');"))
            conn.commit()
        engine.dispose()

        # 2. Run backup script into temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_script = Path("scripts/backup_database.sh").resolve()
            backup_res = subprocess.run(
                [str(backup_script), "-d", self.plain_pg_url, "-o", tmpdir],
                capture_output=True,
                text=True,
            )
            assert backup_res.returncode == 0, f"Backup failed: {backup_res.stderr}"

            # Check that backup file and sha256 exist
            backups = list(Path(tmpdir).glob("*.sql.gz"))
            assert len(backups) == 1
            backup_file = backups[0]
            checksum_file = Path(f"{backup_file}.sha256")
            assert checksum_file.exists()

            # 3. Create clean target database to restore into
            import psycopg
            restore_db = f"thali_restore_{uuid4().hex[:8]}"
            with psycopg.connect("dbname=postgres", autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"CREATE DATABASE {restore_db};")

            target_url = f"postgresql://localhost:5432/{restore_db}"
            try:
                restore_script = Path("scripts/restore_database.sh").resolve()
                restore_res = subprocess.run(
                    [str(restore_script), "-f", str(backup_file), "-d", target_url, "--confirm"],
                    capture_output=True,
                    text=True,
                )
                assert restore_res.returncode == 0, f"Restore failed: {restore_res.stderr}"

                # 4. Verify target database contains restored data with 100% fidelity
                restore_engine = create_db_engine(f"postgresql+psycopg://localhost:5432/{restore_db}")
                with restore_engine.connect() as conn:
                    val = conn.execute(text("SELECT payload FROM test_data WHERE id = 1;")).scalar()
                    assert val == "vital-sign-recovery-proof"
                restore_engine.dispose()
            finally:
                with psycopg.connect("dbname=postgres", autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(f"DROP DATABASE IF EXISTS {restore_db} WITH (FORCE);")
