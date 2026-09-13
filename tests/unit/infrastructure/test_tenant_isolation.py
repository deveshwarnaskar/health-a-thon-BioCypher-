"""Multi-tenant isolation and security enforcement tests (Gate 05).

Verifies:
1. Tenant A cannot retrieve Tenant B records.
2. Tenant A cannot mutate Tenant B records.
3. Tenant-scoped repository methods cannot silently ignore tenant context.
4. List queries for Tenant A never return records belonging to Tenant B.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.domain.entities import (
    AIReviewArtifact,
    CareTask,
    CareTeamMember,
    CareTeamRole,
    GlucoseObservation,
    MealObservation,
    MedicationPlan,
    Patient,
)
from backend.domain.exceptions import EntityNotFound
from backend.domain.value_objects import GlucoseValue, PhoneNumber, UHID
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
def two_tenants():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()

    tenant_a = uuid4()
    tenant_b = uuid4()

    org_a = OrganizationModel(id=tenant_a, name="Hospital A", slug="hospital-a")
    org_b = OrganizationModel(id=tenant_b, name="Hospital B", slug="hospital-b")
    session.add_all([org_a, org_b])
    session.commit()

    yield session, tenant_a, tenant_b

    session.close()
    Base.metadata.drop_all(engine)


def test_repository_refuses_none_tenant_context():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    session = sessionmaker(bind=engine)()

    for repo_cls in [
        SqlAlchemyPatientRepository,
        SqlAlchemyCareTeamMemberRepository,
        SqlAlchemyGlucoseObservationRepository,
        SqlAlchemyMealObservationRepository,
        SqlAlchemyMedicationPlanRepository,
        SqlAlchemyCareTaskRepository,
        SqlAlchemyAIReviewArtifactRepository,
    ]:
        with pytest.raises(ValueError, match="tenant_id is required"):
            repo_cls(session, None)  # type: ignore


def test_tenant_a_cannot_retrieve_tenant_b_patient(two_tenants):
    session, tenant_a, tenant_b = two_tenants
    repo_a = SqlAlchemyPatientRepository(session, tenant_a)
    repo_b = SqlAlchemyPatientRepository(session, tenant_b)

    # Seed patient under Tenant B
    patient_b_id = uuid4()
    patient_b = Patient(
        id=patient_b_id,
        uh_id=UHID("UHID-B"),
        name="Patient of Tenant B",
        phone=PhoneNumber("+919000000002"),
    )
    repo_b.add(patient_b)
    session.commit()

    # Tenant B can access
    assert repo_b.get(patient_b_id).name == "Patient of Tenant B"

    # Tenant A MUST NOT retrieve Tenant B's patient
    with pytest.raises(EntityNotFound):
        repo_a.get(patient_b_id)


def test_tenant_a_cannot_mutate_tenant_b_patient(two_tenants):
    session, tenant_a, tenant_b = two_tenants
    repo_a = SqlAlchemyPatientRepository(session, tenant_a)
    repo_b = SqlAlchemyPatientRepository(session, tenant_b)

    patient_b_id = uuid4()
    patient_b = Patient(
        id=patient_b_id,
        uh_id=UHID("UHID-B"),
        name="Original Tenant B Name",
    )
    repo_b.add(patient_b)
    session.commit()

    # Tenant A tries to save/modify patient_b
    attacker_patient = Patient(
        id=patient_b_id,
        uh_id=UHID("UHID-HACK"),
        name="Mutated By Tenant A",
    )
    with pytest.raises(EntityNotFound):
        repo_a.save(attacker_patient)

    # Verify patient in Tenant B remains untouched
    session.rollback()
    assert repo_b.get(patient_b_id).name == "Original Tenant B Name"


def test_tenant_list_queries_isolated(two_tenants):
    session, tenant_a, tenant_b = two_tenants
    repo_a = SqlAlchemyPatientRepository(session, tenant_a)
    repo_b = SqlAlchemyPatientRepository(session, tenant_b)

    p_a = Patient(id=uuid4(), uh_id=UHID("UHID-A"), name="Patient A")
    p_b = Patient(id=uuid4(), uh_id=UHID("UHID-B"), name="Patient B")
    repo_a.add(p_a)
    repo_b.add(p_b)
    session.commit()

    list_a = repo_a.list()
    assert len(list_a) == 1
    assert list_a[0].id == p_a.id

    list_b = repo_b.list()
    assert len(list_b) == 1
    assert list_b[0].id == p_b.id


def test_tenant_cross_access_blocked_for_observations(two_tenants):
    session, tenant_a, tenant_b = two_tenants
    patient_repo_b = SqlAlchemyPatientRepository(session, tenant_b)
    glucose_repo_a = SqlAlchemyGlucoseObservationRepository(session, tenant_a)
    glucose_repo_b = SqlAlchemyGlucoseObservationRepository(session, tenant_b)

    patient_b = Patient(id=uuid4(), uh_id=UHID("UHID-B"), name="Patient B")
    patient_repo_b.add(patient_b)
    session.commit()

    obs_b_id = uuid4()
    obs_b = GlucoseObservation(
        id=obs_b_id,
        patient_id=patient_b.id,
        value=GlucoseValue(150),
    )
    glucose_repo_b.add(obs_b)
    session.commit()

    # Tenant A cannot get observation
    with pytest.raises(EntityNotFound):
        glucose_repo_a.get(obs_b_id)

    # Tenant A list_for_patient returns empty even if patient_id is guessed
    assert glucose_repo_a.list_for_patient(patient_b.id) == []


def test_tenant_cross_access_blocked_for_medication_plans(two_tenants):
    session, tenant_a, tenant_b = two_tenants
    patient_repo_b = SqlAlchemyPatientRepository(session, tenant_b)
    plan_repo_a = SqlAlchemyMedicationPlanRepository(session, tenant_a)
    plan_repo_b = SqlAlchemyMedicationPlanRepository(session, tenant_b)

    patient_b = Patient(id=uuid4(), uh_id=UHID("UHID-B"), name="Patient B")
    patient_repo_b.add(patient_b)
    session.commit()

    plan_b_id = uuid4()
    plan_b = MedicationPlan(
        id=plan_b_id,
        patient_id=patient_b.id,
        prescribed_by_user_id=uuid4(),
        prescribed_by_role=CareTeamRole.DOCTOR,
        medication="Metformin",
    )
    plan_repo_b.add(plan_b)
    session.commit()

    with pytest.raises(EntityNotFound):
        plan_repo_a.get(plan_b_id)

    assert plan_repo_a.list_for_patient(patient_b.id) == []


def test_tenant_cross_access_blocked_for_care_tasks(two_tenants):
    session, tenant_a, tenant_b = two_tenants
    patient_repo_b = SqlAlchemyPatientRepository(session, tenant_b)
    task_repo_a = SqlAlchemyCareTaskRepository(session, tenant_a)
    task_repo_b = SqlAlchemyCareTaskRepository(session, tenant_b)

    patient_b = Patient(id=uuid4(), uh_id=UHID("UHID-B"), name="Patient B")
    patient_repo_b.add(patient_b)
    session.commit()

    task_b_id = uuid4()
    task_b = CareTask(
        id=task_b_id,
        patient_id=patient_b.id,
        assigned_to_user_id=uuid4(),
        description="Confidential task",
    )
    task_repo_b.add(task_b)
    session.commit()

    with pytest.raises(EntityNotFound):
        task_repo_a.get(task_b_id)

    with pytest.raises(EntityNotFound):
        task_b_mutated = CareTask(
            id=task_b_id,
            patient_id=patient_b.id,
            assigned_to_user_id=uuid4(),
            description="Compromised task",
        )
        task_repo_a.save(task_b_mutated)

    assert task_repo_a.list_for_patient(patient_b.id) == []


def test_tenant_cross_access_blocked_for_care_team_members(two_tenants):
    session, tenant_a, tenant_b = two_tenants
    member_repo_a = SqlAlchemyCareTeamMemberRepository(session, tenant_a)
    member_repo_b = SqlAlchemyCareTeamMemberRepository(session, tenant_b)

    user_b = uuid4()
    member_b = CareTeamMember(
        id=uuid4(),
        user_id=user_b,
        role=CareTeamRole.DOCTOR,
        display_name="Dr. B",
    )
    member_repo_b.add(member_b)
    session.commit()

    with pytest.raises(EntityNotFound):
        member_repo_a.get(user_b)

    assert member_repo_a.list() == []
