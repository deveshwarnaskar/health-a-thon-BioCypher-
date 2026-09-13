"""Persistence layer (Gate 05).

Provides SQLAlchemy 2.x persistence models, repository implementations,
Unit of Work coordination, and transactional outbox.
"""

from .models import (
    AIReviewArtifactModel,
    Base,
    CareTaskModel,
    CareTeamMemberModel,
    DomainEventOutboxModel,
    FacilityModel,
    GlucoseObservationModel,
    MealObservationModel,
    MedicationPlanModel,
    OrganizationModel,
    PatientModel,
)
from .repositories import (
    SqlAlchemyAIReviewArtifactRepository,
    SqlAlchemyCareTaskRepository,
    SqlAlchemyCareTeamMemberRepository,
    SqlAlchemyGlucoseObservationRepository,
    SqlAlchemyMealObservationRepository,
    SqlAlchemyMedicationPlanRepository,
    SqlAlchemyPatientRepository,
)
from .uow import SqlAlchemyOutboxDomainEventPublisher, SqlAlchemyUnitOfWork

__all__ = [
    "Base",
    "OrganizationModel",
    "FacilityModel",
    "PatientModel",
    "CareTeamMemberModel",
    "GlucoseObservationModel",
    "MealObservationModel",
    "MedicationPlanModel",
    "CareTaskModel",
    "AIReviewArtifactModel",
    "DomainEventOutboxModel",
    "SqlAlchemyPatientRepository",
    "SqlAlchemyCareTeamMemberRepository",
    "SqlAlchemyGlucoseObservationRepository",
    "SqlAlchemyMealObservationRepository",
    "SqlAlchemyMedicationPlanRepository",
    "SqlAlchemyCareTaskRepository",
    "SqlAlchemyAIReviewArtifactRepository",
    "SqlAlchemyUnitOfWork",
    "SqlAlchemyOutboxDomainEventPublisher",
]