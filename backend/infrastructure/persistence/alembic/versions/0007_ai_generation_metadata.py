"""Gate 10M — AI generation metadata and provenance extension.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-17

Extends ``ai_review_artifacts`` table with generation provenance and review tracking:
1. model_name: Identifier of the AI model / provider used
2. evidence_hash: Deterministic SHA-256 hash of the authorized evidence package
3. correlation_id: Request tracing and idempotency correlation identifier
4. original_summary: Preserved raw AI generation output upon human clinician edit
5. reviewed_at: Clinician review timestamp
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_review_artifacts",
        sa.Column("model_name", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "ai_review_artifacts",
        sa.Column("evidence_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "ai_review_artifacts",
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "ai_review_artifacts",
        sa.Column("original_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "ai_review_artifacts",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_ai_review_artifacts_correlation_id",
        "ai_review_artifacts",
        ["correlation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_review_artifacts_correlation_id", table_name="ai_review_artifacts")
    op.drop_column("ai_review_artifacts", "reviewed_at")
    op.drop_column("ai_review_artifacts", "original_summary")
    op.drop_column("ai_review_artifacts", "correlation_id")
    op.drop_column("ai_review_artifacts", "evidence_hash")
    op.drop_column("ai_review_artifacts", "model_name")
