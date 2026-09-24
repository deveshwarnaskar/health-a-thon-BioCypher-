"""Authorization boundary tests (Gate 07).

Proves:
- DENY-BY-DEFAULT policy (unknown/missing role → denied)
- Coarse operation-level RBAC (role → operation matrix)
- MedicationPlan clinician authority preserved (domain invariant)
- AI approval authority preserved (no self-approval)
- Patient self-access DENIED (Gate 08)
- Caregiver relationship access DENIED (Gate 08)
- Clinician facility scoping DENIED without matching facility
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    DefaultAuthorizationPolicy,
    Operation,
)
from tests.api.conftest import (
    bearer,
    make_jwt,
    seed_ai_artifact,
    seed_glucose,
    seed_member,
    seed_org,
    seed_patient,
)


class TestAuthorizationPolicy:
    """Unit tests for the AuthorizationPolicy in isolation."""

    def test_deny_by_default_empty_roles(self):
        ctx = AuthenticatedContext(
            actor_id=uuid4(), tenant_id=uuid4(), roles=(), facility_id=None,
        )
        assert not DefaultAuthorizationPolicy().is_allowed(ctx, Operation.READ_OBSERVATIONS)

    def test_deny_by_default_unknown_role(self):
        ctx = AuthenticatedContext(
            actor_id=uuid4(), tenant_id=uuid4(), roles=("super_admin",), facility_id=None,
        )
        assert not DefaultAuthorizationPolicy().is_allowed(ctx, Operation.READ_OBSERVATIONS)

    def test_doctor_read_observations_allowed(self):
        ctx = AuthenticatedContext(
            actor_id=uuid4(), tenant_id=uuid4(), roles=("doctor",), facility_id=uuid4(),
        )
        assert DefaultAuthorizationPolicy().is_allowed(ctx, Operation.READ_OBSERVATIONS)

    def test_doctor_write_medication_plans_allowed(self):
        ctx = AuthenticatedContext(
            actor_id=uuid4(), tenant_id=uuid4(), roles=("doctor",), facility_id=uuid4(),
        )
        assert DefaultAuthorizationPolicy().is_allowed(ctx, Operation.WRITE_MEDICATION_PLANS)

    def test_nurse_review_ai_artifact_allowed(self):
        ctx = AuthenticatedContext(
            actor_id=uuid4(), tenant_id=uuid4(), roles=("nurse",), facility_id=uuid4(),
        )
        assert DefaultAuthorizationPolicy().is_allowed(ctx, Operation.REVIEW_AI_ARTIFACT)

    def test_patient_all_operations_denied(self):
        ctx = AuthenticatedContext(
            actor_id=uuid4(), tenant_id=uuid4(), roles=("patient",), facility_id=None,
        )
        policy = DefaultAuthorizationPolicy()
        for op in Operation:
            assert not policy.is_allowed(ctx, op), f"patient should be denied for {op}"

    def test_caregiver_all_operations_denied(self):
        ctx = AuthenticatedContext(
            actor_id=uuid4(), tenant_id=uuid4(), roles=("caregiver",), facility_id=None,
        )
        policy = DefaultAuthorizationPolicy()
        for op in Operation:
            assert not policy.is_allowed(ctx, op), f"caregiver should be denied for {op}"

    def test_admin_only_admin_operation(self):
        ctx = AuthenticatedContext(
            actor_id=uuid4(), tenant_id=uuid4(), roles=("admin",), facility_id=None,
        )
        policy = DefaultAuthorizationPolicy()
        assert policy.is_allowed(ctx, Operation.ADMIN)
        assert not policy.is_allowed(ctx, Operation.READ_OBSERVATIONS)
        assert not policy.is_allowed(ctx, Operation.WRITE_MEDICATION_PLANS)

    def test_care_coordinator_read_only(self):
        ctx = AuthenticatedContext(
            actor_id=uuid4(), tenant_id=uuid4(), roles=("care_coordinator",), facility_id=uuid4(),
        )
        policy = DefaultAuthorizationPolicy()
        assert policy.is_allowed(ctx, Operation.READ_OBSERVATIONS)
        assert not policy.is_allowed(ctx, Operation.WRITE_OBSERVATIONS)
        assert not policy.is_allowed(ctx, Operation.WRITE_MEDICATION_PLANS)

    def test_field_health_worker_limited(self):
        ctx = AuthenticatedContext(
            actor_id=uuid4(), tenant_id=uuid4(), roles=("field_health_worker",), facility_id=uuid4(),
        )
        policy = DefaultAuthorizationPolicy()
        assert policy.is_allowed(ctx, Operation.READ_OBSERVATIONS)
        assert policy.is_allowed(ctx, Operation.WRITE_OBSERVATIONS)
        assert not policy.is_allowed(ctx, Operation.READ_MEDICATION_PLANS)


class TestMedicationPlanAuthority:
    """Domain-level medication plan authority tests via HTTP."""

    def test_patient_role_denied_by_self_access_check(self, client):
        """Patient role → 403 (self-access unavailable)."""
        actor_id = str(uuid4())
        token = make_jwt(sub=actor_id, tenant_id=str(uuid4()), roles=["patient"])
        resp = client.post(
            "/api/v2/clinical/medication-plans",
            json={"patient_id": str(uuid4()), "medication": "Metformin"},
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_caregiver_role_denied_by_relationship_check(self, client):
        """Caregiver role → 403 (relationship unavailable)."""
        actor_id = str(uuid4())
        token = make_jwt(sub=actor_id, tenant_id=str(uuid4()), roles=["caregiver"])
        resp = client.post(
            "/api/v2/clinical/medication-plans",
            json={"patient_id": str(uuid4()), "medication": "Metformin"},
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_unknown_role_denied(self, client):
        """Unknown role → 403 (deny-by-default)."""
        token = make_jwt(sub=str(uuid4()), tenant_id=str(uuid4()), roles=["unknown_role"])
        resp = client.post(
            "/api/v2/clinical/medication-plans",
            json={"patient_id": str(uuid4()), "medication": "Metformin"},
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_doctor_can_create_plan(self, db_client):
        """Doctor with valid member record + facility scoping → 200."""
        c, sf = db_client
        tid = uuid4()
        fid = uuid4()
        actor_id = uuid4()
        patient_id = uuid4()
        seed_org(sf, tid, "org-a")
        seed_patient(sf, tid, patient_id, facility_id=fid, name="P1")
        seed_member(sf, tid, user_id=actor_id, role="doctor", facility_id=fid)
        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["doctor"], facility_id=str(fid))
        resp = c.post(
            "/api/v2/clinical/medication-plans",
            json={"patient_id": str(patient_id), "medication": "Metformin 500mg"},
            headers=bearer(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["medication_plan_id"]
        assert body["patient_id"] == str(patient_id)


class TestAIApprovalBoundary:
    """Prove AI cannot approve its own artifacts via HTTP."""

    def test_patient_cannot_approve_ai_artifact(self, db_client):
        c, sf = db_client
        tid = uuid4()
        fid = uuid4()
        patient_id = uuid4()
        actor_id = uuid4()
        seed_org(sf, tid, "org")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        artifact = seed_ai_artifact(sf, tid, patient_id)
        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["patient"])
        resp = c.post(
            f"/api/v2/clinical/ai-artifacts/{artifact.id}/review",
            json={"decision": "approve"},
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_caregiver_cannot_approve_ai_artifact(self, client):
        token = make_jwt(sub=str(uuid4()), tenant_id=str(uuid4()), roles=["caregiver"])
        resp = client.post(
            f"/api/v2/clinical/ai-artifacts/{uuid4()}/review",
            json={"decision": "approve"},
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_admin_cannot_approve_ai_artifact(self, client):
        """Admin does not hold REVIEW_AI_ARTIFACT → 403."""
        token = make_jwt(sub=str(uuid4()), tenant_id=str(uuid4()), roles=["admin"])
        resp = client.post(
            f"/api/v2/clinical/ai-artifacts/{uuid4()}/review",
            json={"decision": "approve"},
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_unknown_role_cannot_approve(self, client):
        token = make_jwt(sub=str(uuid4()), tenant_id=str(uuid4()), roles=["ai_assistant"])
        resp = client.post(
            f"/api/v2/clinical/ai-artifacts/{uuid4()}/review",
            json={"decision": "approve"},
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_no_separate_approve_endpoint_exists(self, client):
        """OpenAPI must NOT contain an explicit approve-only endpoint."""
        openapi = client.app.openapi()
        for path in openapi.get("paths", {}):
            lower = path.lower()
            assert "approve" not in lower and "/approve" not in lower, (
                f"Found approve-only endpoint: {path}"
            )


class TestResourceScoping:
    """Facility-based resource scoping tests."""

    def test_doctor_without_facility_denied(self, db_client):
        c, sf = db_client
        tid = uuid4()
        patient_id = uuid4()
        actor_id = uuid4()
        seed_org(sf, tid, "org")
        seed_patient(sf, tid, patient_id, facility_id=uuid4(), name="P")
        seed_member(sf, tid, user_id=actor_id, role="doctor", facility_id=None)
        # No facility_id in JWT
        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["doctor"])
        resp = c.get(
            f"/api/v2/clinical/observations?patient_id={patient_id}",
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_doctor_wrong_facility_denied(self, db_client):
        c, sf = db_client
        tid = uuid4()
        fid_a = uuid4()
        fid_b = uuid4()
        patient_id = uuid4()
        actor_id = uuid4()
        seed_org(sf, tid, "org")
        seed_patient(sf, tid, patient_id, facility_id=fid_b, name="P in B")
        seed_member(sf, tid, user_id=actor_id, role="doctor", facility_id=fid_a)
        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["doctor"], facility_id=str(fid_a))
        resp = c.get(
            f"/api/v2/clinical/observations?patient_id={patient_id}",
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_doctor_correct_facility_can_read(self, db_client):
        c, sf = db_client
        tid = uuid4()
        fid = uuid4()
        patient_id = uuid4()
        actor_id = uuid4()
        seed_org(sf, tid, "org")
        seed_patient(sf, tid, patient_id, facility_id=fid, name="P in F")
        seed_member(sf, tid, user_id=actor_id, role="doctor", facility_id=fid)
        seed_glucose(sf, tid, patient_id, value=120)
        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["doctor"], facility_id=str(fid))
        resp = c.get(
            f"/api/v2/clinical/observations?patient_id={patient_id}",
            headers=bearer(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) >= 1
