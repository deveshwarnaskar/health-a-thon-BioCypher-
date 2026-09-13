"""Organization entity placeholder (Gate 02B)."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Organization:
    id: UUID
    name: str
    tenant_key: str
    created_at: datetime = field(default_factory=datetime.utcnow)