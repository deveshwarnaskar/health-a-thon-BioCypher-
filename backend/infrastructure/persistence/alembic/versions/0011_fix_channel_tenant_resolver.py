"""Fix channel tenant routing function (param/column name collision).

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-22

The mailbox ``resolve_channel_tenant`` body deployed in the wild used the
parameter name ``phone`` unqualified inside its SELECT. Because PostgreSQL
resolves unqualified identifiers against the FROM columns first, ``phone`` was
bound to ``patients.phone`` instead of the function argument — making the
function ignore the caller's number entirely and return the newest active
patient for EVERY sender (a cross-tenant/cross-patient routing leak).

This migration redeploys the function with a non-colliding parameter name
(``candidate_phone``) and explicit qualification, preserving the normalized
exact/suffix matching the wild body intended.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP FUNCTION IF EXISTS public.resolve_channel_tenant(text);")
    op.execute(
        """
        CREATE FUNCTION public.resolve_channel_tenant(candidate_phone text)
        RETURNS TABLE (tenant_id uuid, patient_id uuid)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT p.tenant_id, p.id
            FROM patients p
            WHERE (
                REPLACE(p.phone, '+', '') = REPLACE(candidate_phone, '+', '')
                OR RIGHT(REPLACE(p.phone, '+', ''), 10) = RIGHT(REPLACE(candidate_phone, '+', ''), 10)
            )
              AND p.active
            ORDER BY (REPLACE(p.phone, '+', '') = REPLACE(candidate_phone, '+', '')) DESC, p.created_at DESC
            LIMIT 1;
        $$;
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Restore the ORIGINAL 0003 definition (exact-match only).
    op.execute("DROP FUNCTION IF EXISTS public.resolve_channel_tenant(text);")
    op.execute(
        """
        CREATE FUNCTION public.resolve_channel_tenant(phone text)
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