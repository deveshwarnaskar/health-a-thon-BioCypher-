"""Gate 04 — medication authority enforcement.

CreateMedicationPlan is clinician-authorized only. No patient/caregiver/AI/
automated model path may create a plan. RecordMedicationAdministration is a
distinct patient-side adherence operation that never touches the plan.
"""

from datetime import datetime, timezone

import pytest

from backend.application.commands import (
    CreateMedicationPlan,
    RecordMedicationAdministration,
)
from backend.domain.entities import CareTeamRole
from backend.domain.events import MedicationAdministrationRecorded
from backend.domain.exceptions import (
    EntityNotFound,
    UnauthorizedMedicationPlanMutation,
)
from backend.domain.value_objects import PhoneNumber

NOW = datetime(2026, 9, 1, 7, 30, tzinfo=timezone.utc)


def test_licensed_clinician_can_create_plan(world):
    uow, app, patient_id = world["uow"], world["app"], world["patient_id"]

    result = app.create_medication_plan.handle(
        CreateMedicationPlan(
            patient_id=patient_id,
            prescribed_by_user_id=world["doctor_user_id"],
            medication="Metformin 500 mg",
            instruction="One tablet after dinner",
        )
    )

    plan = uow.medication_plans.get(result.medication_plan_id)
    assert plan.prescribed_by_role == CareTeamRole.DOCTOR
    assert plan.patient_id == patient_id
    assert uow.commits == 1


def test_non_clinician_cannot_create_plan(world):
    uow, app, patient_id = world["uow"], world["app"], world["patient_id"]

    with pytest.raises(UnauthorizedMedicationPlanMutation):
        app.create_medication_plan.handle(
            CreateMedicationPlan(
                patient_id=patient_id,
                prescribed_by_user_id=world["coordinator_user_id"],
                medication="Metformin 500 mg",
                instruction="One tablet after dinner",
            )
        )

    assert uow.rollbacks == 1
    assert uow.commits == 0
    assert uow.medication_plans.list_for_patient(patient_id) == []


def test_unknown_actor_cannot_create_plan(world):
    """A patient/profile identifier is NOT an accepted prescriber source."""
    from uuid import UUID

    uow, app, patient_id = world["uow"], world["app"], world["patient_id"]

    with pytest.raises(EntityNotFound):
        app.create_medication_plan.handle(
            CreateMedicationPlan(
                patient_id=patient_id,
                prescribed_by_user_id=UUID("99999999-0000-0000-0000-000000000001"),
                medication="Metformin 500 mg",
                instruction="One tablet after dinner",
            )
        )

    assert uow.rollbacks == 1
    assert uow.medication_plans.list_for_patient(patient_id) == []


def test_nurse_and_dietitian_can_create_plan(world):
    from backend.application.commands import CreateMedicationPlan
    from backend.domain.entities import CareTeamMember, CareTeamRole

    uow = world["uow"]
    dietitian = CareTeamMember(
        user_id=world["id_gen"].new_uuid(),
        role=CareTeamRole.DIETITIAN,
        display_name="Dietitian D",
    )
    uow.care_team_members.add(dietitian)
    uow.commit()

    for user_id in (
        world["nurse_user_id"],
        dietitian.user_id,
    ):
        result = world["app"].create_medication_plan.handle(
            CreateMedicationPlan(
                patient_id=world["patient_id"],
                prescribed_by_user_id=user_id,
                medication="Metformin 500 mg",
                instruction="One tablet after dinner",
            )
        )
        assert uow.medication_plans.get(result.medication_plan_id).active is True


def test_field_health_worker_cannot_create_plan(world):
    from backend.domain.entities import CareTeamMember, CareTeamRole

    uow = world["uow"]
    field_worker = CareTeamMember(
        user_id=world["id_gen"].new_uuid(),
        role=CareTeamRole.FIELD_HEALTH_WORKER,
        display_name="FHW E",
    )
    uow.care_team_members.add(field_worker)
    uow.commit()

    with pytest.raises(UnauthorizedMedicationPlanMutation):
        world["app"].create_medication_plan.handle(
            CreateMedicationPlan(
                patient_id=world["patient_id"],
                prescribed_by_user_id=field_worker.user_id,
                medication="Metformin 500 mg",
                instruction="One tablet after dinner",
            )
        )

    assert uow.rollbacks >= 1


def test_patient_administration_is_distinct_from_plan_creation(world):
    """Recording administration must never create or modify a plan."""
    uow, events, app = world["uow"], world["events"], world["app"]
    plan_result = app.create_medication_plan.handle(
        CreateMedicationPlan(
            patient_id=world["patient_id"],
            prescribed_by_user_id=world["doctor_user_id"],
            medication="Metformin 500 mg",
            instruction="One tablet after dinner",
        )
    )
    plan_before = uow.medication_plans.get(plan_result.medication_plan_id)

    result = app.record_medication_administration.handle(
        RecordMedicationAdministration(
            medication_plan_id=plan_result.medication_plan_id,
            administered_at=NOW,
            recorded_by=PhoneNumber("+919000000001"),
        )
    )

    assert result.medication_plan_id == plan_result.medication_plan_id
    plans = uow.medication_plans.list_for_patient(world["patient_id"])
    assert len(plans) == 1
    plan_after = plans[0]
    assert plan_after.instruction == plan_before.instruction
    assert plan_after.active is True
    assert plan_after.prescribed_by_role == CareTeamRole.DOCTOR

    admin_events = [e for e in events.published if isinstance(e, MedicationAdministrationRecorded)]
    assert len(admin_events) == 1
    assert admin_events[0].medication_plan_id == plan_result.medication_plan_id


def test_administration_requires_active_plan(world):
    from backend.domain.exceptions import DomainValidationError

    uow, app = world["uow"], world["app"]
    plan_result = app.create_medication_plan.handle(
        CreateMedicationPlan(
            patient_id=world["patient_id"],
            prescribed_by_user_id=world["doctor_user_id"],
            medication="Metformin 500 mg",
            instruction="One tablet after dinner",
        )
    )
    plan = uow.medication_plans.get(plan_result.medication_plan_id)
    plan.deactivate(CareTeamRole.DOCTOR)
    uow.medication_plans.save(plan)
    uow.commit()

    with pytest.raises(DomainValidationError):
        app.record_medication_administration.handle(
            RecordMedicationAdministration(
                medication_plan_id=plan_result.medication_plan_id,
                administered_at=NOW,
                recorded_by=PhoneNumber("+919000000001"),
            )
        )

    assert uow.commits == 2
    assert uow.rollbacks == 1