"""Database connection and session lifecycle management (Gate 05).

Provides centralized SQLAlchemy 2.x engine and sessionmaker factories
with safe connection pooling, pre-ping health checks, and transaction boundaries.
No network calls or connections are made at module import time.
"""

from __future__ import annotations

from typing import Callable
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool, QueuePool


def create_db_engine(
    url: str | None = None,
    echo: bool = False,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_timeout: float = 5.0,
    pool_pre_ping: bool = True,
    pool_recycle: int = 3600,
    pool_reset_on_return: str = "rollback",
) -> Engine:
    """Create and configure a SQLAlchemy Engine.

    If no url is provided, defaults to SQLite in-memory for testing.
    Uses StaticPool for in-memory SQLite to preserve database state across connections.
    For PostgreSQL / other engines, uses QueuePool with configured pool sizing,
    bounded timeout, pre-ping liveness, and deterministic reset on return.
    """
    db_url = url or "sqlite:///:memory:"

    if db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if ":memory:" in db_url:
            return create_engine(
                db_url,
                echo=echo,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        return create_engine(
            db_url,
            echo=echo,
            connect_args=connect_args,
        )

    engine = create_engine(
        db_url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_pre_ping=pool_pre_ping,
        pool_recycle=pool_recycle,
        pool_reset_on_return=pool_reset_on_return,
        poolclass=QueuePool,
    )
    instrument_engine_pool(engine)
    return engine


def instrument_engine_pool(engine: Engine) -> None:
    """Instrument SQLAlchemy connection pool with Prometheus gauges (Gate 10P-D)."""
    from sqlalchemy import event
    from backend.infrastructure.observability.metrics import get_metrics_registry

    registry = get_metrics_registry()

    def _sync_pool_gauges(pool):
        try:
            if hasattr(pool, "size"):
                registry.gauge("db_pool_size").set(pool.size())
            if hasattr(pool, "checkedout"):
                registry.gauge("db_pool_checked_out").set(pool.checkedout())
            if hasattr(pool, "checkedin"):
                registry.gauge("db_pool_checked_in").set(pool.checkedin())
            if hasattr(pool, "overflow"):
                registry.gauge("db_pool_overflow").set(max(0, pool.overflow()))
        except Exception:
            pass

    def on_checkout(dbapi_con, con_record, con_proxy):
        _sync_pool_gauges(engine.pool)

    def on_checkin(dbapi_con, con_record):
        _sync_pool_gauges(engine.pool)

    def on_connect(dbapi_con, con_record):
        _sync_pool_gauges(engine.pool)

    try:
        event.listen(engine.pool, "checkout", on_checkout)
        event.listen(engine.pool, "checkin", on_checkin)
        event.listen(engine.pool, "connect", on_connect)
        _sync_pool_gauges(engine.pool)
    except Exception:
        pass


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to the given engine.

    Sessions are configured to not autoflush or autocommit prematurely,
    and expire_on_commit is set to False to retain domain mappings post-commit.
    """
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def check_database_health(engine: Engine, timeout_seconds: float = 3.0) -> bool:
    """Perform a shallow health-check against the database engine with bounded timeout."""
    import concurrent.futures
    from backend.infrastructure.observability.metrics import get_metrics_registry

    registry = get_metrics_registry()

    def _probe() -> bool:
        try:
            with engine.connect() as conn:
                conn.execution_options(timeout=timeout_seconds).execute(select(1))
                return True
        except Exception:
            return False

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    is_healthy = False
    try:
        future = executor.submit(_probe)
        is_healthy = future.result(timeout=timeout_seconds)
    except Exception:
        is_healthy = False
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    try:
        if is_healthy:
            registry.gauge("db_readiness_status").set(1)
            registry.gauge("dependency_health_status").set(1, dependency="postgresql")
        else:
            registry.gauge("db_readiness_status").set(0)
            registry.gauge("dependency_health_status").set(0, dependency="postgresql")
            registry.counter("db_pool_connection_failures_total").inc()
            registry.counter("dependency_failures_total").inc(
                dependency="postgresql", error_type="connection_failure"
            )
    except Exception:
        pass

    return is_healthy

