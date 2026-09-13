"""Domain exceptions (Gate 02B placeholders)."""


class DomainError(Exception):
    """Base class for all domain-layer errors."""


class EntityNotFound(DomainError):
    """Raised when an aggregate cannot be located."""


class DomainValidationError(DomainError):
    """Raised when a domain invariant is violated."""