"""Query contracts (Gate 04).

Read-side input spells. Metric/report queries remain contracts only until the
deterministic-analytics gate; the observation feeds are implemented now.
"""

from .compute_window_metrics import ComputeWindowMetrics
from .get_clinical_observation_feed import GetClinicalObservationFeed
from .get_patient_observation_feed import GetPatientObservationFeed
from .get_live_inbound import GetLiveInbound
from .build_clinical_report_context import BuildClinicalReportContext

__all__ = [
    "ComputeWindowMetrics",
    "BuildClinicalReportContext",
    "GetLiveInbound",
    "GetPatientObservationFeed",
    "GetClinicalObservationFeed",
]