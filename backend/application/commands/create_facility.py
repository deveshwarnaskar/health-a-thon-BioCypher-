"""CreateFacility command contract (Gate 10K-B)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CreateFacility:
    name: str
    correlation_id: UUID | None = None
