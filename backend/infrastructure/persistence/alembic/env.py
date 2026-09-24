"""Alembic environment configuration (Gate 05)."""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from backend.infrastructure.persistence.models.base import Base
# Ensure all models are imported so their tables appear in Base.metadata
import backend.infrastructure.persistence.models  # noqa: F401

config = getattr(context, "config", None)

if config is not None and config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_database_url() -> str:
    """Resolve database URL dynamically from environment or settings (Gate 10P-C)."""
    import os

    env_url = os.environ.get("THALI_DATABASE__URL")
    if env_url and env_url.strip():
        return env_url.strip()
    try:
        from config.settings import Settings

        settings_url = Settings().database.url
        if settings_url and settings_url.strip():
            return settings_url.strip()
    except Exception:
        pass
    if config is not None:
        return config.get_main_option("sqlalchemy.url") or "sqlite:///:memory:"
    return "sqlite:///:memory:"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = context.config.attributes.get("connection", None)

    if connectable is None:
        db_url = _get_database_url()
        config.set_main_option("sqlalchemy.url", db_url)
        section = config.get_section(config.config_ini_section, {})
        section["sqlalchemy.url"] = db_url

        connectable = engine_from_config(
            section,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata
            )

            with context.begin_transaction():
                context.run_migrations()
    else:
        context.configure(
            connection=connectable, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if config is not None:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
