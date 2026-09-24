"""GetLiveInbound query placeholder (Gate 02B).

Target home for the live WhatsApp inbound feed currently exposed by
``app.server.main`` (``/api/v1/inbound/live``).
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class GetLiveInbound:
    query_id: UUID = field(default_factory=uuid4)
    facility_id: UUID | None = None
    limit: int = 50