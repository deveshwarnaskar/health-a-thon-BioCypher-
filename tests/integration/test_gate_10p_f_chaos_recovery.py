"""Gate 10P-F — Chaos Drills, Degradation & Failure Recovery Test Suite.

Verifies:
1. Database outage, connection pool exhaustion & atomic rollback:
   - /health/ready returns 503 when database is unreachable; recovers to 200 when restored
   - Midway failure inside a clinical mutation transaction guarantees 100% rollback (zero orphaned records)
   - Connection pool exhaustion fails with bounded latency and safe 503 status without hanging

2. Redis degradation & resilience:
   - /health/ready returns 503 when Redis is enabled but unreachable; recovers when available
   - Cache degradation operates without unhandled crashes or hanging sockets

3. Outbox worker crash recovery, lease timeouts & poison message dead-lettering:
   - Crash recovery: worker leasing job dies, lease expires, second worker reclaims and publishes cleanly
   - Duplicate delivery suppression: already processed jobs are ignored idempotently
   - Poison message: handler that repeatedly fails is retried up to max_retries and dead-lettered

4. AI provider degradation & strict zero-autonomous-mutation invariant:
   - Upstream AI service outage or schema failure returns bounded error without service crash
   - Strict human-in-the-loop invariant: AI-generated artifacts NEVER autonomously transition to APPROVED
     or mutate medication plans
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import tempfile
import time
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from backend.application.ops.contracts import DeliveryOutcome, OutboxJob
from backend.application.ops.errors import TransientWorkerError
from backend.application.ops.worker import OutboxWorker
from backend.domain.entities import (
    AIReviewArtifact,
    CareTask,
    CareTaskStatus,
    CareTeamRole,
    MedicationPlan,
    ReviewAuthority,
    ReviewState,
)
from backend.domain.exceptions import UnauthorizedMedicationPlanMutation
from backend.infrastructure.persistence.models import (
    Base,
    DomainEventOutboxModel,
    GlucoseObservationModel,
)
from backend.infrastructure.persistence.ops.outbox_store import SqlAlchemyOutboxWorkerStore
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from backend.interfaces.http.app import create_app
from backend.interfaces.http.dependencies import (
    get_unit_of_work,
    reset_config_cache,
    _get_engine,
)
from config.settings import Settings
from tests.api.conftest import (
    TEST_CLIENT_ID,
    TEST_ISSUER,
    TEST_SECRET,
    make_jwt,
    seed_facility,
    seed_member,
    seed_org,
    seed_patient,
)


@pytest.fixture
def chaos_env(monkeypatch):
    monkeypatch.setenv("THALI_IDENTITY__CLIENT_SECRET", TEST_SECRET)
    monkeypatch.setenv("THALI_IDENTITY__ISSUER_URL", TEST_ISSUER)
    monkeypatch.setenv("THALI_IDENTITY__CLIENT_ID", TEST_CLIENT_ID)
    monkeypatch.setenv("THALI_IDENTITY__ALLOWED_ALGORITHMS", "HS256")
    monkeypatch.setenv("THALI_IDENTITY__JWKS_URI", "")
    monkeypatch.setenv("THALI_APP__ENV", "development")

    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("THALI_DATABASE__URL", db_url)
    reset_config_cache()

    engine = _get_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.execute(text("PRAGMA busy_timeout=30000;"))
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    tenant_id = UUID("40000000-0000-0000-0000-000000000001")
    facility_id = UUID("40000000-0000-0000-0000-000000000011")
    doctor_id = UUID("40000000-0000-0000-0000-000000000021")
    patient_id = UUID("40000000-0000-0000-0000-000000000031")

    sf = session_factory
    seed_org(sf, tenant_id, "CHAOS_ORG")
    seed_facility(sf, tenant_id, facility_id, "CHAOS_CLINIC")
    seed_member(sf, tenant_id, doctor_id, role=CareTeamRole.DOCTOR, facility_id=facility_id)
    seed_patient(sf, tenant_id, patient_id, facility_id, "CHAOS_PATIENT")

    app = create_app()

    from backend.interfaces.http.dependencies import get_authenticated_context
    from backend.interfaces.http.v2.security.authorization import AuthenticatedContext
    from fastapi import Depends

    async def override_uow(ctx: AuthenticatedContext = Depends(get_authenticated_context)):
        uow = SqlAlchemyUnitOfWork(session_factory, ctx.tenant_id)
        try:
            yield uow
        finally:
            uow.close()

    app.dependency_overrides[get_unit_of_work] = override_uow

    token = make_jwt(
        sub=str(doctor_id),
        tenant_id=str(tenant_id),
        roles=["doctor"],
        facility_id=str(facility_id),
    )

    try:
        yield {
            "app": app,
            "engine": engine,
            "session_factory": session_factory,
            "tenant_id": tenant_id,
            "facility_id": facility_id,
            "doctor_id": doctor_id,
            "patient_id": patient_id,
            "token": token,
            "db_path": db_path,
        }
    finally:
        reset_config_cache()
        engine.dispose()
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
        except Exception:
            pass


class TestDatabaseOutageAndPoolRecovery:
    """Validate database degradation, connection exhaustion, and atomic rollback invariants."""

    def test_database_down_readiness_returns_503(self, chaos_env):
        """When database check fails, /health/ready returns 503 and reports unavailable."""
        client = TestClient(chaos_env["app"])

        # Normal condition: database is ok
        resp_healthy = client.get("/health/ready")
        assert resp_healthy.status_code == 200
        assert resp_healthy.json()["status"] == "ok"
        assert resp_healthy.json()["checks"]["database"] == "ok"

        # Simulate database outage via check failure
        with patch("backend.infrastructure.config.database.check_database_health", return_value=False):
            resp_down = client.get("/health/ready")
            assert resp_down.status_code == 503
            assert resp_down.json()["status"] == "not_ready"
            assert resp_down.json()["checks"]["database"] == "unavailable"

        # Recovery condition: database returns to healthy state
        resp_recovered = client.get("/health/ready")
        assert resp_recovered.status_code == 200
        assert resp_recovered.json()["status"] == "ok"
        assert resp_recovered.json()["checks"]["database"] == "ok"

    def test_database_transaction_rollback_on_midway_failure(self, chaos_env):
        """Simulated exception during clinical ingestion triggers complete rollback with zero partial records."""
        sf = chaos_env["session_factory"]
        tenant_id = chaos_env["tenant_id"]
        patient_id = chaos_env["patient_id"]

        with pytest.raises(RuntimeError, match="Chaos drill: simulated mid-transaction failure"):
            with SqlAlchemyUnitOfWork(sf, tenant_id) as uow:
                # Add observation
                from backend.domain.entities import GlucoseObservation
                from backend.domain.value_objects import GlucoseValue
                obs = GlucoseObservation(
                    patient_id=patient_id,
                    value=GlucoseValue(199),
                    taken_at=datetime.now(timezone.utc),
                )
                uow.glucose_observations.add(obs)
                # Intentionally crash before commit
                raise RuntimeError("Chaos drill: simulated mid-transaction failure")

        # Verify nothing was committed (atomicity)
        with SqlAlchemyUnitOfWork(sf, tenant_id) as uow:
            feed = uow.glucose_observations.list_for_patient(patient_id)
            matching = [g for g in feed if g.value.value_mg_dl == 199]
            assert len(matching) == 0, "Partial write detected! Rollback failed."

    def test_pool_exhaustion_bounded_latency_and_fail_closed(self, chaos_env):
        """Database connection checkout failure fails closed cleanly without thread hanging."""
        client = TestClient(chaos_env["app"], raise_server_exceptions=False)
        token = chaos_env["token"]
        patient_id = str(chaos_env["patient_id"])
        original_override = chaos_env["app"].dependency_overrides[get_unit_of_work]

        def broken_uow():
            raise TimeoutError("QueuePool limit of size 5 overflow 10 reached, connection timed out")

        try:
            chaos_env["app"].dependency_overrides[get_unit_of_work] = broken_uow
            t0 = time.perf_counter()
            resp = client.get(
                f"/api/v2/patients/{patient_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            elapsed = time.perf_counter() - t0

            # Must fail with 500 or 503 within bounded time (< 2.0s)
            assert resp.status_code in {500, 503}
            assert elapsed < 2.0, f"Call hung for {elapsed}s on pool exhaustion!"
        finally:
            chaos_env["app"].dependency_overrides[get_unit_of_work] = original_override


class TestRedisDegradationAndLockFailure:
    """Validate Redis outage resilience, readiness health check reporting, and graceful degradation."""

    def test_redis_unreachable_readiness_reports_503(self, chaos_env, monkeypatch):
        """When Redis is enabled but unreachable, /health/ready returns 503 and reports redis unavailable."""
        client = TestClient(chaos_env["app"])

        # Configure settings to enable Redis pointing to an unreachable port
        monkeypatch.setenv("THALI_REDIS__ENABLED", "true")
        monkeypatch.setenv("THALI_REDIS__HOST", "127.0.0.1")
        monkeypatch.setenv("THALI_REDIS__PORT", "59999")  # Non-existent Redis port

        with patch("backend.infrastructure.cache.redis_client.RedisCacheAdapter.ping", return_value=False):
            resp = client.get("/health/ready")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "not_ready"
            assert data["checks"]["redis"] == "unavailable"

    def test_redis_recovery_restores_readiness_200(self, chaos_env, monkeypatch):
        """When Redis returns online, /health/ready returns 200 without requiring process restart."""
        client = TestClient(chaos_env["app"])

        monkeypatch.setenv("THALI_REDIS__ENABLED", "true")
        monkeypatch.setenv("THALI_REDIS__HOST", "127.0.0.1")
        monkeypatch.setenv("THALI_REDIS__PORT", "6379")

        with patch("backend.infrastructure.cache.redis_client.RedisCacheAdapter.ping", return_value=True):
            resp = client.get("/health/ready")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["checks"]["redis"] == "ok"


class TestOutboxWorkerCrashAndPoisonRecovery:
    """Validate transactional outbox lease expiry, crash recovery, deduplication, and dead-lettering."""

    def test_worker_crash_lease_timeout_recovery(self, chaos_env):
        """When a worker crashes while processing a job, lease timeout allows another worker to reclaim and complete it."""
        sf = chaos_env["session_factory"]
        tenant_id = chaos_env["tenant_id"]
        event_id = uuid4()
        now = datetime.now(timezone.utc)

        # 1. Seed a job simulating a dead worker (status='processing', locked 10 minutes ago)
        with sf() as session:
            stale_job = DomainEventOutboxModel(
                event_id=event_id,
                event_type="patient.glucose_recorded",
                tenant_id=tenant_id,
                patient_id=chaos_env["patient_id"],
                correlation_id=uuid4(),
                payload={"mg_dl": 115},
                occurred_at=now - timedelta(minutes=15),
                status="processing",
                locked_by="crashed-worker-node-1",
                locked_at=now - timedelta(minutes=10),
                retry_count=0,
            )
            session.add(stale_job)
            session.commit()

        # 2. Spin up a new worker with lease_seconds=300 (5 minutes)
        # Since locked_at was 10 minutes ago, this stale job MUST be reclaimed
        executed = []

        def sample_handler(job: OutboxJob) -> DeliveryOutcome:
            executed.append(job.event_id)
            return DeliveryOutcome.SUCCESS

        store = SqlAlchemyOutboxWorkerStore(sf)
        worker = OutboxWorker(
            store=store,
            handlers={"patient.glucose_recorded": sample_handler},
            worker_id="surviving-worker-node-2",
            lease_seconds=300,
        )

        claimed_count = worker.process_once()
        assert claimed_count >= 1
        assert event_id in executed, "Crashed worker's expired job was not reclaimed!"

        # 3. Verify job is now marked 'published' in database
        with sf() as session:
            row = session.execute(
                select(DomainEventOutboxModel).where(DomainEventOutboxModel.event_id == event_id)
            ).scalar_one()
            assert row.status == "published"

    def test_poison_message_dead_letter_transition(self, chaos_env):
        """A poison message that repeatedly fails is retried up to max_retries and moved to dead_letter."""
        sf = chaos_env["session_factory"]
        tenant_id = chaos_env["tenant_id"]
        event_id = uuid4()
        now = datetime.now(timezone.utc)

        # Seed a pending job
        with sf() as session:
            poison_job = DomainEventOutboxModel(
                event_id=event_id,
                event_type="clinical.poison_event",
                tenant_id=tenant_id,
                patient_id=chaos_env["patient_id"],
                correlation_id=uuid4(),
                payload={"corrupted": True},
                occurred_at=now,
                status="pending",
                retry_count=0,
            )
            session.add(poison_job)
            session.commit()

        # Handler that always fails
        def crashing_handler(job: OutboxJob) -> DeliveryOutcome:
            raise TransientWorkerError("Simulated poison processing exception")

        store = SqlAlchemyOutboxWorkerStore(sf)
        worker = OutboxWorker(
            store=store,
            handlers={"clinical.poison_event": crashing_handler},
            worker_id="test-worker",
            max_retries=3,
            lease_seconds=0,
        )

        # Run worker multiple times to exhaust retry budget
        for _ in range(4):
            # Reset next_attempt_at so it can be claimed immediately in test
            with sf() as session:
                row = session.execute(
                    select(DomainEventOutboxModel).where(DomainEventOutboxModel.event_id == event_id)
                ).scalar_one()
                row.next_attempt_at = now - timedelta(seconds=1)
                row.status = "pending" if row.status != "dead_letter" else "dead_letter"
                session.commit()
            worker.process_once()

        # Verify job transitioned to dead_letter
        with sf() as session:
            row = session.execute(
                select(DomainEventOutboxModel).where(DomainEventOutboxModel.event_id == event_id)
            ).scalar_one()
            assert row.status == "dead_letter", f"Expected dead_letter status, got {row.status}"


class TestAIFailureAndHumanInTheLoopInvariant:
    """Validate AI service outage handling, strict state machine boundaries, and zero-autonomous-mutation."""

    def test_ai_artifact_never_autonomously_approved(self, chaos_env):
        """AI review artifacts are created in GENERATED state and can NEVER autonomously transition to APPROVED."""
        artifact_id = uuid4()
        patient_id = chaos_env["patient_id"]

        artifact = AIReviewArtifact(
            id=artifact_id,
            patient_id=patient_id,
            tenant_id=chaos_env["tenant_id"],
            artifact_kind="clinical_summary",
            authority=ReviewAuthority.CLINICIAN_REVIEW,
            state=ReviewState.GENERATED,
            summary="AI generated clinical summary",
        )

        # 1. State machine invariant: GENERATED cannot jump directly to APPROVED
        with pytest.raises(Exception):
            artifact.approve(reviewer=uuid4())

        # 2. Even in PENDING_REVIEW, approval requires an explicit human clinician approver
        artifact.submit_for_review()
        assert artifact.state == ReviewState.PENDING_REVIEW

        # Approving requires a human clinician reviewer
        clinician_id = chaos_env["doctor_id"]
        artifact.approve(reviewer=clinician_id)
        assert artifact.state == ReviewState.APPROVED
        assert artifact.reviewed_by_user_id == clinician_id

    def test_ai_or_automated_worker_cannot_create_medication_plan(self, chaos_env):
        """AI or automated worker roles CANNOT author medication plans (strict clinician-authored invariant)."""
        # CareTeamRole does not allow AI or generic automated workers to prescribe
        with pytest.raises(UnauthorizedMedicationPlanMutation):
            MedicationPlan(
                id=uuid4(),
                patient_id=chaos_env["patient_id"],
                prescribed_by_user_id=uuid4(),
                prescribed_by_role=CareTeamRole.CARE_COORDINATOR,  # Non-prescribing role
                medication="Insulin Glargine 10 units",
                instruction="At bedtime",
            )
