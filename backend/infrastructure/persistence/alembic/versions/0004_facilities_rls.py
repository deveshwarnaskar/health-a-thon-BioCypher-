"""Gate 10K-B — Facilities RLS enforcement and CareTeamMember uniqueness.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-17

Enforces database-level multi-tenancy guarantees for administrative control plane:
1. Row Level Security (RLS) on ``facilities``:
   - ENABLE ROW LEVEL SECURITY
   - FORCE ROW LEVEL SECURITY
   - Tenant isolation policy with USING and WITH CHECK
2. Unique constraint on ``care_team_members (tenant_id, user_id)``:
   - Guarantees one membership per user per tenant
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Care team member uniqueness constraint: (tenant_id, user_id)
    if is_postgres:
        op.create_unique_constraint(
            "uq_care_team_members_tenant_user",
            "care_team_members",
            ["tenant_id", "user_id"],
        )
    else:
        with op.batch_alter_table("care_team_members") as batch_op:
            batch_op.create_unique_constraint(
                "uq_care_team_members_tenant_user",
                ["tenant_id", "user_id"],
            )

    # 2. Facilities PostgreSQL Row Level Security (RLS)
    if is_postgres:
        op.execute("ALTER TABLE facilities ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE facilities FORCE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY tenant_isolation_facilities ON facilities
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Drop facilities RLS
    if is_postgres:
        op.execute("DROP POLICY IF EXISTS tenant_isolation_facilities ON facilities;")
        op.execute("ALTER TABLE facilities NO FORCE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE facilities DISABLE ROW LEVEL SECURITY;")

    # 2. Drop care team member uniqueness constraint
    if is_postgres:
        op.drop_constraint(
            "uq_care_team_members_tenant_user",
            "care_team_members",
            type_="unique",
        )
    else:
        with op.batch_alter_table("care_team_members") as batch_op:
            batch_op.drop_constraint("uq_care_team_members_tenant_user", type_="unique")
