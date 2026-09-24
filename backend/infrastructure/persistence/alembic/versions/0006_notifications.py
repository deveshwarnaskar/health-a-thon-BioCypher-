"""Gate 10L — Notifications table and PostgreSQL RLS enforcement.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-17

Enforces database-level multi-tenancy guarantees for notification communication layer:
1. Creates ``notifications`` table
2. Enables and forces Row Level Security (RLS) on ``notifications`` with tenant isolation policy
3. Grants appropriate permissions to application roles
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    json_type = postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON()

    # 1. Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("recipient_id", sa.UUID(), nullable=False),
        sa.Column("recipient_phone", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("patient_id", sa.UUID(), nullable=True),
        sa.Column("notification_type", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="WHATSAPP"),
        sa.Column("template_name", sa.String(length=128), nullable=False),
        sa.Column("template_params", json_type, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.UUID(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_notifications_tenant_status", "notifications", ["tenant_id", "status"])
    op.create_index("ix_notifications_due", "notifications", ["status", "scheduled_at"])
    op.create_index("ix_notifications_recipient", "notifications", ["tenant_id", "recipient_id"])
    op.create_index("ix_notifications_patient", "notifications", ["tenant_id", "patient_id"])

    # 2. PostgreSQL Row Level Security (RLS)
    if is_postgres:
        op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE notifications FORCE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY tenant_isolation_notifications ON notifications
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
            """
        )
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'thali_app_role') THEN
                    GRANT SELECT, INSERT, UPDATE ON notifications TO thali_app_role;
                END IF;
                IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'thali_app_test_role') THEN
                    GRANT SELECT, INSERT, UPDATE ON notifications TO thali_app_test_role;
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP POLICY IF EXISTS tenant_isolation_notifications ON notifications;")
        op.execute("ALTER TABLE notifications NO FORCE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE notifications DISABLE ROW LEVEL SECURITY;")

    op.drop_index("ix_notifications_patient", table_name="notifications")
    op.drop_index("ix_notifications_recipient", table_name="notifications")
    op.drop_index("ix_notifications_due", table_name="notifications")
    op.drop_index("ix_notifications_tenant_status", table_name="notifications")
    op.drop_table("notifications")
