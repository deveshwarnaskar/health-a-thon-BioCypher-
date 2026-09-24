"""Persistence models package (Gate 05).

Exports DeclarativeBase and all relational infrastructure models.
"""

from .base import Base
from .tenant_models import FacilityModel, OrganizationModel
from .identity_models import (
    CaregiverRelationshipModel,
    IdentityPatientMappingModel,
    PatientClinicianLinkModel,
)
from .patient_models import PatientModel
from .clinician_models import CareTeamMemberModel
from .observation_models import ClinicalObservationModel, GlucoseObservationModel, MealObservationModel
from .plan_models import CareTaskModel, MedicationPlanModel
from .ai_models import AIReviewArtifactModel
from .outbox_models import DomainEventOutboxModel
from .ops_models import AuditEventModel, IdempotencyRecordModel, WebhookReceiptModel
from .notification_models import NotificationModel
from .document_models import DocumentReferenceModel
from .conversation_models import ConversationSessionModel, PatientChannelPrefModel
from .user_models import (
    EmailVerificationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenFamilyModel,
    SecurityEventModel,
    UserModel,
    UserSessionModel,
    UserStatus,
)

__all__ = [
    "Base",
    "OrganizationModel",
    "FacilityModel",
    "PatientModel",
    "CareTeamMemberModel",
    "CaregiverRelationshipModel",
    "IdentityPatientMappingModel",
    "PatientClinicianLinkModel",
    "ClinicalObservationModel",
    "GlucoseObservationModel",
    "MealObservationModel",
    "MedicationPlanModel",
    "CareTaskModel",
    "AIReviewArtifactModel",
    "DomainEventOutboxModel",
    "IdempotencyRecordModel",
    "WebhookReceiptModel",
    "AuditEventModel",
    "NotificationModel",
    "DocumentReferenceModel",
    "ConversationSessionModel",
    "PatientChannelPrefModel",
    "UserModel",
    "UserSessionModel",
    "RefreshTokenFamilyModel",
    "PasswordResetTokenModel",
    "EmailVerificationTokenModel",
    "SecurityEventModel",
    "UserStatus",
]
