"""DeactivateIdentityMapping command (Gate 08).

Administrator-managed deactivation of an identity-patient mapping. Deactivated
mappings deny patient self-access even if the row remains visible.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DeactivateIdentityMapping:
    mapping_id: UUID
    correlation_id: UUID | None = None