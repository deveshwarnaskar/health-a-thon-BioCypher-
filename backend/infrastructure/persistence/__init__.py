"""Persistence layer (Gate 05, extended Gate 09).

Provides SQLAlchemy 2.x persistence models, repository implementations,
Unit of Work coordination, transactional outbox, and the Gate 09 operational
stores (idempotency, provider replay, immutable audit, outbox worker, channel
tenant resolution).
"""

from .models import (
    AIReviewArtifactModel,
    AuditEventModel,
    Base,
    CareTaskModel,
    CareTeamMemberModel,
    DomainEventOutboxModel,
    FacilityModel,
    GlucoseObservationModel,
    IdempotencyRecordModel,
    MealObservationModel,
    MedicationPlanModel,
    OrganizationModel,
    PatientModel,
    WebhookReceiptModel,
)
from .repositories import (
    SqlAlchemyAIReviewArtifactRepository,
    SqlAlchemyCareTaskRepository,
    SqlAlchemyCareTeamMemberRepository,
    SqlAlchemyFacilityRepository,
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
    "IdempotencyRecordModel",
    "WebhookReceiptModel",
    "AuditEventModel",
    "SqlAlchemyPatientRepository",
    "SqlAlchemyFacilityRepository",
    "SqlAlchemyCareTeamMemberRepository",
    "SqlAlchemyGlucoseObservationRepository",
    "SqlAlchemyMealObservationRepository",
    "SqlAlchemyMedicationPlanRepository",
    "SqlAlchemyCareTaskRepository",
    "SqlAlchemyAIReviewArtifactRepository",
    "SqlAlchemyUnitOfWork",
    "SqlAlchemyOutboxDomainEventPublisher",
]