"""Administrative result DTOs (Gate 10K-B).

PHI-minimized operational data transfer objects returned by administrative use cases.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class FacilityResult:
    facility_id: UUID
    tenant_id: UUID
    name: str
    active: bool
    created_at: datetime


@dataclass(frozen=True)
class FacilityListResult:
    items: list[FacilityResult]
    total: int


@dataclass(frozen=True)
class CareTeamMemberResult:
    member_id: UUID
    user_id: UUID
    role: str
    display_name: str
    facility_id: UUID | None
    active: bool


@dataclass(frozen=True)
class CareTeamMemberListResult:
    items: list[CareTeamMemberResult]
    total: int


@dataclass(frozen=True)
class AdminPatientSummaryResult:
    patient_id: UUID
    uh_id: str
    name: str
    facility_id: UUID | None
    phone: str | None
    active: bool
    has_active_mapping: bool
    created_at: datetime


@dataclass(frozen=True)
class AdminPatientListResult:
    items: list[AdminPatientSummaryResult]
    total: int
