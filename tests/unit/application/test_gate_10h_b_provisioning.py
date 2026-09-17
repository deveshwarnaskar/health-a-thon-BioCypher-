"""Gate 10H-B provisioning application tests (in-memory).

No network, no database. Proves the two new provisioning use cases:
CreatePatient and AddCareTeamMember — canonical event publication, entity
persistence, and structural validation boundaries. Self-contained fixtures;
the shared unit test world is untouched.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.application.commands import AddCareTeamMember, CreatePatient
from backend.application.services.add_care_team_member import AddCareTeamMemberHandler
from backend.application.services.create_patient import CreatePatientHandler
from backend.domain.entities import CareTeamRole
from backend.domain.events import CareTeamMemberProvisioned, PatientProvisioned
from backend.domain.exceptions import DomainValidationError
from backend.domain.value_objects import UHID

from fakes import FakeClock, FakeEventPublisher, FakeIdGenerator, InMemoryUnitOfWork

FACILITY_ID = uuid4()
FIXED_NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)


class _App:
    def __init__(self, uow, events, clock, id_gen) -> None:
        self.create_patient = CreatePatientHandler(uow, events, clock, id_gen)
        self.add_care_team_member = AddCareTeamMemberHandler(uow, events, clock, id_gen)


@pytest.fixture
def app():
    uow = InMemoryUnitOfWork()
    events = FakeEventPublisher()
    clock = FakeClock(FIXED_NOW)
    id_gen = FakeIdGenerator(seed=5000)
    return {
        "uow": uow,
        "events": events,
        "clock": clock,
        "id_gen": id_gen,
        "app": _App(uow, events, clock, id_gen),
    }


class TestCreatePatient:
    def test_provisions_active_tenant_patient(self, app):
        cmd = CreatePatient(
            name="New Patient",
            facility_id=FACILITY_ID,
            correlation_id=uuid4(),
        )
        result = app["app"].create_patient.handle(cmd)
        assert result.name == "New Patient"
        assert result.facility_id == FACILITY_ID
        assert result.active is True
        assert result.uh_id == "UNASSIGNED"
        assert result.created_at == FIXED_NOW

        patient = app["uow"].patients.get(result.patient_id)
        assert patient.name == "New Patient"
        assert patient.facility_id == FACILITY_ID
        assert patient.active is True

        published = [e for e in app["events"].published if isinstance(e, PatientProvisioned)]
        assert len(published) == 1
        assert published[0].patient_id == result.patient_id
        assert published[0].correlation_id == cmd.correlation_id

    def test_custom_uhid_and_phone(self, app):
        from backend.domain.value_objects import PhoneNumber

        cmd = CreatePatient(
            name="Mapped Patient",
            facility_id=FACILITY_ID,
            uh_id=UHID("D-0100"),
            phone=PhoneNumber("+919000123456"),
        )
        result = app["app"].create_patient.handle(cmd)
        assert result.uh_id == "D-0100"
        patient = app["uow"].patients.get(result.patient_id)
        assert patient.uh_id.value == "D-0100"
        assert patient.phone.value == "+919000123456"

    def test_invalid_uhid_rejected_before_persist(self, app):
        with pytest.raises(DomainValidationError):
            UHID("x")
        assert app["uow"].commits == 0

    def test_commits_exactly_once_on_success(self, app):
        result = app["app"].create_patient.handle(
            CreatePatient(name="Clean", facility_id=FACILITY_ID)
        )
        assert app["uow"].commits == 1
        assert app["uow"].rollbacks == 0
        assert result.active is True


class TestAddCareTeamMember:
    def test_provisions_member_with_frozen_role(self, app):
        user_id = uuid4()
        cmd = AddCareTeamMember(
            user_id=user_id,
            role=CareTeamRole.NURSE,
            display_name="Nurse B",
            facility_id=FACILITY_ID,
            correlation_id=uuid4(),
        )
        result = app["app"].add_care_team_member.handle(cmd)
        assert result.user_id == user_id
        assert result.role == "nurse"
        assert result.display_name == "Nurse B"
        assert result.facility_id == FACILITY_ID
        assert result.active is True

        member = app["uow"].care_team_members.get(user_id)
        assert member.role is CareTeamRole.NURSE
        assert member.facility_id == FACILITY_ID
        assert member.active is True

        published = [e for e in app["events"].published if isinstance(e, CareTeamMemberProvisioned)]
        assert len(published) == 1
        assert published[0].correlation_id == cmd.correlation_id

    def test_provisioned_member_is_retrievable_by_user_id(self, app):
        user_id = uuid4()
        app["app"].add_care_team_member.handle(
            AddCareTeamMember(
                user_id=user_id,
                role=CareTeamRole.FIELD_HEALTH_WORKER,
                display_name="FHW",
                facility_id=FACILITY_ID,
            )
        )
        member = app["uow"].care_team_members.get(user_id)
        assert member.role is CareTeamRole.FIELD_HEALTH_WORKER

    def test_invalid_role_literal_rejected(self, app):
        with pytest.raises(ValueError):
            CareTeamRole("surgeon")