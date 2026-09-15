"""Shared test fixtures for Gate 07 HTTP API tests.

No external services required. Deterministic, repeatable, no PHI.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.domain.entities import (
    AIReviewArtifact,
    CareTeamMember,
    CareTeamRole,
    GlucoseObservation,
    MealObservation,
    Patient,
    ReviewAuthority,
    ReviewState,
)
from backend.domain.value_objects import GlucoseValue, PhoneNumber, UHID
from backend.infrastructure.persistence.models import Base, FacilityModel, OrganizationModel
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from backend.interfaces.http.app import create_app
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_event_publisher,
    get_unit_of_work,
    reset_config_cache,
)
from backend.interfaces.http.v2.security.authorization import AuthenticatedContext

TEST_SECRET = "test-secret"
TEST_ISSUER = "http://test-issuer"


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _test_config(monkeypatch):
    monkeypatch.setenv("THALI_IDENTITY__CLIENT_SECRET", TEST_SECRET)
    monkeypatch.setenv("THALI_IDENTITY__ISSUER_URL", TEST_ISSUER)
    monkeypatch.setenv("THALI_APP__ENV", "development")
    monkeypatch.setenv("THALI_DATABASE__URL", "")
    reset_config_cache()
    yield
    reset_config_cache()


# ─────────────────────────────────────────────────────────────────────────────
# Token builder
# ─────────────────────────────────────────────────────────────────────────────


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_jwt(
    *,
    sub: str | None = None,
    tenant_id: str | None = None,
    roles: list[str] | None = None,
    facility_id: str | None = None,
    exp: float | None = None,
    iss: str | None = None,
    secret: str = TEST_SECRET,
    extra: dict | None = None,
) -> str:
    """Build an HS256-signed JWT for testing (deterministic, no external libs)."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload: dict[str, Any] = {
        "sub": sub or str(uuid4()),
        "tenant_id": tenant_id or str(uuid4()),
        "iss": iss if iss is not None else TEST_ISSUER,
        "exp": exp if exp is not None else int(time.time()) + 3600,
    }
    if roles is not None:
        payload["realm_access"] = {"roles": roles}
    if facility_id:
        payload["facility_id"] = facility_id
    if extra:
        payload.update(extra)

    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# DB fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session_factory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, autocommit=False)


# ─────────────────────────────────────────────────────────────────────────────
# App fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def db_client(db_session_factory):
    """App with database-backed UnitOfWork (for tenant and scoping integration tests)."""
    app = create_app()

    async def override_uow(
        ctx: AuthenticatedContext = Depends(get_authenticated_context),
    ):
        uow = SqlAlchemyUnitOfWork(db_session_factory, ctx.tenant_id)
        try:
            yield uow
        finally:
            uow.close()

    async def override_events(
        uow: SqlAlchemyUnitOfWork = Depends(override_uow),
    ):
        from backend.infrastructure.persistence.uow.outbox_publisher import (
            SqlAlchemyOutboxDomainEventPublisher,
        )
        return SqlAlchemyOutboxDomainEventPublisher(uow.session, uow.tenant_id)

    app.dependency_overrides[get_unit_of_work] = override_uow
    app.dependency_overrides[get_event_publisher] = override_events

    test_client = TestClient(app, raise_server_exceptions=False)
    return test_client, db_session_factory


# ─────────────────────────────────────────────────────────────────────────────
# Seed helpers
# ─────────────────────────────────────────────────────────────────────────────


def seed_org(session_factory, tenant_id: UUID, slug: str = "org"):
    with session_factory() as s:
        s.add(OrganizationModel(id=tenant_id, name=f"Org {slug}", slug=slug))
        s.commit()


def seed_facility(session_factory, tenant_id: UUID, facility_id, name="Facility"):
    with session_factory() as s:
        s.add(FacilityModel(id=facility_id, tenant_id=tenant_id, name=name))
        s.commit()


def seed_patient(session_factory, tenant_id, patient_id, facility_id=None, name="Patient") -> Patient:
    patient = Patient(id=patient_id, uh_id=UHID("D-0001"), name=name, facility_id=facility_id)
    with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
        uow.patients.add(patient)
        uow.commit()
    return patient


def seed_member(session_factory, tenant_id, user_id, role=CareTeamRole.DOCTOR, facility_id=None) -> CareTeamMember:
    if isinstance(role, str):
        role = CareTeamRole(role)
    member = CareTeamMember(id=uuid4(), user_id=user_id, role=role, facility_id=facility_id, display_name="Test Doc")
    with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
        uow.care_team_members.add(member)
        uow.commit()
    return member


def seed_glucose(session_factory, tenant_id, patient_id, value=150):
    obs = GlucoseObservation(id=uuid4(), patient_id=patient_id, value=GlucoseValue(value))
    with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
        uow.glucose_observations.add(obs)
        uow.commit()
    return obs


def seed_meal(session_factory, tenant_id, patient_id, carbs=50.0, gi="medium"):
    meal = MealObservation(
        id=uuid4(),
        patient_id=patient_id,
        description="dal rice",
        carbs_grams=carbs,
        glycemic_index=gi,
    )
    with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
        uow.meal_observations.add(meal)
        uow.commit()
    return meal


def seed_ai_artifact(session_factory, tenant_id, patient_id):
    artifact = AIReviewArtifact(
        id=uuid4(),
        patient_id=patient_id,
        artifact_kind="extracted_observation",
        authority=ReviewAuthority.CLINICIAN_REVIEW,
        state=ReviewState.PENDING_REVIEW,
        generated_by="ai",
        summary="test summary",
    )
    with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
        uow.ai_artifacts.add(artifact)
        uow.commit()
    return artifact


def seed_identity_mapping(session_factory, tenant_id, user_id, patient_id, active=True):
    from backend.domain.entities import IdentityPatientMapping
    from backend.infrastructure.persistence.models.identity_models import IdentityPatientMappingModel
    from sqlalchemy import text

    now = datetime.now(timezone.utc)
    with session_factory() as s:
        s.add(
            IdentityPatientMappingModel(
                tenant_id=tenant_id,
                user_id=user_id,
                patient_id=patient_id,
                active=active,
                created_at=now,
                updated_at=now,
            )
        )
        s.commit()


def seed_caregiver_relationship(
    session_factory,
    tenant_id,
    patient_id,
    caregiver_user_id,
    status="verified",
    capabilities=None,
    expires_at=None,
):
    from backend.infrastructure.persistence.models.identity_models import CaregiverRelationshipModel
    from sqlalchemy import text

    now = datetime.now(timezone.utc)
    caps = sorted(capabilities) if capabilities is not None else sorted(["read_glucose", "read_meal"])
    with session_factory() as s:
        s.add(
            CaregiverRelationshipModel(
                tenant_id=tenant_id,
                patient_id=patient_id,
                caregiver_user_id=caregiver_user_id,
                relationship_label="test-caregiver",
                status=status,
                capabilities=caps,
                expires_at=expires_at,
                created_at=now,
                updated_at=now,
            )
        )
        s.commit()
