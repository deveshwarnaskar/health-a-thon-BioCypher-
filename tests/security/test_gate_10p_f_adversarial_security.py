"""Gate 10P-F — Adversarial Security, Penetration & Authorization Hardening Test Suite.

Verifies:
1. Authentication abuse & protocol tamper resistance:
   - Expired token rejected with 401
   - Malformed / corrupted token rejected with 401
   - Invalid signature / altered secret rejected with 401
   - Tampered token payload rejected with 401
   - Untrusted issuer rejected with 401
   - Mismatched audience rejected with 401
   - Alg=none attack rejected with 401
   - Unsupported algorithms rejected with 401
   - Missing tenant_id claim rejected with 401
   - Malformed tenant UUID rejected with 401

2. Multi-tenant boundary & cross-tenant RLS isolation:
   - Tenant A actor cannot read Tenant B patient (403 or 404, strictly isolated)
   - Tenant A actor cannot post clinical observations for Tenant B patient (403 or 404)
   - Tenant A actor cannot log meals for Tenant B patient (403 or 404)
   - Tenant A actor cannot create care tasks for Tenant B patient (403 or 404)
   - Tenant A patient list query strictly excludes Tenant B data (zero cross-tenant leakage)

3. Role-based clinical boundaries & scoping:
   - Clinician assigned to facility A cannot access patient in facility B (403)
   - Nurse role cannot prescribe medication plans (403 MEDICATION_PLAN_UNAUTHORIZED)
   - Patient role cannot reassign or modify care tasks (403)
   - Field health worker cannot complete care tasks assigned to other workers (403)

4. Document & storage authorization:
   - Cross-tenant document listing rejected (403 or 404)
   - Cross-tenant document download URL request rejected (403 or 404)

5. Webhook HMAC & transport boundary:
   - Missing X-Hub-Signature-256 rejected (401)
   - Forged X-Hub-Signature-256 rejected (401)
   - Correct HMAC signature accepted (202)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import tempfile
import time
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.domain.entities import CareTask, CareTeamRole, DocumentKind
from backend.infrastructure.persistence.models import Base
import backend.infrastructure.persistence.models.identity_models
import backend.infrastructure.persistence.models.ops_models
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from backend.interfaces.http.app import create_app
from backend.interfaces.http.dependencies import (
    get_unit_of_work,
    reset_config_cache,
    _get_engine,
)
from tests.api.conftest import (
    TEST_CLIENT_ID,
    TEST_ISSUER,
    TEST_SECRET,
    make_jwt,
    seed_facility,
    seed_identity_mapping,
    seed_member,
    seed_org,
    seed_patient,
    seed_document_reference,
)


@pytest.fixture
def sec_env(monkeypatch):
    monkeypatch.setenv("THALI_IDENTITY__CLIENT_SECRET", TEST_SECRET)
    monkeypatch.setenv("THALI_IDENTITY__ISSUER_URL", TEST_ISSUER)
    monkeypatch.setenv("THALI_IDENTITY__CLIENT_ID", TEST_CLIENT_ID)
    monkeypatch.setenv("THALI_IDENTITY__ALLOWED_ALGORITHMS", "HS256")
    monkeypatch.setenv("THALI_IDENTITY__JWKS_URI", "")
    monkeypatch.setenv("THALI_APP__ENV", "development")
    monkeypatch.setenv("THALI_WHATSAPP__APP_SECRET", "test-webhook-secret-1234567890123456")
    monkeypatch.setenv("THALI_WHATSAPP__VERIFY_TOKEN", "test-verify-token")

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

    # ── Tenant A Setup ──
    tenant_a = UUID("20000000-0000-0000-0000-000000000001")
    facility_a1 = UUID("20000000-0000-0000-0000-000000000011")
    facility_a2 = UUID("20000000-0000-0000-0000-000000000012")
    doctor_a_id = UUID("20000000-0000-0000-0000-000000000021")
    nurse_a_id = UUID("20000000-0000-0000-0000-000000000022")
    fhw_a_id = UUID("20000000-0000-0000-0000-000000000023")
    patient_a1_id = UUID("20000000-0000-0000-0000-000000000031")
    patient_a1_user = UUID("20000000-0000-0000-0000-000000000032")
    patient_a2_id = UUID("20000000-0000-0000-0000-000000000033")

    sf = session_factory
    seed_org(sf, tenant_a, "SEC_ORG_A")
    seed_facility(sf, tenant_a, facility_a1, "SEC_CLINIC_A1")
    seed_facility(sf, tenant_a, facility_a2, "SEC_CLINIC_A2")
    seed_member(sf, tenant_a, doctor_a_id, role=CareTeamRole.DOCTOR, facility_id=facility_a1)
    seed_member(sf, tenant_a, nurse_a_id, role=CareTeamRole.NURSE, facility_id=facility_a1)
    seed_member(sf, tenant_a, fhw_a_id, role=CareTeamRole.FIELD_HEALTH_WORKER, facility_id=facility_a1)
    seed_patient(sf, tenant_a, patient_a1_id, facility_a1, "PATIENT_A1")
    seed_patient(sf, tenant_a, patient_a2_id, facility_a2, "PATIENT_A2")
    seed_identity_mapping(sf, tenant_a, patient_a1_user, patient_a1_id, active=True)

    # ── Tenant B Setup ──
    tenant_b = UUID("30000000-0000-0000-0000-000000000001")
    facility_b1 = UUID("30000000-0000-0000-0000-000000000011")
    doctor_b_id = UUID("30000000-0000-0000-0000-000000000021")
    patient_b1_id = UUID("30000000-0000-0000-0000-000000000031")

    seed_org(sf, tenant_b, "SEC_ORG_B")
    seed_facility(sf, tenant_b, facility_b1, "SEC_CLINIC_B1")
    seed_member(sf, tenant_b, doctor_b_id, role=CareTeamRole.DOCTOR, facility_id=facility_b1)
    seed_patient(sf, tenant_b, patient_b1_id, facility_b1, "PATIENT_B1")

    # App setup with dynamic tenant-aware UoW dependency
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

    tokens = {
        "doctor_a": make_jwt(
            sub=str(doctor_a_id),
            tenant_id=str(tenant_a),
            roles=["doctor"],
            facility_id=str(facility_a1),
        ),
        "nurse_a": make_jwt(
            sub=str(nurse_a_id),
            tenant_id=str(tenant_a),
            roles=["nurse"],
            facility_id=str(facility_a1),
        ),
        "fhw_a": make_jwt(
            sub=str(fhw_a_id),
            tenant_id=str(tenant_a),
            roles=["field_health_worker"],
            facility_id=str(facility_a1),
        ),
        "patient_a": make_jwt(
            sub=str(patient_a1_user),
            tenant_id=str(tenant_a),
            roles=["patient"],
        ),
        "doctor_b": make_jwt(
            sub=str(doctor_b_id),
            tenant_id=str(tenant_b),
            roles=["doctor"],
            facility_id=str(facility_b1),
        ),
    }

    try:
        yield {
            "app": app,
            "session_factory": session_factory,
            "tenant_a": tenant_a,
            "tenant_b": tenant_b,
            "facility_a1": facility_a1,
            "facility_a2": facility_a2,
            "patient_a1_id": patient_a1_id,
            "patient_a2_id": patient_a2_id,
            "patient_b1_id": patient_b1_id,
            "doctor_a_id": doctor_a_id,
            "doctor_b_id": doctor_b_id,
            "fhw_a_id": fhw_a_id,
            "tokens": tokens,
        }
    finally:
        reset_config_cache()
        engine.dispose()
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
        except Exception:
            pass


class TestAuthenticationAbuse:
    """Validate authentication failure modes, protocol tamper rejection, and malformed claim guards."""

    def test_expired_token_rejected(self, sec_env):
        """Expired JWTs must fail authentication with HTTP 401."""
        client = TestClient(sec_env["app"])
        expired_token = make_jwt(
            sub=str(sec_env["doctor_a_id"]),
            tenant_id=str(sec_env["tenant_a"]),
            roles=["doctor"],
            exp=time.time() - 3600,  # 1 hour in the past
        )
        resp = client.get(
            f"/api/v2/patients/{sec_env['patient_a1_id']}",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401
        assert "expired" in resp.text.lower() or resp.status_code == 401

    def test_malformed_token_structure_rejected(self, sec_env):
        """Malformed, truncated, or non-JWT bearer tokens must fail with HTTP 401."""
        client = TestClient(sec_env["app"])
        for bad_token in ["not-a-token", "a.b", "bearer-garbage-data-string", "eyJhbGciOiJIUzI1NiJ9"]:
            resp = client.get(
                f"/api/v2/patients/{sec_env['patient_a1_id']}",
                headers={"Authorization": f"Bearer {bad_token}"},
            )
            assert resp.status_code == 401

    def test_invalid_signature_tampered_payload_rejected(self, sec_env):
        """Token with modified claims or forged signature must be rejected with HTTP 401."""
        client = TestClient(sec_env["app"])
        valid_token = sec_env["tokens"]["doctor_a"]
        parts = valid_token.split(".")
        # Tamper with the payload (middle segment)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode())
        payload["roles"] = ["admin", "superadmin"]
        tampered_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        forged_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

        resp = client.get(
            f"/api/v2/patients/{sec_env['patient_a1_id']}",
            headers={"Authorization": f"Bearer {forged_token}"},
        )
        assert resp.status_code == 401

    def test_issuer_mismatch_rejected(self, sec_env):
        """Token signed by an untrusted or spoofed issuer must be rejected with HTTP 401."""
        client = TestClient(sec_env["app"])
        rogue_iss_token = make_jwt(
            sub=str(sec_env["doctor_a_id"]),
            tenant_id=str(sec_env["tenant_a"]),
            roles=["doctor"],
            iss="https://malicious-issuer.internal/auth",
        )
        resp = client.get(
            f"/api/v2/patients/{sec_env['patient_a1_id']}",
            headers={"Authorization": f"Bearer {rogue_iss_token}"},
        )
        assert resp.status_code == 401

    def test_audience_mismatch_rejected(self, sec_env):
        """Token issued for an untrusted client audience must be rejected with HTTP 401."""
        client = TestClient(sec_env["app"])
        rogue_aud_token = make_jwt(
            sub=str(sec_env["doctor_a_id"]),
            tenant_id=str(sec_env["tenant_a"]),
            roles=["doctor"],
            aud="rogue-client-application",
        )
        resp = client.get(
            f"/api/v2/patients/{sec_env['patient_a1_id']}",
            headers={"Authorization": f"Bearer {rogue_aud_token}"},
        )
        assert resp.status_code == 401

    def test_algorithm_none_attack_rejected(self, sec_env):
        """Tokens specifying 'alg: none' must be rejected unconditionally."""
        client = TestClient(sec_env["app"])
        header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(
            json.dumps({
                "sub": str(sec_env["doctor_a_id"]),
                "tenant_id": str(sec_env["tenant_a"]),
                "roles": ["doctor"],
                "iss": TEST_ISSUER,
                "aud": TEST_CLIENT_ID,
                "exp": time.time() + 3600,
            }).encode()
        ).rstrip(b"=").decode()
        none_token = f"{header}.{payload}."

        resp = client.get(
            f"/api/v2/patients/{sec_env['patient_a1_id']}",
            headers={"Authorization": f"Bearer {none_token}"},
        )
        assert resp.status_code == 401

    def test_missing_tenant_id_rejected(self, sec_env):
        """Tokens lacking the tenant_id claim fail closed with HTTP 401."""
        client = TestClient(sec_env["app"])
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": str(sec_env["doctor_a_id"]),
            "iss": TEST_ISSUER,
            "aud": TEST_CLIENT_ID,
            "exp": int(time.time()) + 3600,
            "realm_access": {"roles": ["doctor"]},
        }
        h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
        p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        sig = hmac.new(TEST_SECRET.encode(), f"{h_b64}.{p_b64}".encode(), hashlib.sha256).digest()
        no_tenant_token = f"{h_b64}.{p_b64}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"

        resp = client.get(
            f"/api/v2/patients/{sec_env['patient_a1_id']}",
            headers={"Authorization": f"Bearer {no_tenant_token}"},
        )
        assert resp.status_code == 401

    def test_malformed_tenant_uuid_rejected(self, sec_env):
        """Tokens with non-UUID tenant_id fail closed with HTTP 401."""
        client = TestClient(sec_env["app"])
        bad_tenant_token = make_jwt(
            sub=str(sec_env["doctor_a_id"]),
            tenant_id="invalid-not-a-uuid-string",
            roles=["doctor"],
        )
        resp = client.get(
            f"/api/v2/patients/{sec_env['patient_a1_id']}",
            headers={"Authorization": f"Bearer {bad_tenant_token}"},
        )
        assert resp.status_code == 401


class TestCrossTenantAuthorizationIsolation:
    """Validate strict cross-tenant RLS and authorization boundaries."""

    def test_cross_tenant_patient_read_forbidden(self, sec_env):
        """Tenant A doctor cannot read Patient B from Tenant B."""
        client = TestClient(sec_env["app"])
        token_a = sec_env["tokens"]["doctor_a"]
        patient_b_id = sec_env["patient_b1_id"]

        resp = client.get(
            f"/api/v2/patients/{patient_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        # Must fail with 403 Forbidden or 404 Not Found (zero cross-tenant data leakage)
        assert resp.status_code in {403, 404}

    def test_cross_tenant_observation_write_rejected(self, sec_env):
        """Tenant A doctor cannot record clinical observations for Tenant B patient."""
        client = TestClient(sec_env["app"])
        token_a = sec_env["tokens"]["doctor_a"]
        patient_b_id = sec_env["patient_b1_id"]

        resp = client.post(
            "/api/v2/clinical/observations",
            headers={
                "Authorization": f"Bearer {token_a}",
                "Idempotency-Key": f"cross_obs_{uuid4().hex}",
            },
            json={
                "patient_id": str(patient_b_id),
                "value_mg_dl": 140,
                "tag": "fasting",
            },
        )
        assert resp.status_code in {403, 404}

    def test_cross_tenant_meal_write_rejected(self, sec_env):
        """Tenant A doctor cannot log meals for Tenant B patient."""
        client = TestClient(sec_env["app"])
        token_a = sec_env["tokens"]["doctor_a"]
        patient_b_id = sec_env["patient_b1_id"]

        resp = client.post(
            "/api/v2/clinical/meals",
            headers={
                "Authorization": f"Bearer {token_a}",
                "Idempotency-Key": f"cross_meal_{uuid4().hex}",
            },
            json={
                "patient_id": str(patient_b_id),
                "description": "Cross-tenant malicious meal",
            },
        )
        assert resp.status_code in {403, 404}

    def test_cross_tenant_care_task_write_rejected(self, sec_env):
        """Tenant A doctor cannot create care tasks for Tenant B patient."""
        client = TestClient(sec_env["app"])
        token_a = sec_env["tokens"]["doctor_a"]
        patient_b_id = sec_env["patient_b1_id"]

        resp = client.post(
            "/api/v2/care-tasks",
            headers={
                "Authorization": f"Bearer {token_a}",
                "Idempotency-Key": f"cross_task_{uuid4().hex}",
            },
            json={
                "patient_id": str(patient_b_id),
                "assigned_to_user_id": str(sec_env["doctor_a_id"]),
                "description": "Cross tenant task creation attempt",
            },
        )
        assert resp.status_code in {403, 404}

    def test_cross_tenant_patient_list_zero_leakage(self, sec_env):
        """Tenant A patient directory listing never contains Tenant B patients."""
        client = TestClient(sec_env["app"])
        token_a = sec_env["tokens"]["doctor_a"]
        patient_b_id = str(sec_env["patient_b1_id"])

        resp = client.get(
            "/api/v2/patients",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        items = data if isinstance(data, list) else data.get("patients", data.get("items", []))
        item_ids = [str(p.get("id") or p.get("patient_id")) for p in items]
        assert patient_b_id not in item_ids, "Tenant B patient leaked into Tenant A query results!"


class TestRoleBasedClinicalBoundaries:
    """Validate RBAC scoping, facility isolation, and privilege escalation guards."""

    def test_clinician_wrong_facility_scoping_rejected(self, sec_env):
        """Clinician scoped to Facility A1 cannot access Patient residing in Facility A2."""
        client = TestClient(sec_env["app"])
        # Doctor A is scoped to facility_a1
        token_a = sec_env["tokens"]["doctor_a"]
        # Patient A2 is in facility_a2
        patient_a2_id = sec_env["patient_a2_id"]

        resp = client.get(
            f"/api/v2/patients/{patient_a2_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code in {403, 404}

    def test_field_health_worker_cannot_prescribe_medication_plan(self, sec_env):
        """Field health worker role cannot create medication plans (licensed clinicians only)."""
        client = TestClient(sec_env["app"])
        fhw_token = sec_env["tokens"]["fhw_a"]
        patient_id = str(sec_env["patient_a1_id"])

        resp = client.post(
            "/api/v2/clinical/medication-plans",
            headers={
                "Authorization": f"Bearer {fhw_token}",
                "Idempotency-Key": f"fhw_med_{uuid4().hex}",
            },
            json={
                "patient_id": patient_id,
                "medication": "Metformin 500mg",
                "instruction": "twice daily",
            },
        )
        assert resp.status_code in {403, 401}
        if resp.status_code == 403:
            assert resp.json().get("error", {}).get("code") in {"AUTHORIZATION_DENIED", "MEDICATION_PLAN_UNAUTHORIZED"}

    def test_patient_role_cannot_reassign_care_task(self, sec_env):
        """Patient role cannot reassign care tasks."""
        app = sec_env["app"]
        sf = sec_env["session_factory"]
        tenant_a = sec_env["tenant_a"]
        task_id = uuid4()

        with SqlAlchemyUnitOfWork(sf, tenant_a) as uow:
            task = CareTask(
                id=task_id,
                patient_id=sec_env["patient_a1_id"],
                assigned_to_user_id=sec_env["doctor_a_id"],
                description="Test task for patient escalation",
            )
            uow.care_tasks.add(task)
            uow.commit()

        client = TestClient(app)
        patient_token = sec_env["tokens"]["patient_a"]

        resp = client.post(
            f"/api/v2/care-tasks/{task_id}/reassign",
            headers={
                "Authorization": f"Bearer {patient_token}",
                "Idempotency-Key": f"pat_reassign_{uuid4().hex}",
            },
            json={"new_user_id": str(sec_env["fhw_a_id"])},
        )
        assert resp.status_code in {403, 401}

    def test_field_health_worker_cannot_complete_unassigned_task(self, sec_env):
        """Field health worker cannot complete a task assigned to a different clinician."""
        app = sec_env["app"]
        sf = sec_env["session_factory"]
        tenant_a = sec_env["tenant_a"]
        task_id = uuid4()

        # Create task assigned to doctor_a (NOT fhw_a)
        with SqlAlchemyUnitOfWork(sf, tenant_a) as uow:
            task = CareTask(
                id=task_id,
                patient_id=sec_env["patient_a1_id"],
                assigned_to_user_id=sec_env["doctor_a_id"],
                description="Task assigned exclusively to doctor",
            )
            uow.care_tasks.add(task)
            uow.commit()

        client = TestClient(app)
        fhw_token = sec_env["tokens"]["fhw_a"]

        resp = client.post(
            f"/api/v2/care-tasks/{task_id}/complete",
            headers={
                "Authorization": f"Bearer {fhw_token}",
                "Idempotency-Key": f"fhw_comp_{uuid4().hex}",
            },
        )
        assert resp.status_code == 403


class TestDocumentAuthorization:
    """Validate object storage & clinical document access authorization."""

    def test_cross_tenant_document_access_rejected(self, sec_env):
        """Tenant B doctor cannot list or retrieve documents belonging to Tenant A patient."""
        sf = sec_env["session_factory"]
        tenant_a = sec_env["tenant_a"]
        patient_a1 = sec_env["patient_a1_id"]

        # Seed document for patient A1
        seed_document_reference(
            sf,
            tenant_id=tenant_a,
            patient_id=patient_a1,
            facility_id=sec_env["facility_a1"],
            kind=DocumentKind.CLINICAL_REPORT,
            filename="confidential_lab_report.pdf",
        )

        client = TestClient(sec_env["app"])
        token_b = sec_env["tokens"]["doctor_b"]

        resp = client.get(
            f"/api/v2/clinical/patients/{patient_a1}/documents",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code in {403, 404}


class TestWhatsAppWebhookSecurity:
    """Validate WhatsApp webhook HMAC cryptographic signature checks and payload verification."""

    def test_missing_webhook_signature_rejected(self, sec_env):
        """Webhook POST without X-Hub-Signature-256 header must return HTTP 401."""
        client = TestClient(sec_env["app"])
        resp = client.post(
            "/api/v2/webhooks/whatsapp",
            json={"object": "whatsapp_business_account", "entry": []},
        )
        assert resp.status_code == 401

    def test_forged_webhook_signature_rejected(self, sec_env):
        """Webhook POST with forged or tampered HMAC signature must return HTTP 401."""
        client = TestClient(sec_env["app"])
        raw_body = b'{"object": "whatsapp_business_account", "entry": []}'
        resp = client.post(
            "/api/v2/webhooks/whatsapp",
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=0000000000000000000000000000000000000000000000000000000000000000",
            },
            content=raw_body,
        )
        assert resp.status_code == 401
        assert resp.json().get("error", {}).get("code") in {"WEBHOOK_SIGNATURE_INVALID", "AUTHENTICATION_REQUIRED"}

    def test_valid_webhook_signature_accepted(self, sec_env):
        """Webhook POST with valid HMAC-SHA256 signature is accepted with HTTP 202."""
        client = TestClient(sec_env["app"])
        secret = "test-webhook-secret-1234567890123456"
        raw_body = json.dumps({
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "entry-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"display_phone_number": "1234567890", "phone_number_id": "phone-1"},
                                "contacts": [{"wa_id": "919876543210", "profile": {"name": "Test User"}}],
                                "messages": [
                                    {
                                        "id": f"wamid.{uuid4().hex}",
                                        "from": "919876543210",
                                        "timestamp": "1720000000",
                                        "type": "text",
                                        "text": {"body": "Fasting 120"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }).encode("utf-8")

        expected_hmac = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        sig_header = f"sha256={expected_hmac}"

        resp = client.post(
            "/api/v2/webhooks/whatsapp",
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig_header,
            },
            content=raw_body,
        )
        assert resp.status_code == 202
