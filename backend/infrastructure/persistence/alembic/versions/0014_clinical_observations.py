"""Clinical observations (Gate 05 / Clinical Analytics Pipeline).

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-24

1. Creates ``clinical_observations`` table — the durable store for structured
   laboratory, vitals, screening, and document observations.
2. Supports provenance (source, document_id, recorded_at, metadata_json).
3. Enables and forces PostgreSQL RLS with the standard tenant isolation policy.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
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
        "clinical_observations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("facility_id", sa.UUID(), nullable=True),
        sa.Column("observation_type", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("value_text", sa.String(length=255), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="patient_reported"),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["document_references.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_clinical_observations_tenant_id",
        "clinical_observations",
        ["tenant_id"],
    )
    op.create_index(
        "ix_clinical_observations_patient_id",
        "clinical_observations",
        ["patient_id"],
    )
    op.create_index(
        "ix_clinical_observations_facility_id",
        "clinical_observations",
        ["facility_id"],
    )
    op.create_index(
        "ix_clinical_observations_observation_type",
        "clinical_observations",
        ["observation_type"],
    )
    op.create_index(
        "ix_clinical_observations_code",
        "clinical_observations",
        ["code"],
    )
    op.create_index(
        "ix_clinical_observations_observed_at",
        "clinical_observations",
        ["observed_at"],
    )
    op.create_index(
        "ix_clinical_observations_document_id",
        "clinical_observations",
        ["document_id"],
    )
    op.create_index(
        "ix_clinical_obs_tenant_patient_code",
        "clinical_observations",
        ["tenant_id", "patient_id", "code"],
    )
    op.create_index(
        "ix_clinical_obs_tenant_patient_observed",
        "clinical_observations",
        ["tenant_id", "patient_id", "observed_at"],
    )

    if is_postgres:
        _create_rls("clinical_observations")


def downgrade() -> None:
    op.drop_index("ix_clinical_obs_tenant_patient_observed", table_name="clinical_observations")
    op.drop_index("ix_clinical_obs_tenant_patient_code", table_name="clinical_observations")
    op.drop_index("ix_clinical_observations_document_id", table_name="clinical_observations")
    op.drop_index("ix_clinical_observations_observed_at", table_name="clinical_observations")
    op.drop_index("ix_clinical_observations_code", table_name="clinical_observations")
    op.drop_index("ix_clinical_observations_observation_type", table_name="clinical_observations")
    op.drop_index("ix_clinical_observations_facility_id", table_name="clinical_observations")
    op.drop_index("ix_clinical_observations_patient_id", table_name="clinical_observations")
    op.drop_index("ix_clinical_observations_tenant_id", table_name="clinical_observations")
    op.drop_table("clinical_observations")
