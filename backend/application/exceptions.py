"""Application-layer exceptions (Gate 04).

Kept deliberately small. Where the domain already owns an invariant or an
error type, the application re-raises/propagates the DOMAIN error unchanged —
the application does not duplicate domain errors. This module only hosts
application-policy errors that have no domain home yet (e.g. reviewer
authorization for clinician review of AI artifacts).
"""


class ApplicationError(Exception):
    """Base class for application-layer policy errors."""


class ReviewerNotAuthorized(ApplicationError):
    """An actor attempted a CLINICIAN review without a licensed clinical role."""


class DuplicateIdentityMapping(ApplicationError):
    """An active identity-patient mapping already binds this user or patient."""


class DuplicateCaregiverRelationship(ApplicationError):
    """A non-revoked caregiver relationship already exists for this pair."""


class DuplicateCareTeamMember(ApplicationError):
    """A care team member already exists for this user in this tenant."""


class AIGenerationFailed(ApplicationError):
    """Underlying AI provider failed to generate output safely."""

    def __init__(self, error_code: str | None = None, retryable: bool = False, message: str = "") -> None:
        super().__init__(message or f"AI generation failed: {error_code}")
        self.error_code = error_code or "AI_GENERATION_FAILED"
        self.retryable = retryable


class InactivePatientError(ApplicationError):
    """Operation requested on a deactivated patient."""


class InvalidReportFormatError(ApplicationError):
    """Unsupported report format or report type requested."""


class ClinicianUnavailable(ApplicationError):
    """The target clinician user is inactive, suspended, or not authorized
    to accept patient links at this time."""