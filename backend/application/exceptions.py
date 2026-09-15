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