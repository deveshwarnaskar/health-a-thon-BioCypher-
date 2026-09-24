"""Patient-clinician links (patient-doctor QR connect, §13).

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-23

1. Creates ``patient_clinician_links`` — the durable record of a patient
   scanning a clinician's account QR code. The row snapshots the clinician's
   facility (the patient is enrolled there so the clinician's facility-scoped
   reads/monitoring can resolve the patient) and the clinician's display name
   for patient-facing "My Care Team" listings.
2. One ACTIVE link per (tenant, patient, clinician) pair via a partial unique
   index over ``active`` rows only.
3. Enables and forces PostgreSQL RLS with the standard tenant isolation
   policy and grants the application roles.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
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

    op.create_table(
        "patient_clinician_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("clinician_user_id", sa.UUID(), nullable=False),
        sa.Column("facility_id", sa.UUID(), nullable=True),
        sa.Column("clinician_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_patient_clinician_links_tenant_pair",
        "patient_clinician_links",
        ["tenant_id", "patient_id", "clinician_user_id"],
        unique=True,
        postgresql_where=sa.text("active"),
        sqlite_where=sa.text("active"),
    )
    op.create_index(
        "ix_patient_clinician_links_tenant_clinician",
        "patient_clinician_links",
        ["tenant_id", "clinician_user_id"],
    )
    op.create_index(
        "ix_patient_clinician_links_tenant_patient",
        "patient_clinician_links",
        ["tenant_id", "patient_id"],
    )

    if is_postgres:
        _create_rls("patient_clinician_links")


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP POLICY IF EXISTS tenant_isolation_patient_clinician_links ON patient_clinician_links;")
        op.execute("ALTER TABLE patient_clinician_links NO FORCE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE patient_clinician_links DISABLE ROW LEVEL SECURITY;")

    op.drop_index("ix_patient_clinician_links_tenant_patient", table_name="patient_clinician_links")
    op.drop_index("ix_patient_clinician_links_tenant_clinician", table_name="patient_clinician_links")
    op.drop_index("uq_patient_clinician_links_tenant_pair", table_name="patient_clinician_links")
    op.drop_table("patient_clinician_links")