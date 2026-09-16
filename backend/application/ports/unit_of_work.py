"""UnitOfWork outbound port (Gate 04).

Represents the transaction boundary. A use case:

1. reaches repository contracts through ``unit_of_work.<repo>``,
2. orchestrates domain behavior,
3. commits atomically, or
4. rolls back without leaving any partial state behind.

The concrete transaction implementation (PostgreSQL later) must NOT exist in
Gate 04. Tests use an in-memory fake.
"""

from typing import Protocol, runtime_checkable

from .repositories import (
    AIReviewArtifactRepository,
    CareTaskRepository,
    CareTeamMemberRepository,
    CaregiverRelationshipRepository,
    GlucoseObservationRepository,
    IdentityPatientMappingRepository,
    MealObservationRepository,
    MedicationPlanRepository,
    PatientRepository,
)


@runtime_checkable
class UnitOfWork(Protocol):
    patients: PatientRepository
    care_team_members: CareTeamMemberRepository
    glucose_observations: GlucoseObservationRepository
    meal_observations: MealObservationRepository
    medication_plans: MedicationPlanRepository
    care_tasks: CareTaskRepository
    ai_artifacts: AIReviewArtifactRepository
    caregiver_relationships: CaregiverRelationshipRepository
    identity_mappings: IdentityPatientMappingRepository

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None:
        """Release the underlying transaction resources (no-op for in-memory fakes)."""