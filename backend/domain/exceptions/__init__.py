"""Domain exceptions (Gate 03).

A small hierarchy reserved for genuine domain-invariant violations. Generic
"catch-all" exceptions are avoided.
"""


class DomainError(Exception):
    """Base class for all domain-layer errors."""


class DomainValidationError(DomainError):
    """Raised when a structural invariant is violated."""


class EntityNotFound(DomainError):
    """Raised when an aggregate cannot be located."""


class InvalidGlucoseValue(DomainValidationError):
    """Glucose value outside the safe parse boundary 20-600 mg/dL."""


class InvalidKatoriVolume(DomainValidationError):
    """Katori volume not in the canonical household set {150, 220, 350} ml."""


class InvalidPhoneNumber(DomainValidationError):
    """Phone representation fails structural validation or normalization."""


class InvalidStateTransition(DomainValidationError):
    """A domain state machine rejected the requested transition."""


class InvalidRelationship(DomainValidationError):
    """A role/binding relationship is invalid (e.g. revoked twice)."""


class UnauthorizedMedicationPlanMutation(DomainError):
    """Attempt to create or modify a MedicationPlan by a non-clinician or by AI."""


class UnknownFoodItemError(DomainValidationError):
    """Food item is not recognized in the standard nutrition catalog."""


class InvalidPortionQuantityError(DomainValidationError):
    """Portion quantity must be strictly positive."""