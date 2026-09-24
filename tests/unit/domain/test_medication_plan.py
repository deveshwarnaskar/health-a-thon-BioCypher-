"""Gate 03 — MedicationPlan clinician-authority invariant."""

from uuid import uuid4

import pytest

from backend.domain.entities import CareTeamMember, CareTeamRole, MedicationPlan
from backend.domain.exceptions import (
    UnauthorizedMedicationPlanMutation,
)


def _plan(role: CareTeamRole = CareTeamRole.DOCTOR) -> MedicationPlan:
    return MedicationPlan(
        patient_id=uuid4(),
        prescribed_by_user_id=uuid4(),
        prescribed_by_role=role,
        medication="Metformin 500 mg",
        instruction="One tablet after dinner",
    )


def test_clinician_roles_can_author():
    for role in (CareTeamRole.DOCTOR, CareTeamRole.NURSE, CareTeamRole.DIETITIAN):
        assert _plan(role).medication == "Metformin 500 mg"


def test_non_clinician_role_cannot_author():
    for role in (CareTeamRole.CARE_COORDINATOR, CareTeamRole.FIELD_HEALTH_WORKER):
        with pytest.raises(UnauthorizedMedicationPlanMutation):
            _plan(role)


def test_care_team_member_exposes_medication_authority():
    assert CareTeamMember(role=CareTeamRole.DOCTOR).role.can_author_medication is True
    assert (
        CareTeamMember(role=CareTeamRole.FIELD_HEALTH_WORKER).role.can_author_medication
        is False
    )


def test_ai_or_patient_cannot_modify_existing_plan():
    plan = _plan()
    with pytest.raises(UnauthorizedMedicationPlanMutation):
        plan.update_instruction(CareTeamRole.FIELD_HEALTH_WORKER, "changed")
    with pytest.raises(UnauthorizedMedicationPlanMutation):
        plan.deactivate(CareTeamRole.CARE_COORDINATOR)
    assert plan.active is True
    assert plan.instruction == "One tablet after dinner"


def test_clinician_can_modify_and_deactivate():
    plan = _plan()
    plan.update_instruction(CareTeamRole.DOCTOR, "Half tablet after dinner")
    assert plan.instruction == "Half tablet after dinner"
    plan.deactivate(CareTeamRole.DOCTOR)
    assert plan.active is False
    plan.reactivate(CareTeamRole.DOCTOR)
    assert plan.active is True