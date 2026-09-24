"""Initial schema for THALI x P.L.A.T.E. multi-tenant clinical infrastructure.

Revision ID: 0001
Revises: 
Create Date: 2026-09-13

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = [
    "patients",
    "care_team_members",
    "glucose_observations",
    "meal_observations",
    "medication_plans",
    "care_tasks",
    "ai_review_artifacts",
    "domain_event_outbox",
]


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Organizations
    op.create_table(
        "organizations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    # 2. Facilities
    op.create_table(
        "facilities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facilities_tenant_id", "facilities", ["tenant_id"])

    # 3. Patients
    op.create_table(
        "patients",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("facility_id", sa.UUID(), nullable=True),
        sa.Column("uh_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patients_tenant_id", "patients", ["tenant_id"])
    op.create_index("ix_patients_facility_id", "patients", ["facility_id"])
    op.create_index("ix_patients_uh_id", "patients", ["uh_id"])
    op.create_index("ix_patients_phone", "patients", ["phone"])
    op.create_index("ix_patients_tenant_uh_id", "patients", ["tenant_id", "uh_id"])
    op.create_index("ix_patients_tenant_phone", "patients", ["tenant_id", "phone"])

    # 4. Care Team Members
    op.create_table(
        "care_team_members",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("facility_id", sa.UUID(), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_care_team_members_tenant_id", "care_team_members", ["tenant_id"])
    op.create_index("ix_care_team_members_user_id", "care_team_members", ["user_id"])
    op.create_index("ix_care_team_members_facility_id", "care_team_members", ["facility_id"])
    op.create_index("ix_care_team_members_tenant_user", "care_team_members", ["tenant_id", "user_id"])

    # 5. Glucose Observations
    op.create_table(
        "glucose_observations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value_mg_dl", sa.Integer(), nullable=True),
        sa.Column("tag", sa.String(length=32), nullable=True),
        sa.Column("confirmation", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("confirmed_by", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_glucose_observations_tenant_id", "glucose_observations", ["tenant_id"])
    op.create_index("ix_glucose_observations_patient_id", "glucose_observations", ["patient_id"])
    op.create_index("ix_glucose_observations_taken_at", "glucose_observations", ["taken_at"])
    op.create_index(
        "ix_glucose_obs_tenant_patient_taken",
        "glucose_observations",
        ["tenant_id", "patient_id", "taken_at"],
    )

    # 6. Meal Observations
    op.create_table(
        "meal_observations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("portion_food_key", sa.String(length=128), nullable=True),
        sa.Column("portion_volume_ml", sa.Integer(), nullable=True),
        sa.Column("portion_quantity", sa.Float(), nullable=True),
        sa.Column("carbs_grams", sa.Float(), nullable=True),
        sa.Column("glycemic_index", sa.String(length=32), nullable=True),
        sa.Column("confirmation", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("confirmed_by", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meal_observations_tenant_id", "meal_observations", ["tenant_id"])
    op.create_index("ix_meal_observations_patient_id", "meal_observations", ["patient_id"])
    op.create_index("ix_meal_observations_recorded_at", "meal_observations", ["recorded_at"])
    op.create_index(
        "ix_meal_obs_tenant_patient_recorded",
        "meal_observations",
        ["tenant_id", "patient_id", "recorded_at"],
    )

    # 7. Medication Plans
    op.create_table(
        "medication_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("prescribed_by_user_id", sa.UUID(), nullable=False),
        sa.Column("prescribed_by_role", sa.String(length=32), nullable=False),
        sa.Column("medication", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("instruction", sa.Text(), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_medication_plans_tenant_id", "medication_plans", ["tenant_id"])
    op.create_index("ix_medication_plans_patient_id", "medication_plans", ["patient_id"])
    op.create_index("ix_medication_plans_prescribed_by_user_id", "medication_plans", ["prescribed_by_user_id"])
    op.create_index(
        "ix_medication_plans_tenant_patient",
        "medication_plans",
        ["tenant_id", "patient_id"],
    )

    # 8. Care Tasks
    op.create_table(
        "care_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("assigned_to_user_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_care_tasks_tenant_id", "care_tasks", ["tenant_id"])
    op.create_index("ix_care_tasks_patient_id", "care_tasks", ["patient_id"])
    op.create_index("ix_care_tasks_assigned_to_user_id", "care_tasks", ["assigned_to_user_id"])
    op.create_index("ix_care_tasks_tenant_patient", "care_tasks", ["tenant_id", "patient_id"])
    op.create_index("ix_care_tasks_tenant_assigned", "care_tasks", ["tenant_id", "assigned_to_user_id"])

    # 9. AI Review Artifacts
    op.create_table(
        "ai_review_artifacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("artifact_kind", sa.String(length=64), nullable=False, server_default="extracted_observation"),
        sa.Column("authority", sa.String(length=32), nullable=False, server_default="clinician_review"),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="generated"),
        sa.Column("generated_by", sa.String(length=64), nullable=False, server_default="ai"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("reviewed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_review_artifacts_tenant_id", "ai_review_artifacts", ["tenant_id"])
    op.create_index("ix_ai_review_artifacts_patient_id", "ai_review_artifacts", ["patient_id"])
    op.create_index("ix_ai_artifacts_tenant_patient", "ai_review_artifacts", ["tenant_id", "patient_id"])
    op.create_index("ix_ai_artifacts_tenant_state", "ai_review_artifacts", ["tenant_id", "state"])

    # 10. Domain Event Outbox
    op.create_table(
        "domain_event_outbox",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=True),
        sa.Column("correlation_id", sa.UUID(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_domain_event_outbox_tenant_id", "domain_event_outbox", ["tenant_id"])
    op.create_index("ix_domain_event_outbox_event_type", "domain_event_outbox", ["event_type"])
    op.create_index("ix_domain_event_outbox_occurred_at", "domain_event_outbox", ["occurred_at"])
    op.create_index("ix_domain_event_outbox_patient_id", "domain_event_outbox", ["patient_id"])
    op.create_index("ix_outbox_unpublished", "domain_event_outbox", ["event_type", "published_at"])

    # PostgreSQL Row Level Security (RLS) enforcement
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

    op.drop_table("domain_event_outbox")
    op.drop_table("ai_review_artifacts")
    op.drop_table("care_tasks")
    op.drop_table("medication_plans")
    op.drop_table("meal_observations")
    op.drop_table("glucose_observations")
    op.drop_table("care_team_members")
    op.drop_table("patients")
    op.drop_table("facilities")
    op.drop_table("organizations")
