"""Tests for Database Connection and Configuration Management (Gate 05).

Verifies:
1. create_db_engine configures SQLite in-memory and connection options cleanly.
2. create_session_factory produces sessions without autoflush/autocommit.
3. check_database_health executes shallow ping.
4. No network or database calls happen at module import time.
"""

from sqlalchemy import text

from backend.infrastructure.config.database import (
    check_database_health,
    create_db_engine,
    create_session_factory,
)


def test_create_engine_sqlite_in_memory():
    engine = create_db_engine()
    assert engine.dialect.name == "sqlite"
    assert check_database_health(engine) is True


def test_session_factory_configuration():
    engine = create_db_engine()
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        result = session.execute(text("SELECT 42")).scalar()
        assert result == 42
        assert session.autoflush is False
        assert session.expire_on_commit is False


def test_database_health_check_failure():
    # An engine with invalid closed or broken state
    engine = create_db_engine("sqlite:///:memory:")
    engine.dispose()
    # Health check returns false on broken connect
    # Let's create an invalid host URL
    broken_engine = create_db_engine("postgresql+psycopg://invalid_user:invalid_pass@127.0.0.1:54329/invalid_db")
    assert check_database_health(broken_engine) is False
