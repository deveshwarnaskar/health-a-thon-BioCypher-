"""Gate 10F-B — clinician read-contract handler tests.

Exercises the application-layer filters that back the four clinician read
families:

- AI review artifact queue + detail        (pending-review, facility, active)
- medication plan list + detail            (clinician-authored, facility, active)
- patient cohort list + detail             (facility, active)

Facility scoping and the deactivated-patient invariant are enforced HERE (the
application layer) so a route misconfiguration can never widen scope.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from backend.application.queries import (
    GetAIReviewArtifact,
    GetMedicationPlan,
    GetPatient,
    ListAIReviewArtifacts,
    ListMedicationPlans,
    ListPatients,
)
from backend.application.services import (
    GetAIReviewArtifactHandler,
    GetMedicationPlanHandler,
    GetPatientHandler,
    ListAIReviewArtifactsHandler,
    ListMedicationPlansHandler,
    ListPatientsHandler,
)
from backend.domain.entities import (
    AIReviewArtifact,
    CareTeamMember,
    CareTeamRole,
    MedicationPlan,
    Patient,
    ReviewState,
)
from backend.domain.exceptions import EntityNotFound
from backend.domain.value_objects import UHID

from tests.unit.application.fakes import InMemoryUnitOfWork

FAC_A = UUID("a0000000-0000-0000-0000-000000000001")
FAC_B = UUID("b0000000-0000-0000-0000-000000000002")

_T0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)


def _patient(id, facility_id=FAC_A, active=True, name="Pat"):
    return Patient(
        id=id,
        uh_id=UHID("D-0001"),
        name=name,
        facility_id=facility_id,
        active=active,
        created_at=_T0,
    )


def _artifact(id, patient_id, state=ReviewState.PENDING_REVIEW, created_at=_T0):
    return AIReviewArtifact(
        id=id,
        patient_id=patient_id,
        artifact_kind="extracted_observation",
        state=state,
        summary=f"summary {id}",
        created_at=created_at,
    )


def _plan(id, patient_id, active=True, created_at=_T0):
    return MedicationPlan(
        id=id,
        patient_id=patient_id,
        prescribed_by_user_id=uuid4(),
        prescribed_by_role=CareTeamRole.DOCTOR,
        medication="Metformin",
        instruction="500 mg with meals",
        active=active,
        created_at=created_at,
    )


def _member(user_id, facility_id=FAC_A):
    return CareTeamMember(
        id=uuid4(), user_id=user_id, role=CareTeamRole.DOCTOR, facility_id=facility_id
    )


def _world():
    uow = InMemoryUnitOfWork()
    uow.patients.add(_patient(UUID("10000000-0000-0000-0000-000000000001"), FAC_A))
    uow.patients.add(_patient(UUID("10000000-0000-0000-0000-000000000002"), FAC_A, active=False))
    uow.patients.add(_patient(UUID("10000000-0000-0000-0000-000000000003"), FAC_B))
    uow.care_team_members.add(_member(UUID("20000000-0000-0000-0000-000000000001"), FAC_A))
    uow.commit()
    return uow


def _seed_pending(uow, patient_id, created_at=_T0):
    artifact = _artifact(uuid4(), patient_id, created_at=created_at)
    uow.ai_artifacts.add(artifact)
    return artifact


class TestListAIReviewArtifacts:

    def test_only_pending_review_artifacts_surface(self):
        uow = _world()
        p1 = UUID("10000000-0000-0000-0000-000000000001")
        pending = _seed_pending(uow, p1)
        uow.ai_artifacts.add(_artifact(uuid4(), p1, state=ReviewState.APPROVED))
        uow.ai_artifacts.add(_artifact(uuid4(), p1, state=ReviewState.REJECTED))
        uow.ai_artifacts.add(_artifact(uuid4(), p1, state=ReviewState.GENERATED))
        uow.commit()
        result = ListAIReviewArtifactsHandler(uow).handle(ListAIReviewArtifacts(facility_id=FAC_A))
        assert result.artifact_count == 1
        assert result.items[0].artifact_id == pending.id
        assert result.items[0].state == "pending_review"

    def test_other_facility_patients_excluded(self):
        uow = _world()
        _seed_pending(uow, UUID("10000000-0000-0000-0000-000000000001"))  # FAC_A
        _seed_pending(uow, UUID("10000000-0000-0000-0000-000000000003"))  # FAC_B
        uow.commit()
        result = ListAIReviewArtifactsHandler(uow).handle(ListAIReviewArtifacts(facility_id=FAC_A))
        assert result.artifact_count == 1

    def test_deactivated_patient_artifacts_excluded(self):
        uow = _world()
        _seed_pending(uow, UUID("10000000-0000-0000-0000-000000000001"))  # active
        _seed_pending(uow, UUID("10000000-0000-0000-0000-000000000002"))  # inactive
        uow.commit()
        result = ListAIReviewArtifactsHandler(uow).handle(ListAIReviewArtifacts(facility_id=FAC_A))
        assert result.artifact_count == 1

    def test_limit_applied(self):
        uow = _world()
        p1 = UUID("10000000-0000-0000-0000-000000000001")
        _seed_pending(uow, p1, created_at=_T0)
        _seed_pending(uow, p1, created_at=_T1)
        uow.commit()
        result = ListAIReviewArtifactsHandler(uow).handle(
            ListAIReviewArtifacts(facility_id=FAC_A, limit=1)
        )
        assert result.artifact_count == 1

    def test_deterministic_ordering(self):
        uow = _world()
        p1 = UUID("10000000-0000-0000-0000-000000000001")
        first = _seed_pending(uow, p1, created_at=_T0)
        second = _seed_pending(uow, p1, created_at=_T1)
        uow.commit()
        result = ListAIReviewArtifactsHandler(uow).handle(ListAIReviewArtifacts(facility_id=FAC_A))
        assert [r.artifact_id for r in result.items] == [first.id, second.id]


class TestGetAIReviewArtifact:

    def test_resolves_own_facility_active_patient(self):
        uow = _world()
        p1 = UUID("10000000-0000-0000-0000-000000000001")
        artifact = _seed_pending(uow, p1)
        uow.commit()
        result = GetAIReviewArtifactHandler(uow).handle(
            GetAIReviewArtifact(artifact_id=artifact.id, facility_id=FAC_A)
        )
        assert result.artifact_id == artifact.id
        assert result.patient_id == p1

    def test_missing_artifact_raises(self):
        uow = _world()
        with pytest.raises(EntityNotFound):
            GetAIReviewArtifactHandler(uow).handle(
                GetAIReviewArtifact(artifact_id=uuid4(), facility_id=FAC_A)
            )

    def test_cross_facility_patient_raises(self):
        uow = _world()
        artifact = _seed_pending(uow, UUID("10000000-0000-0000-0000-000000000003"))  # FAC_B
        uow.commit()
        with pytest.raises(EntityNotFound):
            GetAIReviewArtifactHandler(uow).handle(
                GetAIReviewArtifact(artifact_id=artifact.id, facility_id=FAC_A)
            )

    def test_deactivated_patient_raises(self):
        uow = _world()
        artifact = _seed_pending(uow, UUID("10000000-0000-0000-0000-000000000002"))  # inactive
        uow.commit()
        with pytest.raises(EntityNotFound):
            GetAIReviewArtifactHandler(uow).handle(
                GetAIReviewArtifact(artifact_id=artifact.id, facility_id=FAC_A)
            )


class TestListMedicationPlans:

    def test_facility_scoped_and_active_only(self):
        uow = _world()
        p1 = UUID("10000000-0000-0000-0000-000000000001")
        p2 = UUID("10000000-0000-0000-0000-000000000002")  # inactive
        p3 = UUID("10000000-0000-0000-0000-000000000003")  # FAC_B
        plan_a = _plan(uuid4(), p1)
        uow.medication_plans.add(plan_a)
        uow.medication_plans.add(_plan(uuid4(), p2))
        uow.medication_plans.add(_plan(uuid4(), p3))
        uow.commit()
        result = ListMedicationPlansHandler(uow).handle(ListMedicationPlans(facility_id=FAC_A))
        assert result.plan_count == 1
        assert result.items[0].medication_plan_id == plan_a.id
        assert result.items[0].instruction == "500 mg with meals"

    def test_active_field_preserved(self):
        uow = _world()
        p1 = UUID("10000000-0000-0000-0000-000000000001")
        active = _plan(uuid4(), p1, active=True)
        inactive = _plan(uuid4(), p1, active=False)
        uow.medication_plans.add(active)
        uow.medication_plans.add(inactive)
        uow.commit()
        result = ListMedicationPlansHandler(uow).handle(ListMedicationPlans(facility_id=FAC_A))
        assert result.plan_count == 2
        assert {r.active for r in result.items} == {True, False}

    def test_limit_applied(self):
        uow = _world()
        p1 = UUID("10000000-0000-0000-0000-000000000001")
        uow.medication_plans.add(_plan(uuid4(), p1, created_at=_T0))
        uow.medication_plans.add(_plan(uuid4(), p1, created_at=_T1))
        uow.commit()
        result = ListMedicationPlansHandler(uow).handle(ListMedicationPlans(facility_id=FAC_A, limit=1))
        assert result.plan_count == 1


class TestGetMedicationPlan:

    def test_resolves_own_facility(self):
        uow = _world()
        p1 = UUID("10000000-0000-0000-0000-000000000001")
        plan = _plan(uuid4(), p1)
        uow.medication_plans.add(plan)
        uow.commit()
        result = GetMedicationPlanHandler(uow).handle(
            GetMedicationPlan(plan_id=plan.id, facility_id=FAC_A)
        )
        assert result.medication_plan_id == plan.id

    def test_missing_raises(self):
        uow = _world()
        with pytest.raises(EntityNotFound):
            GetMedicationPlanHandler(uow).handle(
                GetMedicationPlan(plan_id=uuid4(), facility_id=FAC_A)
            )

    def test_cross_facility_raises(self):
        uow = _world()
        plan = _plan(uuid4(), UUID("10000000-0000-0000-0000-000000000003"))  # FAC_B
        uow.medication_plans.add(plan)
        uow.commit()
        with pytest.raises(EntityNotFound):
            GetMedicationPlanHandler(uow).handle(
                GetMedicationPlan(plan_id=plan.id, facility_id=FAC_A)
            )


class TestListPatients:

    def test_active_facility_cohort_only(self):
        uow = _world()
        result = ListPatientsHandler(uow).handle(ListPatients(facility_id=FAC_A))
        assert result.patient_count == 1
        assert result.items[0].patient_id == UUID("10000000-0000-0000-0000-000000000001")
        assert result.items[0].uh_id == "D-0001"
        assert result.items[0].facility_id == FAC_A

    def test_no_phone_in_record(self):
        uow = _world()
        result = ListPatientsHandler(uow).handle(ListPatients(facility_id=FAC_A))
        record = result.items[0]
        assert not hasattr(record, "phone")

    def test_limit_applied(self):
        uow = _world()
        uow.patients.add(_patient(UUID("10000000-0000-0000-0000-000000000004"), FAC_A))
        uow.commit()
        result = ListPatientsHandler(uow).handle(ListPatients(facility_id=FAC_A, limit=1))
        assert result.patient_count == 1


class TestGetPatient:

    def test_resolves_own_facility_active_patient(self):
        uow = _world()
        pid = UUID("10000000-0000-0000-0000-000000000001")
        result = GetPatientHandler(uow).handle(GetPatient(patient_id=pid, facility_id=FAC_A))
        assert result.patient_id == pid
        assert result.name == "Pat"

    def test_missing_raises(self):
        uow = _world()
        with pytest.raises(EntityNotFound):
            GetPatientHandler(uow).handle(GetPatient(patient_id=uuid4(), facility_id=FAC_A))

    def test_cross_facility_raises(self):
        uow = _world()
        with pytest.raises(EntityNotFound):
            GetPatientHandler(uow).handle(
                GetPatient(patient_id=UUID("10000000-0000-0000-0000-000000000003"), facility_id=FAC_A)
            )

    def test_deactivated_raises(self):
        uow = _world()
        with pytest.raises(EntityNotFound):
            GetPatientHandler(uow).handle(
                GetPatient(patient_id=UUID("10000000-0000-0000-0000-000000000002"), facility_id=FAC_A)
            )