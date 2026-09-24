"""Adversarial Security Test Suite for Hardened Authentication & Authorization.

Validates:
- Case A: Wrong password returns 401 with generic error.
- Case B: Unknown email returns 401 (timing & enumeration defense).
- Case C: Disabled/suspended account returns 403.
- Case D: Account lockout triggers after 5 failed attempts (returns 423 Locked).
- Case E: Successful login resets failed attempt counter.
- Case F: Session persistence and device/client binding in user_sessions.
- Case G: Refresh token rotation issues new access and new refresh tokens; marks old token used.
- Case H: Refresh token replay / reuse detection revokes entire session family and returns 401.
- Case I: Revoked session rejects subsequent refresh attempts.
- Case J: Stateful logout terminates session and invalidates refresh tokens.
- Case K: Single-use password reset tokens: second usage attempt fails with 400.
- Case L: Password reset terminates all existing active user sessions.
- Case M: Tampered JWT signature is rejected.
- Case N: Algorithm 'none' attack is rejected.
- Case O: Doctor signup without invite code marks status PENDING_VERIFICATION.
- Case P: Doctor signup with verified invite code activates clinician record.
- Case Q: Patient self-registration auto-provisions UHID and active identity mapping.
- Case R: Caregiver self-registration does NOT auto-grant patient access.
- Case S: Authenticated password change revokes existing sessions.
- Case T: Key rotation verifies tokens signed with rotated kid.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from backend.infrastructure.auth.password_service import hash_password, verify_password
from backend.infrastructure.auth.session_service import SessionService
from backend.infrastructure.auth.token_service import TokenService
from backend.infrastructure.persistence.models.identity_models import IdentityPatientMappingModel
from backend.infrastructure.persistence.models.patient_models import PatientModel
from backend.infrastructure.persistence.models.tenant_models import OrganizationModel
from backend.infrastructure.persistence.models.user_models import (
    PasswordResetTokenModel,
    RefreshTokenFamilyModel,
    SecurityEventModel,
    UserModel,
    UserSessionModel,
    UserStatus,
)
from backend.interfaces.http.dependencies import _get_session_factory, get_db_url, get_token_service
from tests.api.conftest import bearer


@pytest.fixture
def hardened_tenant_and_user(client: TestClient):
    """Fixture providing a seeded tenant and user for security tests."""
    session_factory = _get_session_factory(get_db_url())
    with session_factory() as session:
        tenant_id = uuid4()
        org = OrganizationModel(
            id=tenant_id,
            name="Security Test Hospital",
            slug=f"sec-{uuid4().hex[:8]}",
            active=True,
        )
        session.add(org)
        session.commit()

        user_id = uuid4()
        user = UserModel(
            id=user_id,
            email=f"user-{uuid4().hex[:6]}@security.thali.dev",
            hashed_password=hash_password("CorrectHorseBatteryStaple!123"),
            role="patient",
            tenant_id=tenant_id,
            active=True,
            status=UserStatus.ACTIVE.value,
            failed_login_attempts=0,
        )
        session.add(user)
        session.commit()

        return {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "email": user.email,
            "password": "CorrectHorseBatteryStaple!123",
        }


def error_message(resp) -> str:
    """Extract error message from standard or wrapped JSON error response."""
    body = resp.json()
    err = body.get("error")
    if isinstance(err, dict):
        return err.get("message", "")
    return body.get("detail", "")


def test_case_a_wrong_password_returns_401(client: TestClient, hardened_tenant_and_user):
    """Case A: Authentication failure returns 401 without leaking internal details."""
    resp = client.post(
        "/api/v2/auth/login",
        json={"email": hardened_tenant_and_user["email"], "password": "WrongPassword999!"},
    )
    assert resp.status_code == 401
    assert "invalid" in error_message(resp).lower() or "credentials" in error_message(resp).lower()


def test_case_b_unknown_email_returns_401(client: TestClient):
    """Case B: Unknown email returns identical 401 error message to prevent enumeration."""
    resp = client.post(
        "/api/v2/auth/login",
        json={"email": f"nonexistent-{uuid4().hex[:8]}@nowhere.dev", "password": "AnyPassword123!"},
    )
    assert resp.status_code == 401
    assert "invalid" in error_message(resp).lower() or "credentials" in error_message(resp).lower()


def test_case_c_disabled_account_returns_403(client: TestClient, hardened_tenant_and_user):
    """Case C: Deactivated/disabled user accounts are blocked with 403."""
    session_factory = _get_session_factory(get_db_url())
    with session_factory() as session:
        user = session.query(UserModel).filter(UserModel.email == hardened_tenant_and_user["email"]).first()
        user.active = False
        user.status = UserStatus.DISABLED.value
        session.commit()

    resp = client.post(
        "/api/v2/auth/login",
        json={"email": hardened_tenant_and_user["email"], "password": hardened_tenant_and_user["password"]},
    )
    assert resp.status_code == 403
    assert "access denied" in error_message(resp).lower() or "authorization" in error_message(resp).lower()


def test_case_d_account_lockout_after_five_failed_attempts(client: TestClient, hardened_tenant_and_user):
    """Case D: Account locks out for 15 minutes after 5 consecutive failed login attempts."""
    for attempt in range(1, 5):
        resp = client.post(
            "/api/v2/auth/login",
            json={"email": hardened_tenant_and_user["email"], "password": f"wrong-pass-{attempt}"},
        )
        assert resp.status_code == 401

    # 5th attempt triggers lockout
    resp_5 = client.post(
        "/api/v2/auth/login",
        json={"email": hardened_tenant_and_user["email"], "password": "wrong-pass-5"},
    )
    assert resp_5.status_code == 401

    # 6th attempt (even with correct password) returns 423 Locked
    locked_resp = client.post(
        "/api/v2/auth/login",
        json={"email": hardened_tenant_and_user["email"], "password": hardened_tenant_and_user["password"]},
    )
    assert locked_resp.status_code == 423
    assert "locked" in error_message(locked_resp).lower()


def test_case_e_successful_login_resets_failed_counter(client: TestClient, hardened_tenant_and_user):
    """Case E: A successful login clears the failed attempt counter."""
    # 2 failed attempts
    client.post("/api/v2/auth/login", json={"email": hardened_tenant_and_user["email"], "password": "bad1"})
    client.post("/api/v2/auth/login", json={"email": hardened_tenant_and_user["email"], "password": "bad2"})

    # Successful login
    succ_resp = client.post(
        "/api/v2/auth/login",
        json={"email": hardened_tenant_and_user["email"], "password": hardened_tenant_and_user["password"]},
    )
    assert succ_resp.status_code == 200

    session_factory = _get_session_factory(get_db_url())
    with session_factory() as session:
        user = session.query(UserModel).filter(UserModel.email == hardened_tenant_and_user["email"]).first()
        assert user.failed_login_attempts == 0
        assert user.locked_until is None


def test_case_f_session_tracking_in_database(client: TestClient, hardened_tenant_and_user):
    """Case F: Logging in creates a database user_sessions row with client attributes."""
    resp = client.post(
        "/api/v2/auth/login",
        json={
            "email": hardened_tenant_and_user["email"],
            "password": hardened_tenant_and_user["password"],
            "device_id": "iphone-15-pro-secure",
        },
        headers={"User-Agent": "THALIMobile/1.0.0 iOS"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "refresh_token" in data
    assert "access_token" in data

    session_factory = _get_session_factory(get_db_url())
    with session_factory() as session:
        sess = session.query(UserSessionModel).filter(
            UserSessionModel.device_id == "iphone-15-pro-secure"
        ).first()
        assert sess is not None
        assert sess.is_active is True
        assert "THALIMobile" in (sess.user_agent or "")


def test_case_g_refresh_token_rotation_success(client: TestClient, hardened_tenant_and_user):
    """Case G: Exchanging a refresh token rotates both access and refresh tokens and marks old token used."""
    login_resp = client.post(
        "/api/v2/auth/login",
        json={"email": hardened_tenant_and_user["email"], "password": hardened_tenant_and_user["password"]},
    )
    orig_access = login_resp.json()["access_token"]
    orig_refresh = login_resp.json()["refresh_token"]

    # Refresh
    refresh_resp = client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": orig_refresh},
    )
    assert refresh_resp.status_code == 200
    ref_data = refresh_resp.json()
    new_access = ref_data["access_token"]
    new_refresh = ref_data["refresh_token"]

    assert new_access != orig_access
    assert new_refresh is not None and new_refresh != orig_refresh

    # Verify in DB: original refresh token is marked used
    session_factory = _get_session_factory(get_db_url())
    with session_factory() as session:
        orig_hash = TokenService.hash_secret(orig_refresh)
        orig_rec = session.query(RefreshTokenFamilyModel).filter(
            RefreshTokenFamilyModel.token_hash == orig_hash
        ).first()
        assert orig_rec is not None
        assert orig_rec.is_used is True

        new_hash = TokenService.hash_secret(new_refresh)
        new_rec = session.query(RefreshTokenFamilyModel).filter(
            RefreshTokenFamilyModel.token_hash == new_hash
        ).first()
        assert new_rec is not None
        assert new_rec.is_used is False
        assert new_rec.sequence_number == 2


def test_case_h_refresh_token_reuse_detection_and_revocation(client: TestClient, hardened_tenant_and_user):
    """Case H (CRITICAL): Presenting an already-used refresh token invalidates the entire session family."""
    # 1. Login
    login_resp = client.post(
        "/api/v2/auth/login",
        json={"email": hardened_tenant_and_user["email"], "password": hardened_tenant_and_user["password"]},
    )
    tok1 = login_resp.json()["refresh_token"]

    # 2. Legitimate refresh with tok1 -> yields tok2
    ref1_resp = client.post("/api/v2/auth/refresh", json={"refresh_token": tok1})
    assert ref1_resp.status_code == 200
    tok2 = ref1_resp.json()["refresh_token"]

    # 3. Adversary replays tok1 (already used)
    replay_resp = client.post("/api/v2/auth/refresh", json={"refresh_token": tok1})
    assert replay_resp.status_code == 401
    assert "authentication" in error_message(replay_resp).lower() or "required" in error_message(replay_resp).lower()

    # 4. Invariant: tok2 (which was legitimately issued) is NOW ALSO REVOKED because the family was breached!
    ref2_resp = client.post("/api/v2/auth/refresh", json={"refresh_token": tok2})
    assert ref2_resp.status_code == 401

    # Verify session is marked inactive in database
    session_factory = _get_session_factory(get_db_url())
    with session_factory() as session:
        tok1_hash = TokenService.hash_secret(tok1)
        rec = session.query(RefreshTokenFamilyModel).filter(RefreshTokenFamilyModel.token_hash == tok1_hash).first()
        user_sess = session.query(UserSessionModel).filter(UserSessionModel.id == rec.session_id).first()
        assert user_sess.is_active is False
        assert user_sess.revoked_at is not None


def test_case_j_stateful_logout_invalidates_session(client: TestClient, hardened_tenant_and_user):
    """Case J: Logout invalidates the server-side session and prevents further refresh."""
    login_resp = client.post(
        "/api/v2/auth/login",
        json={"email": hardened_tenant_and_user["email"], "password": hardened_tenant_and_user["password"]},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Logout
    logout_resp = client.post("/api/v2/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 204

    # Subsequent refresh attempt with that token fails
    ref_resp = client.post("/api/v2/auth/refresh", json={"refresh_token": refresh_token})
    assert ref_resp.status_code == 401


def test_case_k_single_use_password_reset_replay_fails(client: TestClient, hardened_tenant_and_user):
    """Case K: Password reset token cannot be used twice."""
    # 1. Request reset
    forgot_resp = client.post(
        "/api/v2/auth/forgot-password",
        json={"email": hardened_tenant_and_user["email"]},
    )
    assert forgot_resp.status_code == 200
    reset_token = forgot_resp.json()["reset_token"]
    assert reset_token is not None

    # 2. First consumption succeeds
    first_reset = client.post(
        "/api/v2/auth/reset-password",
        json={"token": reset_token, "new_password": "NewSafePassword456!"},
    )
    assert first_reset.status_code == 200

    # 3. Replay of same token fails with 400
    replay_reset = client.post(
        "/api/v2/auth/reset-password",
        json={"token": reset_token, "new_password": "AnotherPassword789!"},
    )
    assert replay_reset.status_code == 400
    assert "invalid" in error_message(replay_reset).lower() or "request" in error_message(replay_reset).lower()


def test_case_l_password_reset_revokes_active_sessions(client: TestClient, hardened_tenant_and_user):
    """Case L: Completing a password reset revokes all active sessions for the user."""
    # Log in to create an active session
    login_resp = client.post(
        "/api/v2/auth/login",
        json={"email": hardened_tenant_and_user["email"], "password": hardened_tenant_and_user["password"]},
    )
    active_refresh = login_resp.json()["refresh_token"]

    # Trigger and complete password reset
    forgot_resp = client.post("/api/v2/auth/forgot-password", json={"email": hardened_tenant_and_user["email"]})
    reset_token = forgot_resp.json()["reset_token"]
    client.post("/api/v2/auth/reset-password", json={"token": reset_token, "new_password": "BrandNewPassword123!"})

    # The existing session's refresh token must now be rejected
    ref_resp = client.post("/api/v2/auth/refresh", json={"refresh_token": active_refresh})
    assert ref_resp.status_code == 401


def test_case_m_tampered_jwt_signature_rejected(client: TestClient, hardened_tenant_and_user):
    """Case M: Modifying any claim in an issued JWT causes cryptographic signature verification to fail."""
    login_resp = client.post(
        "/api/v2/auth/login",
        json={"email": hardened_tenant_and_user["email"], "password": hardened_tenant_and_user["password"]},
    )
    token = login_resp.json()["access_token"]
    parts = token.split(".")
    # Tamper with payload part
    tampered_token = f"{parts[0]}.eyJuYW1lIjoiSGFja2VyIn0.{parts[2]}"

    resp = client.get("/api/v2/auth/verify", headers=bearer(tampered_token))
    assert resp.status_code == 401


def test_case_n_alg_none_attack_rejected(client: TestClient):
    """Case N: An unsigned token with alg 'none' is rejected."""
    unsigned_token = pyjwt.encode({"sub": str(uuid4()), "role": "doctor"}, key="", algorithm="none")
    resp = client.get("/api/v2/auth/verify", headers=bearer(unsigned_token))
    assert resp.status_code == 401


def test_case_o_doctor_signup_without_invite_code_is_pending_verification(client: TestClient):
    """Case O: Doctor self-signup without invite code receives PENDING_VERIFICATION status."""
    doc_email = f"doc-{uuid4().hex[:6]}@clinic.thali.dev"
    resp = client.post(
        "/api/v2/auth/signup",
        json={
            "email": doc_email,
            "password": "DocSecurePassword123!",
            "role": "doctor",
            "name": "Dr. Unverified Clinician",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "doctor"
    assert data["user_status"] == UserStatus.PENDING_VERIFICATION.value


def test_case_p_doctor_signup_with_verified_invite_code_is_active(client: TestClient):
    """Case P: Doctor signup with approved facility invite code activates immediately."""
    doc_email = f"doc-active-{uuid4().hex[:6]}@clinic.thali.dev"
    resp = client.post(
        "/api/v2/auth/signup",
        json={
            "email": doc_email,
            "password": "DocSecurePassword123!",
            "role": "doctor",
            "invite_code": "CLINIC-VERIFIED-2026",
            "name": "Dr. Verified Clinician",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "doctor"
    assert data["user_status"] == UserStatus.ACTIVE.value


def test_case_q_patient_signup_auto_provisions_uhid_and_mapping(client: TestClient):
    """Case Q: Patient signup auto-provisions patient aggregate and 1:1 identity mapping."""
    patient_email = f"pat-{uuid4().hex[:6]}@patient.thali.dev"
    resp = client.post(
        "/api/v2/auth/signup",
        json={
            "email": patient_email,
            "password": "PatientPassword123!",
            "name": "Devi Prasad",
            "role": "patient",
        },
    )
    assert resp.status_code == 201

    session_factory = _get_session_factory(get_db_url())
    with session_factory() as session:
        user = session.query(UserModel).filter(UserModel.email == patient_email).first()
        mapping = session.query(IdentityPatientMappingModel).filter(
            IdentityPatientMappingModel.user_id == user.id
        ).first()
        assert mapping is not None
        assert mapping.active is True

        patient = session.query(PatientModel).filter(PatientModel.id == mapping.patient_id).first()
        assert patient is not None
        assert patient.uh_id.startswith("UHID-")
        assert patient.name == "Devi Prasad"


def test_case_r_caregiver_signup_does_not_auto_grant_patient_access(client: TestClient):
    """Case R: Caregiver registration does not auto-link patient profile."""
    cg_email = f"caregiver-{uuid4().hex[:6]}@cg.thali.dev"
    resp = client.post(
        "/api/v2/auth/signup",
        json={
            "email": cg_email,
            "password": "CaregiverPassword123!",
            "role": "caregiver",
        },
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]

    # Calling /api/v2/auth/context reflects RELATIONSHIP_PENDING
    ctx_resp = client.get("/api/v2/auth/context", headers=bearer(token))
    assert ctx_resp.status_code == 200
    ctx_data = ctx_resp.json()
    assert ctx_data["onboarding_state"] == "RELATIONSHIP_PENDING"
    assert len(ctx_data["available_patient_contexts"]) == 0


def test_case_s_change_password_revokes_sessions(client: TestClient, hardened_tenant_and_user):
    """Case S: Authenticated change-password updates password and terminates previous sessions."""
    # Login to get access token and refresh token
    login_resp = client.post(
        "/api/v2/auth/login",
        json={"email": hardened_tenant_and_user["email"], "password": hardened_tenant_and_user["password"]},
    )
    access_token = login_resp.json()["access_token"]
    refresh_token = login_resp.json()["refresh_token"]

    # Change password
    chg_resp = client.post(
        "/api/v2/auth/change-password",
        headers=bearer(access_token),
        json={
            "current_password": hardened_tenant_and_user["password"],
            "new_password": "UpgradedSecurePassword789!",
        },
    )
    assert chg_resp.status_code == 200

    # Old refresh token is revoked
    ref_resp = client.post("/api/v2/auth/refresh", json={"refresh_token": refresh_token})
    assert ref_resp.status_code == 401

    # Login with new password succeeds
    new_login = client.post(
        "/api/v2/auth/login",
        json={"email": hardened_tenant_and_user["email"], "password": "UpgradedSecurePassword789!"},
    )
    assert new_login.status_code == 200


def test_case_t_key_rotation_with_kid():
    """Case T: TokenService accepts key rotation dictionary and verifies tokens by kid."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    # Generate old key
    old_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    old_priv_pem = old_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    old_pub_pem = old_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    # Generate current key
    curr_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    curr_priv_pem = curr_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    curr_pub_pem = curr_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    # TokenService with active curr_key and rotated old_key in rotation dictionary
    token_service = TokenService(
        private_key_pem=curr_priv_pem,
        public_key_pem=curr_pub_pem,
        kid="key-2026-v2",
        rotation_public_keys={"key-2025-v1": old_pub_pem, "key-2026-v2": curr_pub_pem},
    )

    # Issue token with old service
    old_service = TokenService(
        private_key_pem=old_priv_pem,
        public_key_pem=old_pub_pem,
        kid="key-2025-v1",
    )
    old_token = old_service.issue_access_token(user_id="user-1", tenant_id="tenant-1", role="doctor")

    # Verify old token using new service (should succeed via rotation dict lookup)
    claims = token_service.verify_token(old_token)
    assert claims["sub"] == "user-1"
    assert claims["role"] == "doctor"
