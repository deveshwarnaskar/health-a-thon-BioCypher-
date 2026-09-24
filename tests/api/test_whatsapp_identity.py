"""Tests for WhatsApp Identity and Connection API (Gate 10P / WhatsApp Onboarding)."""

from uuid import uuid4

import pytest

from backend.domain.value_objects import PhoneNumber
from tests.api.conftest import (
    bearer,
    make_jwt,
    seed_identity_mapping,
    seed_org,
    seed_patient,
)


def test_whatsapp_identity_unauthenticated(client) -> None:
    """Unauthenticated calls to /api/v2/whatsapp/identity must be rejected with 401."""
    resp = client.get("/api/v2/whatsapp/identity")
    assert resp.status_code == 401


def test_whatsapp_identity_unconnected(db_client) -> None:
    """When a patient has no linked phone, identity status must be 'not_connected'."""
    client, session_factory = db_client
    org_id = uuid4()
    seed_org(session_factory, org_id, "org-unconnected")
    user_id = uuid4()
    patient_id = uuid4()
    seed_patient(session_factory, org_id, patient_id, name="Jane Doe")
    seed_identity_mapping(session_factory, org_id, user_id, patient_id)

    token = make_jwt(sub=str(user_id), tenant_id=str(org_id), roles=["patient"])
    resp = client.get("/api/v2/whatsapp/identity", headers=bearer(token))

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "not_connected"
    assert data["phone_number"] is None
    assert data["phone_number_masked"] is None
    assert "health_logging" in data["capabilities"]


def test_whatsapp_request_verification_invalid_phone(db_client) -> None:
    """Requesting verification with an invalid phone number returns 422."""
    client, session_factory = db_client
    org_id = uuid4()
    seed_org(session_factory, org_id, "org-invalid")
    user_id = uuid4()
    patient_id = uuid4()
    seed_patient(session_factory, org_id, patient_id, name="Jane Doe")
    seed_identity_mapping(session_factory, org_id, user_id, patient_id)

    token = make_jwt(sub=str(user_id), tenant_id=str(org_id), roles=["patient"])
    resp = client.post(
        "/api/v2/whatsapp/identity/request-verification",
        json={"phone_number": "invalid"},
        headers=bearer(token),
    )
    assert resp.status_code == 422


def test_whatsapp_verification_and_connection_lifecycle(db_client) -> None:
    """Full lifecycle: request OTP, verify code, link phone, get connected status, and disconnect."""
    client, session_factory = db_client
    org_id = uuid4()
    seed_org(session_factory, org_id, "org-lifecycle")
    user_id = uuid4()
    patient_id = uuid4()
    seed_patient(session_factory, org_id, patient_id, name="Jane Doe")
    seed_identity_mapping(session_factory, org_id, user_id, patient_id)

    token = make_jwt(sub=str(user_id), tenant_id=str(org_id), roles=["patient"])
    headers = bearer(token)

    # 1. Request verification
    req_resp = client.post(
        "/api/v2/whatsapp/identity/request-verification",
        json={"phone_number": "+919876543210"},
        headers=headers,
    )
    assert req_resp.status_code == 200
    req_data = req_resp.json()
    assert req_data["success"] is True
    assert req_data["phone_number"] == "+919876543210"
    dev_code = req_data.get("dev_code")
    assert dev_code is not None

    # 2. Verify with wrong code -> 400
    bad_resp = client.post(
        "/api/v2/whatsapp/identity/verify-code",
        json={"phone_number": "+919876543210", "code": "000000"},
        headers=headers,
    )
    assert bad_resp.status_code == 400

    # 3. Verify with valid dev_code -> 200 connected
    verify_resp = client.post(
        "/api/v2/whatsapp/identity/verify-code",
        json={"phone_number": "+919876543210", "code": dev_code},
        headers=headers,
    )
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["status"] == "connected"
    assert verify_data["phone_number"] == "+919876543210"
    assert verify_data["phone_number_masked"] == "+********3210"

    # 4. GET /identity now returns connected
    get_resp = client.get("/api/v2/whatsapp/identity", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "connected"
    assert get_resp.json()["phone_number_masked"] == "+********3210"

    # 5. Disconnect -> unlinks phone, returns not_connected
    disc_resp = client.post("/api/v2/whatsapp/identity/disconnect", headers=headers)
    assert disc_resp.status_code == 200
    assert disc_resp.json()["status"] == "not_connected"

    # 6. GET /identity now returns not_connected
    final_get = client.get("/api/v2/whatsapp/identity", headers=headers)
    assert final_get.status_code == 200
    assert final_get.json()["status"] == "not_connected"


def test_whatsapp_identity_caregiver_context(db_client) -> None:
    """A caregiver can query WhatsApp connection status for their linked patient."""
    from tests.api.conftest import seed_caregiver_relationship

    client, session_factory = db_client
    org_id = uuid4()
    seed_org(session_factory, org_id, "org-caregiver-wa")
    caregiver_user_id = uuid4()
    patient_id = uuid4()
    seed_patient(session_factory, org_id, patient_id, name="Parent Patient")
    seed_caregiver_relationship(
        session_factory,
        org_id,
        patient_id=patient_id,
        caregiver_user_id=caregiver_user_id,
    )

    token = make_jwt(sub=str(caregiver_user_id), tenant_id=str(org_id), roles=["caregiver"])
    resp = client.get("/api/v2/whatsapp/identity", headers=bearer(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_connected"
