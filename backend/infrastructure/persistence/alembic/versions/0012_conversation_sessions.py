"""Gate 11 — Conversation sessions + patient channel preferences (spec §5).

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-22

1. Creates ``whatsapp_conversation_sessions`` — the durable pointer to the
   §5 state machine. Rows carry NO PHI: state, draft kind and a fingerprint
   only (the underlying observation row lives in its own tenant-scoped table
   already persisted in PENDING by the domain handler).
2. Creates ``patient_channel_prefs`` — per-patient, per-channel preferences
   (language + reminder quiet hours) the conversational layer needs to honour
   §20 (quiet hours) and the user's chosen language.
3. Enables and forces PostgreSQL RLS with the standard tenant isolation
   policy on both tables, and grants the application roles.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql, sqlite

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{table} ON {table}
        FOR ALL
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
        """
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'thali_app_role') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO thali_app_role;
            END IF;
            IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'thali_app_test_role') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO thali_app_test_role;
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    json_type = postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON()

    # 1. Conversation sessions — one row per (tenant, patient).
    op.create_table(
        "whatsapp_conversation_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False, server_default="idle"),
        sa.Column("draft_kind", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("draft_fingerprint", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("context", json_type, nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "patient_id", name="uq_conversation_sessions_tenant_patient"),
    )
    op.create_index(
        "ix_conversation_sessions_tenant_state",
        "whatsapp_conversation_sessions",
        ["tenant_id", "state"],
    )
    op.create_index(
        "ix_conversation_sessions_patient",
        "whatsapp_conversation_sessions",
        ["tenant_id", "patient_id"],
    )

    # 2. Patient channel preferences — one row per (patient, channel).
    op.create_table(
        "patient_channel_prefs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="WHATSAPP"),
        sa.Column("preferred_language", sa.String(length=16), nullable=True),
        sa.Column("quiet_hours_start", sa.String(length=5), nullable=True),
        sa.Column("quiet_hours_end", sa.String(length=5), nullable=True),
        sa.Column("last_reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_id", "channel", name="uq_patient_channel_prefs_patient_channel"),
    )
    op.create_index(
        "ix_patient_channel_prefs_tenant_channel",
        "patient_channel_prefs",
        ["tenant_id", "channel"],
    )

    # 3. PostgreSQL RLS.
    if is_postgres:
        _create_rls("whatsapp_conversation_sessions")
        _create_rls("patient_channel_prefs")


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        for table in ("patient_channel_prefs", "whatsapp_conversation_sessions"):
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    op.drop_index("ix_patient_channel_prefs_tenant_channel", table_name="patient_channel_prefs")
    op.drop_table("patient_channel_prefs")
    op.drop_index("ix_conversation_sessions_patient", table_name="whatsapp_conversation_sessions")
    op.drop_index("ix_conversation_sessions_tenant_state", table_name="whatsapp_conversation_sessions")
    op.drop_table("whatsapp_conversation_sessions")
