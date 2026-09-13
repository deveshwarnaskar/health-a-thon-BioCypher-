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
    pool_pre_ping: bool = True,
    pool_recycle: int = 3600,
) -> Engine:
    """Create and configure a SQLAlchemy Engine.
    
    If no url is provided, defaults to SQLite in-memory for testing.
    Uses StaticPool for in-memory SQLite to preserve database state across connections.
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
    
    return create_engine(
        db_url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        pool_recycle=pool_recycle,
        poolclass=QueuePool,
    )


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
    """Perform a shallow health-check against the database engine."""
    try:
        with engine.connect() as conn:
            conn.execute(select(1))
            return True
    except Exception:
        return False
