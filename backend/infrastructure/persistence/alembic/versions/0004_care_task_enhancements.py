"""Gate 10J-B — CareTask due_at and assignee status index.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-17

Adds:
1. due_at column to care_tasks
2. ix_care_tasks_tenant_assigned_status composite index for assignee/status queries
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("care_tasks", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_care_tasks_tenant_assigned_status",
        "care_tasks",
        ["tenant_id", "assigned_to_user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_care_tasks_tenant_assigned_status", table_name="care_tasks")
    op.drop_column("care_tasks", "due_at")
