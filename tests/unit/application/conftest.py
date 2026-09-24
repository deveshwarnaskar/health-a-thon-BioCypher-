"""Shared world + handler wiring for Gate 04 application tests."""

from __future__ import annotations

from uuid import UUID

import pytest

from backend.application.services import (
    CompleteCareTaskHandler,
    ConfirmMealObservationHandler,
    CreateCareTaskHandler,
    CreateIdentityMappingHandler,
    CreateMedicationPlanHandler,
    DeactivateIdentityMappingHandler,
    GenerateAIReviewArtifactHandler,
    GetClinicalObservationFeedHandler,
    GetPatientObservationFeedHandler,
    IdentityPatientResolver,
    IngestGlucoseHandler,
    LinkPatientPhoneHandler,
    LogMealDraftHandler,
    RecordMedicationAdministrationHandler,
    RegisterCaregiverHandler,
    ReviewAIArtifactHandler,
    RevokeCaregiverHandler,
    VerifyCaregiverHandler,
)
from backend.domain.entities import CareTeamRole

from tests.unit.application.fakes import (
    FakeAIArtifactGenerator,
    FakeClock,
    FakeEventPublisher,
    FakeIdGenerator,
    InMemoryUnitOfWork,
    seed_member,
    seed_patient,
)

PATIENT_ID = UUID("10000000-0000-0000-0000-000000000001")
DOCTOR_MEMBER_ID = UUID("20000000-0000-0000-0000-000000000001")
DOCTOR_USER_ID = UUID("20000000-0000-0000-0000-000000000002")
NURSE_MEMBER_ID = UUID("20000000-0000-0000-0000-000000000003")
NURSE_USER_ID = UUID("20000000-0000-0000-0000-000000000004")
COORD_MEMBER_ID = UUID("20000000-0000-0000-0000-000000000005")
COORD_USER_ID = UUID("20000000-0000-0000-0000-000000000006")


class App:
    def __init__(self, uow, events, clock, id_gen, ai) -> None:
        self.ingest_glucose = IngestGlucoseHandler(uow, events, clock, id_gen)
        self.link_patient_phone = LinkPatientPhoneHandler(uow)
        self.log_meal_draft = LogMealDraftHandler(uow, events, clock, id_gen)
        self.confirm_meal_observation = ConfirmMealObservationHandler(uow, events, clock, id_gen)
        self.record_medication_administration = RecordMedicationAdministrationHandler(
            uow, events, clock, id_gen
        )
        self.create_care_task = CreateCareTaskHandler(uow, events, clock, id_gen)
        self.complete_care_task = CompleteCareTaskHandler(uow, events, clock, id_gen)
        self.create_medication_plan = CreateMedicationPlanHandler(uow, clock, id_gen)
        self.generate_ai_artifact = GenerateAIReviewArtifactHandler(uow, events, ai, clock, id_gen)
        self.review_ai_artifact = ReviewAIArtifactHandler(uow, events, clock, id_gen)
        self.patient_feed = GetPatientObservationFeedHandler(uow)
        self.clinical_feed = GetClinicalObservationFeedHandler(uow)
        self.register_caregiver = RegisterCaregiverHandler(uow, events, clock, id_gen)
        self.verify_caregiver = VerifyCaregiverHandler(uow, events, clock, id_gen)
        self.revoke_caregiver = RevokeCaregiverHandler(uow, events, clock, id_gen)
        self.create_identity_mapping = CreateIdentityMappingHandler(uow, events, clock, id_gen)
        self.deactivate_identity_mapping = DeactivateIdentityMappingHandler(uow, events, clock, id_gen)
        self.identity_resolver = IdentityPatientResolver(uow)


@pytest.fixture
def world():
    """A seeded in-memory world: committed patient + clinician members, and
    handlers wired with deterministic clock/id/AI fakes."""
    uow = InMemoryUnitOfWork()
    events = FakeEventPublisher()
    clock = FakeClock()
    id_gen = FakeIdGenerator(seed=1000)
    ai = FakeAIArtifactGenerator()

    seed_patient(uow, PATIENT_ID)
    seed_member(uow, DOCTOR_MEMBER_ID, DOCTOR_USER_ID, CareTeamRole.DOCTOR, name="Dr A")
    seed_member(uow, NURSE_MEMBER_ID, NURSE_USER_ID, CareTeamRole.NURSE, name="Nurse B")
    seed_member(uow, COORD_MEMBER_ID, COORD_USER_ID, CareTeamRole.CARE_COORDINATOR, name="Coord C")

    uow.commit()
    uow.commits = 0
    uow.rollbacks = 0

    app = App(uow, events, clock, id_gen, ai)

    return {
        "uow": uow,
        "events": events,
        "clock": clock,
        "id_gen": id_gen,
        "ai": ai,
        "app": app,
        "patient_id": PATIENT_ID,
        "doctor_user_id": DOCTOR_USER_ID,
        "nurse_user_id": NURSE_USER_ID,
        "coordinator_user_id": COORD_USER_ID,
    }