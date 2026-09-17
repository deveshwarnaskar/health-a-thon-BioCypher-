"""BuildClinicalReportContext query (Gate 02B, extended Gate 10N).

Aggregates patient glycemic observations, meals, medication plans, care tasks,
and AI review artifacts into a structured report context.
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class BuildClinicalReportContext:
    query_id: UUID = field(default_factory=uuid4)
    patient_id: UUID | None = None
    facility_id: UUID | None = None
    report_type: str = "clinical_summary"  # "clinical_summary" or "patient_summary"