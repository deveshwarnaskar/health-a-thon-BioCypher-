"""SqlAlchemyUnitOfWork (Gate 05).

Concrete infrastructure implementation of the application UnitOfWork port.
Coordinates repository transactions, session lifecycle, and multi-tenant RLS context.
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from ..repositories import (
    SqlAlchemyAIReviewArtifactRepository,
    SqlAlchemyCareTaskRepository,
    SqlAlchemyCareTeamMemberRepository,
    SqlAlchemyCaregiverRelationshipRepository,
    SqlAlchemyGlucoseObservationRepository,
    SqlAlchemyIdentityPatientMappingRepository,
    SqlAlchemyMealObservationRepository,
    SqlAlchemyMedicationPlanRepository,
    SqlAlchemyPatientRepository,
)


class SqlAlchemyUnitOfWork:
    """SQLAlchemy implementation of the transaction boundary."""

    def __init__(
        self,
        session_factory_or_session: sessionmaker[Session] | Session,
        tenant_id: UUID,
    ) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyUnitOfWork")

        self.tenant_id = tenant_id

        if isinstance(session_factory_or_session, Session):
            self.session = session_factory_or_session
            self._owns_session = False
        else:
            self.session = session_factory_or_session()
            self._owns_session = True

        self._init_repositories()
        self._apply_tenant_context()

    def _init_repositories(self) -> None:
        self.patients = SqlAlchemyPatientRepository(self.session, self.tenant_id)
        self.care_team_members = SqlAlchemyCareTeamMemberRepository(self.session, self.tenant_id)
        self.caregiver_relationships = SqlAlchemyCaregiverRelationshipRepository(self.session, self.tenant_id)
        self.identity_mappings = SqlAlchemyIdentityPatientMappingRepository(self.session, self.tenant_id)
        self.glucose_observations = SqlAlchemyGlucoseObservationRepository(self.session, self.tenant_id)
        self.meal_observations = SqlAlchemyMealObservationRepository(self.session, self.tenant_id)
        self.medication_plans = SqlAlchemyMedicationPlanRepository(self.session, self.tenant_id)
        self.care_tasks = SqlAlchemyCareTaskRepository(self.session, self.tenant_id)
        self.ai_artifacts = SqlAlchemyAIReviewArtifactRepository(self.session, self.tenant_id)

    def _apply_tenant_context(self) -> None:
        """Set local session configuration for PostgreSQL RLS if dialect is postgresql."""
        bind = self.session.get_bind()
        if bind and bind.dialect.name == "postgresql":
            # set_config accepts parameters safely, 3rd arg is_local=true
            self.session.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(self.tenant_id)},
            )

    def commit(self) -> None:
        """Commit the current database transaction."""
        self.session.commit()

    def rollback(self) -> None:
        """Rollback the current database transaction."""
        self.session.rollback()

    def close(self) -> None:
        """Close the current session if owned."""
        if self._owns_session:
            self.session.close()

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self._apply_tenant_context()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            if exc_type is not None:
                self.rollback()
        finally:
            if self._owns_session:
                self.close()
