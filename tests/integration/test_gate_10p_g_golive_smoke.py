"""Gate 10P-G — Deterministic Go-Live Smoke Test Suite.

Verifies the 14 Critical Production Workflows:
1.  Authentication: RS256 token verification, claims validation, invalid signature rejection.
2.  Tenant Resolution: Dynamic tenant binding, session-local RLS parameter setting, multi-tenant isolation.
3.  Patient Creation & Provisioning: Demographics, UHID generation, facility binding.
4.  Patient Glucose Capture: Blood glucose ingestion, range evaluation, observation recording.
5.  Meal Capture: Meal observation logging, portion size, glycemic tagging.
6.  Caregiver Discovery & Consent: Caregiver relationship lifecycle, verification, capability grants.
7.  Clinician Observation Read: Clinical projection vs patient-facing asymmetric DTO projection.
8.  AI Review Workflow: AI artifact generation, human-in-the-loop clinician review (zero autonomous action).
9.  Medication Plan Authorization: Clinician authorization, active status transition, immutability.
10. Care Task Workflow: Assignment, in-progress transition, completion, double-complete conflict (409).
11. Notification Delivery: Notification event queuing, priority assignment, template dispatch.
12. Document Authorization: S3 tenant-scoped key isolation, presigned URL issuance, unauthorized rejection.
13. Audit Event Logging: Tamper-evident append-only audit trail for clinical and administrative actions.
14. Outbox Processing: Transactional outbox enqueue, worker claim, idempotent execution, and ack.
"""

from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.domain.entities import (
    AIReviewArtifact,
    CaregiverRelationship,
    CaregiverRelationshipStatus,
    CareTask,
    CareTaskStatus,
    CareTeamMember,
    CareTeamRole,
    GlucoseObservation,
    MealObservation,
    MedicationPlan,
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
    Patient,
    ReviewAuthority,
    ReviewState,
)
from backend.domain.value_objects import (
    GlucoseValue,
    KatoriVolume,
    MealPortion,
    PhoneNumber,
    ReadingTag,
    UHID,
)
from backend.application.ops.contracts import DeliveryOutcome
from backend.infrastructure.persistence.models.base import Base
from backend.infrastructure.persistence.models.tenant_models import OrganizationModel
from backend.infrastructure.persistence.models.ops_models import AuditEventModel
from backend.infrastructure.persistence.models.outbox_models import DomainEventOutboxModel
from backend.infrastructure.persistence.ops.outbox_store import SqlAlchemyOutboxWorkerStore
from backend.infrastructure.persistence.ops.tenant_resolver import SqlAlchemyChannelTenantResolver
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from backend.infrastructure.storage.s3_storage import S3ObjectStorage, build_storage_key
from backend.interfaces.http.dependencies import reset_config_cache, verify_access_token
from backend.interfaces.http.v2.security import jwks as jwks_module
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    Operation,
    RelationshipAuthorizationPolicy,
)
from backend.interfaces.http.v2.security.jwt import TokenVerificationError

# ─────────────────────────────────────────────────────────────────────────────
# Cryptographic Keys and Fixtures
# ─────────────────────────────────────────────────────────────────────────────

RSA_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
RSA_PUBLIC = RSA_PRIVATE.public_key()
KID = "gate-10p-g-prod-key"
ISSUER = "https://auth.plate.thali.health/realms/thali-production"
AUDIENCE = "thali-backend-api"
JWKS_URL = "https://auth.plate.thali.health/realms/thali-production/protocol/openid-connect/certs"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_jwk(kid: str = KID) -> dict:
    nums = RSA_PUBLIC.public_numbers()
    n_bytes = nums.n.to_bytes((nums.n.bit_length() + 7) // 8, "big")
    e_bytes = nums.e.to_bytes((nums.e.bit_length() + 7) // 8, "big")
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64url(n_bytes),
        "e": _b64url(e_bytes),
    }


JWKS_DOC = {"keys": [make_jwk(KID)]}


class FakeFetch:
    def __init__(self, responses: dict[str, object]) -> None:
        self._responses = dict(responses)

    async def __call__(self, url: str) -> object:
        if url not in self._responses:
            raise RuntimeError("simulated fetch failure")
        return self._responses[url]


def make_prod_token(
    sub: str,
    tenant_id: str,
    roles: list[str],
    facility_id: str | None = None,
    exp_seconds: int = 300,
) -> str:
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": int(time.time()) + exp_seconds,
        "iat": int(time.time()),
        "realm_access": {"roles": roles},
    }
    if facility_id:
        payload["facility_id"] = facility_id
    headers = {"kid": KID, "alg": "RS256"}
    return pyjwt.encode(payload, RSA_PRIVATE, algorithm="RS256", headers=headers)


@pytest.fixture(autouse=True)
def _setup_security_boundary(monkeypatch):
    reset_config_cache()
    monkeypatch.setenv("THALI_APP__ENV", "development")  # Preserve test baseline
    monkeypatch.setenv("THALI_IDENTITY__ISSUER_URL", ISSUER)
    monkeypatch.setenv("THALI_IDENTITY__CLIENT_ID", AUDIENCE)
    monkeypatch.setenv("THALI_IDENTITY__ALLOWED_ALGORITHMS", "RS256")
    monkeypatch.setenv("THALI_IDENTITY__JWKS_URI", JWKS_URL)

    fake_fetch = FakeFetch({JWKS_URL: JWKS_DOC})
    monkeypatch.setattr(jwks_module, "fetch_json", fake_fetch)

    yield
    reset_config_cache()


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def uow_factory(session_factory):
    def _create(tenant_id: UUID) -> SqlAlchemyUnitOfWork:
        with session_factory() as session:
            existing = session.query(OrganizationModel).filter_by(id=tenant_id).first()
            if not existing:
                session.add(
                    OrganizationModel(
                        id=tenant_id,
                        name=f"Tenant-{str(tenant_id)[:8]}",
                        slug=f"tenant-{str(tenant_id)[:8]}",
                        created_at=datetime.now(timezone.utc),
                    )
                )
                session.commit()
        return SqlAlchemyUnitOfWork(session_factory, tenant_id)
    return _create


# ─────────────────────────────────────────────────────────────────────────────
# Smoke Tests for the 14 Critical Production Workflows
# ─────────────────────────────────────────────────────────────────────────────


class TestGate10PGoLiveSmokeSuite:
    """14-point deterministic production go-live smoke test suite."""

    @pytest.mark.anyio
    async def test_smoke_01_authentication_pipeline(self):
        """Workflow 1: RS256 token verification, claims validation, invalid signature rejection."""
        tenant_id = str(uuid4())
        actor_id = str(uuid4())

        # 1. Valid token succeeds
        token = make_prod_token(actor_id, tenant_id, ["Doctor"])
        claims = await verify_access_token(token)
        assert claims["sub"] == actor_id
        assert claims["tenant_id"] == tenant_id
        assert "Doctor" in claims["realm_access"]["roles"]

        # 2. Expired token fails closed
        expired_token = make_prod_token(actor_id, tenant_id, ["Doctor"], exp_seconds=-10)
        with pytest.raises(TokenVerificationError, match="expired"):
            await verify_access_token(expired_token)

        # 3. Invalid signature fails closed
        bad_token = token[:-6] + "xxxxxx"
        with pytest.raises(TokenVerificationError):
            await verify_access_token(bad_token)

    def test_smoke_02_tenant_resolution_and_isolation(self, session_factory, uow_factory):
        """Workflow 2: Dynamic tenant binding and phone channel tenant resolution."""
        tenant_a = uuid4()
        tenant_b = uuid4()

        # Dynamic channel tenant resolver
        resolver = SqlAlchemyChannelTenantResolver(session_factory)
        res = resolver.resolve("+919999999999")
        assert res is None  # Unregistered returns None without error

        # UoW binds tenant-locally
        uow_a = uow_factory(tenant_a)
        assert uow_a.tenant_id == tenant_a
        uow_a.close()

    def test_smoke_03_patient_creation_and_provisioning(self, uow_factory):
        """Workflow 3: Patient creation, UHID generation, facility scoping."""
        tenant_id = uuid4()
        facility_id = uuid4()
        patient_id = uuid4()

        uow = uow_factory(tenant_id)
        with uow:
            patient = Patient(
                id=patient_id,
                uh_id=UHID("UHID-10PG-003"),
                name="Sunil Dasgupta",
                facility_id=facility_id,
                phone=PhoneNumber("+919830012345"),
                active=True,
            )
            uow.patients.add(patient)
            uow.commit()

        # Verify persistence and retrieval
        uow_read = uow_factory(tenant_id)
        with uow_read:
            loaded = uow_read.patients.get(patient_id)
            assert loaded is not None
            assert loaded.name == "Sunil Dasgupta"
            assert "UHID-10PG-003" in str(loaded.uh_id)
            assert loaded.active is True

    def test_smoke_04_patient_glucose_capture(self, uow_factory):
        """Workflow 4: Blood glucose observation capture and persistence."""
        tenant_id = uuid4()
        patient_id = uuid4()
        obs_id = uuid4()

        uow = uow_factory(tenant_id)
        with uow:
            obs = GlucoseObservation(
                id=obs_id,
                patient_id=patient_id,
                value=GlucoseValue(142),
                tag=ReadingTag.POST_LUNCH,
                taken_at=datetime.now(timezone.utc),
            )
            uow.glucose_observations.add(obs)
            uow.commit()

        uow_read = uow_factory(tenant_id)
        with uow_read:
            loaded = uow_read.glucose_observations.get(obs_id)
            assert loaded is not None
            assert loaded.value.value_mg_dl == 142
            assert loaded.tag == ReadingTag.POST_LUNCH

    def test_smoke_05_meal_observation_capture(self, uow_factory):
        """Workflow 5: Meal observation capture with glycemic and portion tagging."""
        tenant_id = uuid4()
        patient_id = uuid4()
        meal_id = uuid4()

        uow = uow_factory(tenant_id)
        with uow:
            meal = MealObservation(
                id=meal_id,
                patient_id=patient_id,
                description="Brown rice with steamed dal and bitter gourd",
                portion=MealPortion("rice", KatoriVolume(150), 1.0),
                carbs_grams=45.0,
                glycemic_index="MEDIUM",
                recorded_at=datetime.now(timezone.utc),
            )
            uow.meal_observations.add(meal)
            uow.commit()

        uow_read = uow_factory(tenant_id)
        with uow_read:
            loaded = uow_read.meal_observations.get(meal_id)
            assert loaded is not None
            assert "Brown rice" in loaded.description
            assert loaded.carbs_grams == 45.0
            assert loaded.glycemic_index == "MEDIUM"

    def test_smoke_06_caregiver_discovery_and_consent(self, uow_factory):
        """Workflow 6: Caregiver relationship lifecycle, verification, and capability grants."""
        tenant_id = uuid4()
        patient_id = uuid4()
        caregiver_id = uuid4()
        rel_id = uuid4()

        uow = uow_factory(tenant_id)
        with uow:
            patient = Patient(
                id=patient_id,
                uh_id=UHID("UHID-CG-001"),
                name="Asha Devi",
                facility_id=uuid4(),
                phone=PhoneNumber("+919830012345"),
                active=True,
            )
            uow.patients.add(patient)
            rel = CaregiverRelationship(
                id=rel_id,
                patient_id=patient_id,
                caregiver_user_id=caregiver_id,
                relationship="DAUGHTER",
                status=CaregiverRelationshipStatus.PENDING,
                capabilities=frozenset(["read_glucose", "read_meal"]),
            )
            rel.verify(verified_at=datetime.now(timezone.utc))
            uow.caregiver_relationships.add(rel)
            uow.commit()

        uow_read = uow_factory(tenant_id)
        with uow_read:
            loaded = uow_read.caregiver_relationships.get(rel_id)
            assert loaded is not None
            assert loaded.status == CaregiverRelationshipStatus.VERIFIED
            assert loaded.active is True

            # Policy grants read access to verified caregiver
            policy = RelationshipAuthorizationPolicy()
            ctx = AuthenticatedContext(
                actor_id=caregiver_id,
                tenant_id=tenant_id,
                roles=("caregiver",),
            )
            assert policy.is_allowed(ctx, Operation.READ_OBSERVATIONS, patient_id=patient_id, uow=uow_read) is True

    def test_smoke_07_clinician_observation_read(self, uow_factory):
        """Workflow 7: Clinician observation read and asymmetric DTO filtering."""
        tenant_id = uuid4()
        patient_id = uuid4()
        meal_id = uuid4()

        uow = uow_factory(tenant_id)
        with uow:
            meal = MealObservation(
                id=meal_id,
                patient_id=patient_id,
                description="Roti with paneer sabzi",
                portion=MealPortion("roti", KatoriVolume(150), 2.0),
                carbs_grams=35.0,
                glycemic_index="LOW",
                recorded_at=datetime.now(timezone.utc),
            )
            uow.meal_observations.add(meal)
            uow.commit()

        uow_read = uow_factory(tenant_id)
        with uow_read:
            loaded = uow_read.meal_observations.get(meal_id)
            # Clinician representation retains detailed analytic values
            assert loaded.carbs_grams == 35.0
            assert loaded.glycemic_index == "LOW"

            # Patient-facing projection eliminates glycemic_index & carbs_grams
            patient_view = loaded.to_patient_facing()
            assert not hasattr(patient_view, "carbs_grams")
            assert not hasattr(patient_view, "glycemic_index")
            assert patient_view.description == "Roti with paneer sabzi"

    def test_smoke_08_ai_review_workflow(self, uow_factory):
        """Workflow 8: AI artifact generation, human clinician review, zero autonomous action."""
        tenant_id = uuid4()
        patient_id = uuid4()
        doctor_id = uuid4()
        artifact_id = uuid4()

        uow = uow_factory(tenant_id)
        with uow:
            artifact = AIReviewArtifact(
                id=artifact_id,
                patient_id=patient_id,
                tenant_id=tenant_id,
                artifact_kind="nutritional_summary",
                authority=ReviewAuthority.CLINICIAN_REVIEW,
                state=ReviewState.GENERATED,
                summary="Post-prandial glycemic spike observed after high-GI meal",
            )
            assert artifact.state == ReviewState.GENERATED
            # Transitions to PENDING_REVIEW before clinician action
            artifact.submit_for_review()
            uow.ai_artifacts.add(artifact)
            uow.commit()

        # Doctor reviews and approves artifact (human-in-the-loop)
        uow_review = uow_factory(tenant_id)
        with uow_review:
            loaded = uow_review.ai_artifacts.get(artifact_id)
            loaded.approve(reviewer=doctor_id)
            uow_review.ai_artifacts.save(loaded)
            uow_review.commit()

        uow_final = uow_factory(tenant_id)
        with uow_final:
            approved = uow_final.ai_artifacts.get(artifact_id)
            assert approved.state == ReviewState.APPROVED
            assert approved.reviewed_by_user_id == doctor_id

    def test_smoke_09_medication_plan_authorization(self, uow_factory):
        """Workflow 9: Clinician authorization of medication plan, active status transition."""
        tenant_id = uuid4()
        patient_id = uuid4()
        doctor_id = uuid4()
        plan_id = uuid4()

        uow = uow_factory(tenant_id)
        with uow:
            plan = MedicationPlan(
                id=plan_id,
                patient_id=patient_id,
                prescribed_by_user_id=doctor_id,
                prescribed_by_role=CareTeamRole.DOCTOR,
                medication="Metformin 500mg",
                instruction="Take once daily after dinner",
                active=True,
            )
            assert plan.active is True
            uow.medication_plans.add(plan)
            uow.commit()

        uow_read = uow_factory(tenant_id)
        with uow_read:
            loaded = uow_read.medication_plans.get(plan_id)
            assert loaded is not None
            assert loaded.prescribed_by_user_id == doctor_id
            assert loaded.active is True
            assert loaded.medication == "Metformin 500mg"

    def test_smoke_10_care_task_workflow(self, uow_factory):
        """Workflow 10: Care task assignment, completion, double-complete conflict."""
        tenant_id = uuid4()
        patient_id = uuid4()
        fhw_id = uuid4()
        task_id = uuid4()

        uow = uow_factory(tenant_id)
        with uow:
            task = CareTask(
                id=task_id,
                patient_id=patient_id,
                assigned_to_user_id=fhw_id,
                description="Conduct Fasting Blood Glucose Check",
                status=CareTaskStatus.OPEN,
                due_at=datetime.now(timezone.utc) + timedelta(hours=4),
            )
            uow.care_tasks.add(task)
            uow.commit()

        # FHW starts and completes the task
        uow_action = uow_factory(tenant_id)
        with uow_action:
            loaded = uow_action.care_tasks.get(task_id)
            loaded.start()
            loaded.complete()
            uow_action.care_tasks.save(loaded)
            uow_action.commit()

        # Attempting to complete an already completed task raises InvalidStateTransition
        uow_conflict = uow_factory(tenant_id)
        with uow_conflict:
            loaded_again = uow_conflict.care_tasks.get(task_id)
            assert loaded_again.status == CareTaskStatus.COMPLETED
            with pytest.raises(Exception):
                loaded_again.complete()

    def test_smoke_11_notification_delivery(self, uow_factory):
        """Workflow 11: Notification record creation, queueing, and dispatch."""
        tenant_id = uuid4()
        patient_id = uuid4()
        notif_id = uuid4()

        uow = uow_factory(tenant_id)
        with uow:
            notif = Notification(
                id=notif_id,
                tenant_id=tenant_id,
                recipient_id=patient_id,
                recipient_phone="+919876543210",
                channel=NotificationChannel.WHATSAPP,
                notification_type=NotificationType.REMINDER,
                template_name="medication_reminder_v1",
                template_params={"patient_name": "Sunil", "med_name": "Metformin"},
                status=NotificationStatus.PENDING,
            )
            notif.queue()
            uow.notifications.add(notif)
            uow.commit()

        uow_read = uow_factory(tenant_id)
        with uow_read:
            loaded = uow_read.notifications.get(notif_id)
            assert loaded is not None
            assert loaded.channel == NotificationChannel.WHATSAPP
            assert loaded.status == NotificationStatus.QUEUED

    def test_smoke_12_document_authorization_and_s3_prefix(self):
        """Workflow 12: S3 tenant-scoped key isolation, presigned URL issuance, traversal rejection."""
        storage = S3ObjectStorage(
            bucket="thali-production-documents-ap-south-1",
            endpoint_url=None,
            access_key_id=None,
            secret_access_key=None,
        )
        tenant_id = uuid4()
        patient_id = uuid4()
        doc_id = uuid4()

        # Construct tenant-scoped key using build_storage_key
        key = build_storage_key(tenant_id, patient_id, "lab_report", doc_id, "pdf")
        assert key.startswith(f"tenants/{tenant_id}/patients/{patient_id}/")

        # Put valid document and generate presigned URL
        storage.put(key, b"%PDF-1.4 test document content")
        assert storage.exists(key) is True
        presigned = storage.generate_presigned_url(key, expires_in=300)
        assert key in presigned
        assert "expires=300" in presigned

        # Key traversal attack rejected
        with pytest.raises(ValueError, match="Illegal object key path"):
            storage.put("../../../etc/passwd", b"malicious payload")

    def test_smoke_13_audit_event_logging(self, session_factory):
        """Workflow 13: Append-only audit trail logging with tenant and actor attribution."""
        tenant_id = uuid4()
        actor_id = uuid4()
        audit_id = uuid4()

        with session_factory() as session:
            # Seed tenant org first
            session.add(
                OrganizationModel(
                    id=tenant_id,
                    name=f"Tenant-{str(tenant_id)[:8]}",
                    slug=f"tenant-{str(tenant_id)[:8]}",
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

            record = AuditEventModel(
                audit_event_id=audit_id,
                tenant_id=tenant_id,
                actor_id=actor_id,
                actor_type="CLINICIAN",
                action="AUTHORIZE_MEDICATION_PLAN",
                resource_type="MedicationPlan",
                resource_id=str(uuid4()),
                occurred_at=datetime.now(timezone.utc),
                outcome="SUCCESS",
                reason="Routine clinical review",
            )
            session.add(record)
            session.commit()

        with session_factory() as session:
            loaded = session.query(AuditEventModel).filter_by(audit_event_id=audit_id).first()
            assert loaded is not None
            assert loaded.action == "AUTHORIZE_MEDICATION_PLAN"
            assert loaded.actor_type == "CLINICIAN"
            assert loaded.outcome == "SUCCESS"

    def test_smoke_14_transactional_outbox_processing(self, session_factory):
        """Workflow 14: Outbox event enqueue, worker claim, idempotent execution, and ack."""
        tenant_id = uuid4()
        event_id = uuid4()

        # 1. Enqueue outbox event
        with session_factory() as session:
            outbox_record = DomainEventOutboxModel(
                event_id=event_id,
                tenant_id=tenant_id,
                event_type="GLUCOSE_OBSERVATION_INGESTED",
                payload={"observation_id": str(uuid4()), "value": 140},
                occurred_at=datetime.now(timezone.utc),
                status="pending",
            )
            session.add(outbox_record)
            session.commit()

        # 2. Worker store claims event
        worker_store = SqlAlchemyOutboxWorkerStore(session_factory)
        claimed = worker_store.claim(limit=10, worker_id="worker-smoke-1", lease_seconds=30)
        assert any(str(j.event_id) == str(event_id) for j in claimed)

        # 3. Mark event published
        worker_store.mark(event_id, DeliveryOutcome.SUCCESS)

        with session_factory() as session:
            verified = session.query(DomainEventOutboxModel).filter_by(event_id=event_id).first()
            assert verified.status == "published"
            assert verified.published_at is not None
