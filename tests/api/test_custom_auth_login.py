"""Tests for custom auth API endpoints (Task 2):

- POST /api/v2/auth/login
- POST /api/v2/auth/refresh
- POST /api/v2/auth/logout
- POST /api/v2/auth/register
- Token authorization round-trip with issued RS256 token
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.infrastructure.auth.password_service import hash_password
from backend.infrastructure.persistence.models.tenant_models import OrganizationModel
from backend.infrastructure.persistence.models.user_models import UserModel
from backend.interfaces.http.dependencies import (
    _get_session_factory,
    get_db_url,
    get_token_service,
)
from tests.api.conftest import bearer, make_jwt


@pytest.fixture
def auth_test_user(client):
    """Seed a tenant and user for testing login."""
    session_factory = _get_session_factory(get_db_url())
    with session_factory() as session:
        tenant_id = uuid4()
        org = OrganizationModel(
            id=tenant_id,
            name="Auth Test Org",
            slug=f"org-{uuid4().hex[:8]}",
            active=True,
        )
        session.add(org)
        session.commit()

        user = UserModel(
            id=uuid4(),
            email="admin@thali.local",
            hashed_password=hash_password("admin-password-123"),
            role="admin",
            tenant_id=tenant_id,
            active=True,
        )
        session.add(user)
        session.commit()

        return {
            "user_id": str(user.id),
            "email": "admin@thali.local",
            "password": "admin-password-123",
            "tenant_id": str(tenant_id),
            "role": "admin",
        }


def test_login_successful_returns_jwt(client: TestClient, auth_test_user):
    resp = client.post(
        "/api/v2/auth/login",
        json={"email": auth_test_user["email"], "password": auth_test_user["password"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0

    token_service = get_token_service()
    claims = token_service.verify_token(data["access_token"])
    assert claims["sub"] == auth_test_user["user_id"]
    assert claims["tenant_id"] == auth_test_user["tenant_id"]
    assert claims["role"] == auth_test_user["role"]


def test_login_wrong_password_returns_401(client: TestClient, auth_test_user):
    resp = client.post(
        "/api/v2/auth/login",
        json={"email": auth_test_user["email"], "password": "wrong-password"},
    )
    assert resp.status_code == 401
    body = resp.json()
    msg = body.get("error", {}).get("message") or body.get("detail", "")
    assert "invalid" in msg.lower() or "credentials" in msg.lower()


def test_login_unknown_email_returns_401(client: TestClient):
    resp = client.post(
        "/api/v2/auth/login",
        json={"email": "nobody@nowhere.com", "password": "any-password"},
    )
    assert resp.status_code == 401


def test_refresh_token_flow(client: TestClient, auth_test_user):
    # 1. Login to get tokens
    login_resp = client.post(
        "/api/v2/auth/login",
        json={"email": auth_test_user["email"], "password": auth_test_user["password"]},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    # 2. Refresh
    refresh_resp = client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    assert "access_token" in data

    claims = get_token_service().verify_token(data["access_token"])
    assert claims["sub"] == auth_test_user["user_id"]


def test_refresh_with_invalid_token_returns_401(client: TestClient):
    resp = client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": "not-a-valid-refresh-token"},
    )
    assert resp.status_code == 401


def test_logout_endpoint_succeeds(client: TestClient):
    resp = client.post(
        "/api/v2/auth/logout",
        json={"refresh_token": "any-token"},
    )
    assert resp.status_code == 204


def test_issued_access_token_authenticates_protected_routes(client: TestClient, auth_test_user):
    login_resp = client.post(
        "/api/v2/auth/login",
        json={"email": auth_test_user["email"], "password": auth_test_user["password"]},
    )
    access_token = login_resp.json()["access_token"]

    verify_resp = client.get(
        "/api/v2/auth/verify",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    assert data["actor_id"] == auth_test_user["user_id"]
    assert data["tenant_id"] == auth_test_user["tenant_id"]
    assert "admin" in data["roles"]


def test_register_requires_admin(client: TestClient, auth_test_user):
    # 1. Without admin token → 403
    non_admin_token = make_jwt(
        sub=str(uuid4()),
        tenant_id=auth_test_user["tenant_id"],
        roles=["doctor"],
    )
    new_email = f"newuser-{uuid4().hex[:6]}@thali.local"
    resp = client.post(
        "/api/v2/auth/register",
        headers=bearer(non_admin_token),
        json={
            "email": new_email,
            "password": "new-user-password",
            "role": "doctor",
            "tenant_id": auth_test_user["tenant_id"],
        },
    )
    assert resp.status_code == 403

    # 2. With admin token → 201
    admin_token = make_jwt(
        sub=auth_test_user["user_id"],
        tenant_id=auth_test_user["tenant_id"],
        roles=["admin"],
    )
    resp2 = client.post(
        "/api/v2/auth/register",
        headers=bearer(admin_token),
        json={
            "email": new_email,
            "password": "new-user-password",
            "role": "doctor",
            "tenant_id": auth_test_user["tenant_id"],
        },
    )
    assert resp2.status_code == 201
    data = resp2.json()
    assert data["email"] == new_email
    assert data["role"] == "doctor"


def test_signup_creates_patient_and_issues_jwt(client: TestClient):
    signup_email = f"patient-{uuid4().hex[:6]}@thali.dev"
    resp = client.post(
        "/api/v2/auth/signup",
        json={
            "email": signup_email,
            "password": "patient-strong-password-123",
            "name": "Ananya Sharma",
            "phone": "+919876543210",
            "role": "patient",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    token_service = get_token_service()
    claims = token_service.verify_token(data["access_token"])
    assert claims["role"] == "patient"

    # Authenticate /verify with the newly issued token
    verify_resp = client.get("/api/v2/auth/verify", headers=bearer(data["access_token"]))
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert "patient" in verify_data["roles"]

    # The number provided at signup must NOT be stored or connected to
    # WhatsApp: connection happens only through the explicit OTP flow, so the
    # in-app connect popup keeps appearing until the patient verifies.
    identity_resp = client.get("/api/v2/whatsapp/identity", headers=bearer(data["access_token"]))
    assert identity_resp.status_code == 200
    identity_data = identity_resp.json()
    assert identity_data["status"] == "not_connected"
    assert identity_data["phone_number"] is None


def test_signup_duplicate_email_returns_409(client: TestClient, auth_test_user):
    resp = client.post(
        "/api/v2/auth/signup",
        json={
            "email": auth_test_user["email"],
            "password": "some-valid-password",
        },
    )
    assert resp.status_code == 409


def test_signup_short_password_returns_400(client: TestClient):
    resp = client.post(
        "/api/v2/auth/signup",
        json={
            "email": f"user-{uuid4().hex[:6]}@thali.dev",
            "password": "short",
        },
    )
    assert resp.status_code == 400


def test_forgot_and_reset_password_flow(client: TestClient, auth_test_user):
    # 1. Request forgot password
    forgot_resp = client.post(
        "/api/v2/auth/forgot-password",
        json={"email": auth_test_user["email"]},
    )
    assert forgot_resp.status_code == 200
    forgot_data = forgot_resp.json()
    assert forgot_data["status"] == "ok"
    reset_token = forgot_data.get("reset_token")
    assert reset_token is not None

    # 2. Reset password with token
    new_pw = "new-secure-password-456"
    reset_resp = client.post(
        "/api/v2/auth/reset-password",
        json={"token": reset_token, "new_password": new_pw},
    )
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "ok"

    # 3. Old password fails
    old_login = client.post(
        "/api/v2/auth/login",
        json={"email": auth_test_user["email"], "password": auth_test_user["password"]},
    )
    assert old_login.status_code == 401

    # 4. New password succeeds
    new_login = client.post(
        "/api/v2/auth/login",
        json={"email": auth_test_user["email"], "password": new_pw},
    )
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()


def test_signup_stores_phone_and_delete_account_flow(client: TestClient):
    """Verifies that signup stores phone, delete account verifies phone match, and permanently deletes user."""
    email = f"delete-me-{uuid4().hex[:6]}@thali.dev"
    password = "delete-secure-password-123"
    phone = "+91 98765 43210"

    # 1. Sign up with phone
    signup_resp = client.post(
        "/api/v2/auth/signup",
        json={
            "email": email,
            "password": password,
            "name": "Delete Tester",
            "phone": phone,
            "role": "patient",
        },
    )
    assert signup_resp.status_code == 201
    tokens = signup_resp.json()
    access_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Check context returns phone
    ctx_resp = client.get("/api/v2/auth/context", headers=headers)
    assert ctx_resp.status_code == 200
    ctx_data = ctx_resp.json()
    assert ctx_data.get("phone") == phone

    # 3. Attempt deletion with mismatching phone fails
    del_fail_resp = client.request(
        "DELETE",
        "/api/v2/auth/account",
        headers=headers,
        json={"phone": "9999999999"},
    )
    assert del_fail_resp.status_code == 400
    fail_detail = del_fail_resp.json().get("detail", "")
    assert "match" in fail_detail.lower()

    # 4. Attempt deletion with matching phone succeeds
    del_ok_resp = client.request(
        "DELETE",
        "/api/v2/auth/account",
        headers=headers,
        json={"phone": "9876543210"},
    )
    assert del_ok_resp.status_code == 200
    del_data = del_ok_resp.json()
    assert del_data["status"] == "ok"

    # 5. Subsequent login fails because user account is permanently deleted
    login_resp = client.post(
        "/api/v2/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 401


