"""ComputeWindowMetrics query placeholder (Gate 02B).

Target home for TIR, adherence, meal-slot chronobiology, CVI, and Pearson
correlation currently implemented in ``app/core/metrics.py``.
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ComputeWindowMetrics:
    query_id: UUID = field(default_factory=uuid4)
    patient_profile_id: UUID | None = None
    window_id: UUID | None = None