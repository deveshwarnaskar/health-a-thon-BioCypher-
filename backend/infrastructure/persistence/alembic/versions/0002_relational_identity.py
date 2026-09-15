"""Relational identity: caregiver relationships + identity-patient mappings.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-15

Adds tenant-scoped RLS-protected tables for caregiver proxy relationships and
identity→patient mappings. Runs on both PostgreSQL and SQLite; RLS policies
execute only on PostgreSQL.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = [
    "caregiver_relationships",
    "identity_patient_mappings",
]


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 11. Caregiver Relationships
    op.create_table(
        "caregiver_relationships",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("caregiver_user_id", sa.UUID(), nullable=False),
        sa.Column("relationship_label", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # One non-revoked relationship per (tenant, patient, caregiver) pair.
    op.create_index(
        "uq_caregiver_relationships_tenant_pair",
        "caregiver_relationships",
        ["tenant_id", "patient_id", "caregiver_user_id"],
        unique=True,
        postgresql_where=sa.text("status != 'revoked'"),
        sqlite_where=sa.text("status != 'revoked'"),
    )
    op.create_index(
        "ix_caregiver_relationships_tenant_id",
        "caregiver_relationships",
        ["tenant_id"],
    )
    op.create_index(
        "ix_caregiver_relationships_patient_id",
        "caregiver_relationships",
        ["patient_id"],
    )
    op.create_index(
        "ix_caregiver_relationships_caregiver_user_id",
        "caregiver_relationships",
        ["caregiver_user_id"],
    )
    op.create_index(
        "ix_caregiver_relationships_tenant_caregiver",
        "caregiver_relationships",
        ["tenant_id", "caregiver_user_id"],
    )
    op.create_index(
        "ix_caregiver_relationships_tenant_patient",
        "caregiver_relationships",
        ["tenant_id", "patient_id"],
    )

    # 12. Identity Patient Mappings
    op.create_table(
        "identity_patient_mappings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Active mappings are 1:1 per user and per patient (partial unique).
    op.create_index(
        "uq_identity_mappings_tenant_user",
        "identity_patient_mappings",
        ["tenant_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("active"),
        sqlite_where=sa.text("active"),
    )
    op.create_index(
        "uq_identity_mappings_tenant_patient",
        "identity_patient_mappings",
        ["tenant_id", "patient_id"],
        unique=True,
        postgresql_where=sa.text("active"),
        sqlite_where=sa.text("active"),
    )
    op.create_index(
        "ix_identity_patient_mappings_tenant_id",
        "identity_patient_mappings",
        ["tenant_id"],
    )
    op.create_index(
        "ix_identity_patient_mappings_user_id",
        "identity_patient_mappings",
        ["user_id"],
    )
    op.create_index(
        "ix_identity_patient_mappings_patient_id",
        "identity_patient_mappings",
        ["patient_id"],
    )

    # PostgreSQL Row Level Security (RLS) enforcement for both tables
    if is_postgres:
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


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        for tbl in TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{tbl} ON {tbl};")

    op.drop_table("identity_patient_mappings")
    op.drop_table("caregiver_relationships")