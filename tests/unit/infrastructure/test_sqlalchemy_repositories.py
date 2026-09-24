"""Tests for SQLAlchemy concrete repository implementations (Gate 05).

Verifies:
1. All 7 repositories fulfill Gate 04 repository protocols.
2. Correct CRUD persistence and retrieval.
3. EntityNotFound is raised consistently for missing records.
4. No ORM models leak through repository boundaries.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.domain.entities import (
    AIReviewArtifact,
    CareTask,
    CareTeamMember,
    CareTeamRole,
    CareTaskStatus,
    GlucoseObservation,
    MealObservation,
    MedicationPlan,
    Patient,
)
from backend.domain.exceptions import EntityNotFound
from backend.domain.value_objects import (
    GlucoseValue,
    KatoriVolume,
    MealPortion,
    PatientConfirmationState,
    PhoneNumber,
    ReadingTag,
    UHID,
)
from backend.infrastructure.persistence.models import Base, OrganizationModel
from backend.infrastructure.persistence.repositories import (
    SqlAlchemyAIReviewArtifactRepository,
    SqlAlchemyCareTaskRepository,
    SqlAlchemyCareTeamMemberRepository,
    SqlAlchemyGlucoseObservationRepository,
    SqlAlchemyMealObservationRepository,
    SqlAlchemyMedicationPlanRepository,
    SqlAlchemyPatientRepository,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()

    # Seed default tenant organization
    tenant_id = uuid4()
    org = OrganizationModel(
        id=tenant_id,
        name="Test Hospital",
        slug="test-hospital",
        created_at=datetime.now(timezone.utc),
    )
    session.add(org)
    session.commit()

    yield session, tenant_id

    session.close()
    Base.metadata.drop_all(engine)


def test_patient_repository_crud(db_session):
    session, tenant_id = db_session
    repo = SqlAlchemyPatientRepository(session, tenant_id)

    patient_id = uuid4()
    patient = Patient(
        id=patient_id,
        uh_id=UHID("UHID-100"),
        name="Rajesh Patel",
        phone=PhoneNumber("+919000000001"),
        created_at=datetime.now(timezone.utc),
    )
    repo.add(patient)
    session.commit()

    # Get
    fetched = repo.get(patient_id)
    assert isinstance(fetched, Patient)
    assert fetched.id == patient_id
    assert fetched.name == "Rajesh Patel"
    assert fetched.phone.value == "+919000000001"

    # Save
    fetched.name = "Rajesh K. Patel"
    fetched.link_phone(PhoneNumber("+919000000002"))
    repo.save(fetched)
    session.commit()

    updated = repo.get(patient_id)
    assert updated.name == "Rajesh K. Patel"
    assert updated.phone.value == "+919000000002"

    # List
    patients = repo.list()
    assert len(patients) == 1
    assert patients[0].id == patient_id

    # Not found
    with pytest.raises(EntityNotFound):
        repo.get(uuid4())


def test_care_team_member_repository_crud(db_session):
    session, tenant_id = db_session
    repo = SqlAlchemyCareTeamMemberRepository(session, tenant_id)

    member_id = uuid4()
    user_id = uuid4()
    member = CareTeamMember(
        id=member_id,
        user_id=user_id,
        role=CareTeamRole.DIETITIAN,
        display_name="Ananya Sen",
        active=True,
    )
    repo.add(member)
    session.commit()

    # Get by user_id
    fetched = repo.get(user_id)
    assert isinstance(fetched, CareTeamMember)
    assert fetched.id == member_id
    assert fetched.user_id == user_id
    assert fetched.role == CareTeamRole.DIETITIAN

    # List
    members = repo.list()
    assert len(members) == 1
    assert members[0].user_id == user_id

    # Not found
    with pytest.raises(EntityNotFound):
        repo.get(uuid4())


def test_glucose_observation_repository_crud(db_session):
    session, tenant_id = db_session
    patient_repo = SqlAlchemyPatientRepository(session, tenant_id)
    repo = SqlAlchemyGlucoseObservationRepository(session, tenant_id)

    patient_id = uuid4()
    patient_repo.add(Patient(id=patient_id, uh_id=UHID("UHID-101"), name="P1"))
    session.commit()

    obs_id = uuid4()
    obs = GlucoseObservation(
        id=obs_id,
        patient_id=patient_id,
        taken_at=datetime.now(timezone.utc),
        value=GlucoseValue(110),
        tag=ReadingTag("fasting"),
    )
    repo.add(obs)
    session.commit()

    fetched = repo.get(obs_id)
    assert isinstance(fetched, GlucoseObservation)
    assert fetched.id == obs_id
    assert fetched.value.value_mg_dl == 110

    # List for patient
    obs_list = repo.list_for_patient(patient_id)
    assert len(obs_list) == 1
    assert obs_list[0].id == obs_id

    # List for empty patient
    assert repo.list_for_patient(uuid4()) == []

    with pytest.raises(EntityNotFound):
        repo.get(uuid4())


def test_meal_observation_repository_crud(db_session):
    session, tenant_id = db_session
    patient_repo = SqlAlchemyPatientRepository(session, tenant_id)
    repo = SqlAlchemyMealObservationRepository(session, tenant_id)

    patient_id = uuid4()
    patient_repo.add(Patient(id=patient_id, uh_id=UHID("UHID-102"), name="P2"))
    session.commit()

    meal_id = uuid4()
    meal = MealObservation(
        id=meal_id,
        patient_id=patient_id,
        recorded_at=datetime.now(timezone.utc),
        description="Khichdi with curd",
        portion=MealPortion(food_key="khichdi", katori=KatoriVolume(220), quantity=1.0),
        carbs_grams=35.0,
        glycemic_index="low",
    )
    repo.add(meal)
    session.commit()

    fetched = repo.get(meal_id)
    assert isinstance(fetched, MealObservation)
    assert fetched.id == meal_id
    assert fetched.description == "Khichdi with curd"
    assert fetched.carbs_grams == 35.0

    # List for patient
    meals = repo.list_for_patient(patient_id)
    assert len(meals) == 1
    assert meals[0].id == meal_id

    with pytest.raises(EntityNotFound):
        repo.get(uuid4())


def test_medication_plan_repository_crud(db_session):
    session, tenant_id = db_session
    patient_repo = SqlAlchemyPatientRepository(session, tenant_id)
    repo = SqlAlchemyMedicationPlanRepository(session, tenant_id)

    patient_id = uuid4()
    patient_repo.add(Patient(id=patient_id, uh_id=UHID("UHID-103"), name="P3"))
    session.commit()

    plan_id = uuid4()
    prescriber_id = uuid4()
    plan = MedicationPlan(
        id=plan_id,
        patient_id=patient_id,
        prescribed_by_user_id=prescriber_id,
        prescribed_by_role=CareTeamRole.DOCTOR,
        medication="Glimepiride 1mg",
        instruction="Once daily before breakfast",
    )
    repo.add(plan)
    session.commit()

    fetched = repo.get(plan_id)
    assert isinstance(fetched, MedicationPlan)
    assert fetched.id == plan_id
    assert fetched.medication == "Glimepiride 1mg"

    plans = repo.list_for_patient(patient_id)
    assert len(plans) == 1
    assert plans[0].id == plan_id

    with pytest.raises(EntityNotFound):
        repo.get(uuid4())


def test_care_task_repository_crud(db_session):
    session, tenant_id = db_session
    patient_repo = SqlAlchemyPatientRepository(session, tenant_id)
    repo = SqlAlchemyCareTaskRepository(session, tenant_id)

    patient_id = uuid4()
    patient_repo.add(Patient(id=patient_id, uh_id=UHID("UHID-104"), name="P4"))
    session.commit()

    task_id = uuid4()
    assigned_user = uuid4()
    task = CareTask(
        id=task_id,
        patient_id=patient_id,
        assigned_to_user_id=assigned_user,
        description="Verify fasting glucose log",
        status=CareTaskStatus.OPEN,
    )
    repo.add(task)
    session.commit()

    fetched = repo.get(task_id)
    assert isinstance(fetched, CareTask)
    assert fetched.id == task_id
    assert fetched.status == CareTaskStatus.OPEN

    # Update and save
    fetched.start()
    repo.save(fetched)
    session.commit()

    updated = repo.get(task_id)
    assert updated.status == CareTaskStatus.IN_PROGRESS

    tasks = repo.list_for_patient(patient_id)
    assert len(tasks) == 1
    assert tasks[0].id == task_id

    with pytest.raises(EntityNotFound):
        repo.get(uuid4())


def test_ai_artifact_repository_crud(db_session):
    session, tenant_id = db_session
    patient_repo = SqlAlchemyPatientRepository(session, tenant_id)
    repo = SqlAlchemyAIReviewArtifactRepository(session, tenant_id)

    patient_id = uuid4()
    patient_repo.add(Patient(id=patient_id, uh_id=UHID("UHID-105"), name="P5"))
    session.commit()

    artifact_id = uuid4()
    artifact = AIReviewArtifact(
        id=artifact_id,
        patient_id=patient_id,
        artifact_kind="extracted_observation",
        summary="Extracted 2 rotis",
    )
    repo.add(artifact)
    session.commit()

    fetched = repo.get(artifact_id)
    assert isinstance(fetched, AIReviewArtifact)
    assert fetched.id == artifact_id
    assert fetched.summary == "Extracted 2 rotis"

    # Save
    clinician_id = uuid4()
    fetched.submit_for_review()
    fetched.approve(clinician_id)
    repo.save(fetched)
    session.commit()

    updated = repo.get(artifact_id)
    assert updated.reviewed_by_user_id == clinician_id

    artifacts = repo.list_for_patient(patient_id)
    assert len(artifacts) == 1
    assert artifacts[0].id == artifact_id

    with pytest.raises(EntityNotFound):
        repo.get(uuid4())
