"""Gate 09 — Operational resiliency: idempotency, replay, audit, outbox worker.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-16

Adds the operational scaffolding required by Gate 09:

1. Outbox worker columns on ``domain_event_outbox`` (+ due-index).
2. ``idempotency_records`` — client idempotency reservations.
3. ``webhook_receipts`` — provider replay deduplication (global, no tenant).
4. ``audit_events`` — append-only compliance trail (RG RLS-enforced; mutation
   revoked at the privilege layer AND blocked by a guard trigger).
5. ``resolve_channel_tenant`` — narrow, SECURITY DEFINER phone→(tenant,
   patient) routing function so the privileged lookup works under FORCE RLS.

SQLite paths mirror PostgreSQL minus RLS/grants/trigger/function, keeping the
full suite hermetic offline.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = ["audit_events"]


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ---- 1. Outbox worker columns ---------------------------------------
    op.add_column("domain_event_outbox", sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"))
    op.add_column("domain_event_outbox", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("domain_event_outbox", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("domain_event_outbox", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("domain_event_outbox", sa.Column("locked_by", sa.String(length=255), nullable=True))
    op.add_column("domain_event_outbox", sa.Column("last_error", sa.Text(), nullable=True))
    op.create_index(
        "ix_outbox_due",
        "domain_event_outbox",
        ["status", "next_attempt_at"],
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
        sqlite_where=sa.text("status IN ('pending', 'processing')"),
    )

    # ---- 2. Idempotency records -----------------------------------------
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=512), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="in_progress"),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_headers", sa.JSON(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_idempotency_scope",
        "idempotency_records",
        ["tenant_id", "actor_id", "idempotency_key"],
        unique=True,
    )
    op.create_index("ix_idempotency_expires_at", "idempotency_records", ["expires_at"])

    # ---- 3. Webhook receipts (global, no tenant column) -----------------
    op.create_table(
        "webhook_receipts",
        sa.Column("receipt_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_message_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("source_phone", sa.String(length=32), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="received"),
        sa.PrimaryKeyConstraint("receipt_id"),
    )
    op.create_index(
        "uq_webhook_receipt_provider_msg",
        "webhook_receipts",
        ["provider", "provider_message_id"],
        unique=True,
    )
    op.create_index("ix_webhook_receipt_received", "webhook_receipts", ["received_at"])

    # ---- 4. Audit events (append-only) ----------------------------------
    provenance_type = postgresql.JSONB() if is_postgres else sa.JSON()
    op.create_table(
        "audit_events",
        sa.Column("audit_event_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False, server_default="SYSTEM_WORKER"),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=128), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False, server_default="SUCCESS"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("provenance_metadata", provenance_type, nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("audit_event_id"),
    )
    op.create_index("ix_audit_tenant_occurred", "audit_events", ["tenant_id", "occurred_at"])

    if is_postgres:
        _upgrade_postgres_only()


def _upgrade_postgres_only() -> None:
    # Audit RLS: FORCE so even the table owner is isolated per session tenant.
    for tbl in TENANT_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{tbl} ON {tbl}
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
            """
        )

    # Privilege hardening: application roles may only INSERT/SELECT audit rows.
    # UPDATE/DELETE/TRUNCATE are revoked from PUBLIC and never granted; the
    # trigger below additionally blocks even the table owner.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'thali_app_role') THEN
                GRANT SELECT, INSERT ON audit_events TO thali_app_role;
                GRANT SELECT, INSERT ON idempotency_records TO thali_app_role;
                GRANT SELECT, INSERT ON webhook_receipts TO thali_app_role;
            END IF;
            IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'thali_app_test_role') THEN
                GRANT SELECT, INSERT ON audit_events TO thali_app_test_role;
                GRANT SELECT, INSERT ON idempotency_records TO thali_app_test_role;
                GRANT SELECT, INSERT ON webhook_receipts TO thali_app_test_role;
            END IF;
        END $$;
        """
    )
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM PUBLIC;")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON idempotency_records FROM PUBLIC;")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON webhook_receipts FROM PUBLIC;")

    # Append-only guard: even privileged SQL cannot mutate audit history.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("CREATE TRIGGER prevent_audit_mutation BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();")

    # Narrow SECURITY DEFINER routing anchor: returns ONLY uuid pairs.
    # Executes as its (privileged) owner so FORCE RLS cannot hide rows.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.resolve_channel_tenant(phone text)
        RETURNS TABLE (tenant_id uuid, patient_id uuid)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT p.tenant_id, p.id
            FROM patients p
            WHERE p.phone = resolve_channel_tenant.phone
              AND p.active
            ORDER BY p.created_at
            LIMIT 1;
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'thali_app_test_role') THEN
                GRANT EXECUTE ON FUNCTION public.resolve_channel_tenant(text) TO thali_app_test_role;
            END IF;
            IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'thali_app_role') THEN
                GRANT EXECUTE ON FUNCTION public.resolve_channel_tenant(text) TO thali_app_role;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP TRIGGER IF EXISTS prevent_audit_mutation ON audit_events;")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_mutation();")
        op.execute("DROP FUNCTION IF EXISTS public.resolve_channel_tenant(text);")
        for tbl in TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{tbl} ON {tbl};")

    op.drop_index("ix_audit_tenant_occurred", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("uq_webhook_receipt_provider_msg", table_name="webhook_receipts")
    op.drop_index("ix_webhook_receipt_received", table_name="webhook_receipts")
    op.drop_table("webhook_receipts")
    op.drop_index("uq_idempotency_scope", table_name="idempotency_records")
    op.drop_index("ix_idempotency_expires_at", table_name="idempotency_records")
    op.drop_table("idempotency_records")

    op.drop_index("ix_outbox_due", table_name="domain_event_outbox")
    op.drop_column("domain_event_outbox", "last_error")
    op.drop_column("domain_event_outbox", "locked_by")
    op.drop_column("domain_event_outbox", "locked_at")
    op.drop_column("domain_event_outbox", "next_attempt_at")
    op.drop_column("domain_event_outbox", "retry_count")
    op.drop_column("domain_event_outbox", "status")