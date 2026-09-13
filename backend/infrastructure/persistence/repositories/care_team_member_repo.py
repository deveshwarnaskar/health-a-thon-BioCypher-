"""SqlAlchemyCareTeamMemberRepository (Gate 05).

Concrete infrastructure implementation of CareTeamMemberRepository port.
Looks up care team members by their authoritative user_id under the active tenant.
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities import CareTeamMember
from backend.domain.exceptions import EntityNotFound
from ..mappings.mappers import care_team_member_to_domain, care_team_member_to_model
from ..models.clinician_models import CareTeamMemberModel


class SqlAlchemyCareTeamMemberRepository:
    """SQLAlchemy-backed repository for CareTeamMember entities."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyCareTeamMemberRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, member: CareTeamMember) -> None:
        model = care_team_member_to_model(member, self.tenant_id)
        self.session.add(model)

    def get(self, user_id: UUID) -> CareTeamMember:
        stmt = select(CareTeamMemberModel).where(
            CareTeamMemberModel.user_id == user_id,
            CareTeamMemberModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"care_team_member with user_id {user_id} not found")
        return care_team_member_to_domain(model)

    def list(self) -> list[CareTeamMember]:
        stmt = (
            select(CareTeamMemberModel)
            .where(CareTeamMemberModel.tenant_id == self.tenant_id)
            .order_by(CareTeamMemberModel.id)
        )
        return [care_team_member_to_domain(m) for m in self.session.scalars(stmt).all()]
