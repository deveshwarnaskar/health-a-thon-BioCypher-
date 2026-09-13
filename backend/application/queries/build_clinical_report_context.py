"""BuildClinicalReportContext query placeholder (Gate 02B).

Target home for the two-page lab-grade clinical report aggregation currently
implemented in ``app/core/report.py`` + ``app/report/*``.
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class BuildClinicalReportContext:
    query_id: UUID = field(default_factory=uuid4)
    patient_id: UUID | None = None
    window_id: UUID | None = None