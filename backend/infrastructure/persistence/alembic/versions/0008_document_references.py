"""Gate 10N — Document references table and PostgreSQL RLS enforcement.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-18

Enforces database-level multi-tenancy guarantees for document and report storage:
1. Creates ``document_references`` table
2. Enables and forces Row Level Security (RLS) on ``document_references`` with tenant isolation policy
3. Grants appropriate permissions to application roles
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Create document_references table
    op.create_table(
        "document_references",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("facility_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="clinical_report"),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_document_references_tenant_patient", "document_references", ["tenant_id", "patient_id"])
    op.create_index("ix_document_references_tenant_kind", "document_references", ["tenant_id", "kind"])
    op.create_index("ix_document_references_facility", "document_references", ["tenant_id", "facility_id"])
    op.create_index("ix_document_references_correlation_id", "document_references", ["correlation_id"])

    # 2. PostgreSQL Row Level Security (RLS)
    if is_postgres:
        op.execute("ALTER TABLE document_references ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE document_references FORCE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY tenant_isolation_document_references ON document_references
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
                    GRANT SELECT, INSERT, UPDATE, DELETE ON document_references TO thali_app_role;
                END IF;
                IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'thali_app_test_role') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE ON document_references TO thali_app_test_role;
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP POLICY IF EXISTS tenant_isolation_document_references ON document_references;")
        op.execute("ALTER TABLE document_references NO FORCE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE document_references DISABLE ROW LEVEL SECURITY;")

    op.drop_index("ix_document_references_correlation_id", table_name="document_references")
    op.drop_index("ix_document_references_facility", table_name="document_references")
    op.drop_index("ix_document_references_tenant_kind", table_name="document_references")
    op.drop_index("ix_document_references_tenant_patient", table_name="document_references")
    op.drop_table("document_references")
