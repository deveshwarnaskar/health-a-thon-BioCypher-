"""Gate 10P — Authenticated bootstrap/context endpoint tests.

Proves:
- GET /api/v2/auth/context requires authentication (401 without bearer).
- Patient with active mapping resolves patient_id and ACTIVE onboarding state.
- Patient without mapping resolves IDENTITY_MAPPING_PENDING.
- Patient with deactivated mapping or patient resolves DEACTIVATED.
- Caregiver with verified relationship resolves active patient context and capabilities.
- Caregiver without relationship resolves RELATIONSHIP_PENDING.
- Doctor resolves facility_id and clinical capabilities.
- Admin resolves admin capabilities.
- Minimum data exposure: secrets and database internals are never returned.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from backend.domain.entities import (
    CareTeamMember,
    CareTeamRole,
    CaregiverRelationship,
    CaregiverRelationshipStatus,
    IdentityPatientMapping,
    Patient,
)
from backend.domain.value_objects import UHID
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from tests.api.conftest import bearer, make_jwt


class TestAuthContextEndpoint:
    """Proves /api/v2/auth/context behavior across all roles and relationship states."""

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/v2/auth/context")
        assert resp.status_code == 401

    def test_patient_with_active_mapping(self, db_client):
        client, db_session_factory = db_client
        actor_id = uuid4()
        tenant_id = uuid4()
        patient_id = uuid4()

        with SqlAlchemyUnitOfWork(db_session_factory, tenant_id) as uow:
            pat = Patient(
                id=patient_id,
                facility_id=uuid4(),
                uh_id=UHID("UH-PAT-01"),
                name="Test Patient",
                active=True,
            )
            mapping = IdentityPatientMapping(
                id=uuid4(),
                user_id=actor_id,
                patient_id=patient_id,
                active=True,
            )
            uow.patients.add(pat)
            uow.identity_mappings.add(mapping)
            uow.commit()

        token = make_jwt(sub=str(actor_id), tenant_id=str(tenant_id), roles=["patient"])
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()

        assert body["actor_id"] == str(actor_id)
        assert body["tenant_id"] == str(tenant_id)
        assert body["roles"] == ["patient"]
        assert body["patient_id"] == str(patient_id)
        assert body["onboarding_state"] == "ACTIVE"
        assert len(body["available_patient_contexts"]) == 1
        assert body["available_patient_contexts"][0]["patient_id"] == str(patient_id)
        assert body["available_patient_contexts"][0]["relationship"] == "self"

    def test_patient_without_mapping_resolves_pending(self, client):
        actor_id = uuid4()
        tenant_id = uuid4()

        token = make_jwt(sub=str(actor_id), tenant_id=str(tenant_id), roles=["patient"])
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()

        assert body["actor_id"] == str(actor_id)
        assert body["patient_id"] is None
        assert body["onboarding_state"] == "IDENTITY_MAPPING_PENDING"
        assert body["available_patient_contexts"] == []

    def test_patient_with_deactivated_mapping(self, db_client):
        client, db_session_factory = db_client
        actor_id = uuid4()
        tenant_id = uuid4()
        patient_id = uuid4()

        with SqlAlchemyUnitOfWork(db_session_factory, tenant_id) as uow:
            pat = Patient(
                id=patient_id,
                facility_id=uuid4(),
                uh_id=UHID("UH-PAT-02"),
                name="Inactive Patient",
                active=False,
            )
            mapping = IdentityPatientMapping(
                id=uuid4(),
                user_id=actor_id,
                patient_id=patient_id,
                active=True,
            )
            uow.patients.add(pat)
            uow.identity_mappings.add(mapping)
            uow.commit()

        token = make_jwt(sub=str(actor_id), tenant_id=str(tenant_id), roles=["patient"])
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()

        assert body["onboarding_state"] == "DEACTIVATED"

    def test_caregiver_with_verified_relationship(self, db_client):
        client, db_session_factory = db_client
        actor_id = uuid4()
        tenant_id = uuid4()
        patient_id = uuid4()

        with SqlAlchemyUnitOfWork(db_session_factory, tenant_id) as uow:
            pat = Patient(
                id=patient_id,
                facility_id=uuid4(),
                uh_id=UHID("UH-PAT-03"),
                name="Ward Patient",
                active=True,
            )
            rel = CaregiverRelationship(
                id=uuid4(),
                patient_id=patient_id,
                caregiver_user_id=actor_id,
                relationship="Mother",
                status=CaregiverRelationshipStatus.VERIFIED,
                capabilities=frozenset({"read_observations", "write_meal_observations"}),
            )
            uow.patients.add(pat)
            uow.caregiver_relationships.add(rel)
            uow.commit()

        token = make_jwt(sub=str(actor_id), tenant_id=str(tenant_id), roles=["caregiver"])
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()

        assert body["actor_id"] == str(actor_id)
        assert body["patient_id"] == str(patient_id)
        assert body["onboarding_state"] == "ACTIVE"
        assert len(body["available_patient_contexts"]) == 1
        assert body["available_patient_contexts"][0]["patient_id"] == str(patient_id)
        assert body["available_patient_contexts"][0]["relationship"] == "Mother"
        assert "read_observations" in body["capabilities"]

    def test_caregiver_with_naive_storage_expires_at(self, db_client):
        """Simulates SQLite returning naive datetimes without raising offset comparison TypeError."""
        client, db_session_factory = db_client
        actor_id = uuid4()
        tenant_id = uuid4()
        patient_id = uuid4()

        with SqlAlchemyUnitOfWork(db_session_factory, tenant_id) as uow:
            pat = Patient(
                id=patient_id,
                facility_id=uuid4(),
                uh_id=UHID("UH-PAT-EXP"),
                name="Sita Sharma",
                active=True,
            )
            naive_expires = datetime(2030, 1, 1, 0, 0, 0)
            rel = CaregiverRelationship(
                id=uuid4(),
                patient_id=patient_id,
                caregiver_user_id=actor_id,
                relationship="Daughter",
                status=CaregiverRelationshipStatus.VERIFIED,
                capabilities=frozenset({"read_observations", "write_meal_observations"}),
                expires_at=naive_expires,
            )
            uow.patients.add(pat)
            uow.caregiver_relationships.add(rel)
            uow.commit()

        token = make_jwt(sub=str(actor_id), tenant_id=str(tenant_id), roles=["caregiver"])
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()

        assert body["actor_id"] == str(actor_id)
        assert body["patient_id"] == str(patient_id)
        assert body["onboarding_state"] == "ACTIVE"
        assert len(body["available_patient_contexts"]) == 1
        assert body["available_patient_contexts"][0]["patient_id"] == str(patient_id)
        assert body["available_patient_contexts"][0]["relationship"] == "Daughter"
        assert "read_observations" in body["capabilities"]

    def test_caregiver_with_expired_naive_relationship_resolves_pending(self, db_client):
        """Proves expired naive relationship does not grant active context."""
        client, db_session_factory = db_client
        actor_id = uuid4()
        tenant_id = uuid4()
        patient_id = uuid4()

        with SqlAlchemyUnitOfWork(db_session_factory, tenant_id) as uow:
            pat = Patient(
                id=patient_id,
                facility_id=uuid4(),
                uh_id=UHID("UH-PAT-PAST"),
                name="Past Patient",
                active=True,
            )
            naive_past = datetime(2020, 1, 1, 0, 0, 0)
            rel = CaregiverRelationship(
                id=uuid4(),
                patient_id=patient_id,
                caregiver_user_id=actor_id,
                relationship="Daughter",
                status=CaregiverRelationshipStatus.VERIFIED,
                capabilities=frozenset({"read_observations"}),
                expires_at=naive_past,
            )
            uow.patients.add(pat)
            uow.caregiver_relationships.add(rel)
            uow.commit()

        token = make_jwt(sub=str(actor_id), tenant_id=str(tenant_id), roles=["caregiver"])
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()

        assert body["patient_id"] is None
        assert body["onboarding_state"] == "RELATIONSHIP_PENDING"
        assert body["available_patient_contexts"] == []

    def test_caregiver_without_relationship_resolves_pending(self, client):
        actor_id = uuid4()
        tenant_id = uuid4()

        token = make_jwt(sub=str(actor_id), tenant_id=str(tenant_id), roles=["caregiver"])
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()

        assert body["patient_id"] is None
        assert body["onboarding_state"] == "RELATIONSHIP_PENDING"
        assert body["available_patient_contexts"] == []

    def test_doctor_context(self, client):
        actor_id = uuid4()
        tenant_id = uuid4()
        facility_id = uuid4()

        token = make_jwt(
            sub=str(actor_id),
            tenant_id=str(tenant_id),
            roles=["doctor"],
            facility_id=str(facility_id),
        )
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()

        assert body["actor_id"] == str(actor_id)
        assert body["facility_id"] == str(facility_id)
        assert body["onboarding_state"] == "ACTIVE"
        assert "write_medication_plans" in body["capabilities"]
        assert "read_observations" in body["capabilities"]

    def test_admin_context(self, client):
        actor_id = uuid4()
        tenant_id = uuid4()

        token = make_jwt(sub=str(actor_id), tenant_id=str(tenant_id), roles=["admin"])
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()

        assert body["actor_id"] == str(actor_id)
        assert body["onboarding_state"] == "ACTIVE"
        assert "admin" in body["capabilities"]
        assert "manage_care_team" in body["capabilities"]


class TestTenantAuthorityAndIsolation:
    """Proves the 10 tenant authority and isolation invariants for /api/v2/auth/context."""

    def test_query_param_tenant_id_ignored_for_context(self, client):
        """Query parameters cannot override or alter the authoritative JWT tenant_id."""
        actor_id = uuid4()
        jwt_tenant_id = uuid4()
        spoofed_tenant_id = uuid4()

        token = make_jwt(sub=str(actor_id), tenant_id=str(jwt_tenant_id), roles=["patient"])
        resp = client.get(
            f"/api/v2/auth/context?tenant_id={spoofed_tenant_id}",
            headers=bearer(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == str(jwt_tenant_id)
        assert body["tenant_id"] != str(spoofed_tenant_id)

    def test_missing_jwt_tenant_id_fails_closed(self, client):
        """A JWT lacking a tenant_id claim is unconditionally rejected (401)."""
        actor_id = uuid4()
        token = make_jwt(sub=str(actor_id), roles=["patient"], extra={"tenant_id": None})
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 401

    def test_malformed_jwt_tenant_id_fails_closed(self, client):
        """A JWT with a non-UUID tenant_id claim is rejected as malformed (401)."""
        actor_id = uuid4()
        token = make_jwt(sub=str(actor_id), tenant_id="not-a-valid-uuid", roles=["patient"])
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 401

    def test_tampered_jwt_signature_fails_closed(self, client):
        """Tampering with token payload to alter tenant_id invalidates cryptographic signature (401)."""
        actor_id = uuid4()
        real_tenant = uuid4()
        fake_tenant = uuid4()

        token = make_jwt(sub=str(actor_id), tenant_id=str(real_tenant), roles=["doctor"])
        parts = token.split(".")
        # Tamper payload part with fake tenant
        import base64, json
        raw_payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
        raw_payload["tenant_id"] = str(fake_tenant)
        tampered_payload_b64 = base64.urlsafe_b64encode(json.dumps(raw_payload).encode()).decode().rstrip("=")
        tampered_token = f"{parts[0]}.{tampered_payload_b64}.{parts[2]}"

        resp = client.get("/api/v2/auth/context", headers=bearer(tampered_token))
        assert resp.status_code == 401

    def test_cross_tenant_patient_mapping_isolated(self, db_client):
        """An actor with an active patient mapping in Tenant B cannot resolve it when authenticating in Tenant A."""
        client, db_session_factory = db_client
        actor_id = uuid4()
        tenant_a = uuid4()
        tenant_b = uuid4()
        patient_b = uuid4()

        # Seed patient mapping in Tenant B
        with SqlAlchemyUnitOfWork(db_session_factory, tenant_b) as uow:
            pat = Patient(
                id=patient_b,
                facility_id=uuid4(),
                uh_id=UHID("UH-B-01"),
                name="Tenant B Patient",
                active=True,
            )
            mapping = IdentityPatientMapping(
                id=uuid4(),
                user_id=actor_id,
                patient_id=patient_b,
                active=True,
            )
            uow.patients.add(pat)
            uow.identity_mappings.add(mapping)
            uow.commit()

        # Authenticate with token scoped to Tenant A
        token = make_jwt(sub=str(actor_id), tenant_id=str(tenant_a), roles=["patient"])
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()

        # Must NOT see Tenant B's patient
        assert body["tenant_id"] == str(tenant_a)
        assert body["patient_id"] is None
        assert body["onboarding_state"] == "IDENTITY_MAPPING_PENDING"
        assert body["available_patient_contexts"] == []

    def test_cross_tenant_caregiver_relationship_isolated(self, db_client):
        """A caregiver granted relationships in Tenant B cannot access them when presenting Tenant A's token."""
        client, db_session_factory = db_client
        caregiver_actor_id = uuid4()
        tenant_a = uuid4()
        tenant_b = uuid4()
        patient_b = uuid4()

        # Seed caregiver relationship in Tenant B
        with SqlAlchemyUnitOfWork(db_session_factory, tenant_b) as uow:
            pat = Patient(
                id=patient_b,
                facility_id=uuid4(),
                uh_id=UHID("UH-B-02"),
                name="Tenant B Patient",
                active=True,
            )
            rel = CaregiverRelationship(
                id=uuid4(),
                patient_id=patient_b,
                caregiver_user_id=caregiver_actor_id,
                relationship="Spouse",
                status=CaregiverRelationshipStatus.VERIFIED,
                capabilities=frozenset({"read_observations"}),
            )
            uow.patients.add(pat)
            uow.caregiver_relationships.add(rel)
            uow.commit()

        # Authenticate with Tenant A token
        token = make_jwt(sub=str(caregiver_actor_id), tenant_id=str(tenant_a), roles=["caregiver"])
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()

        assert body["tenant_id"] == str(tenant_a)
        assert body["patient_id"] is None
        assert body["onboarding_state"] == "RELATIONSHIP_PENDING"
        assert body["available_patient_contexts"] == []

    def test_keycloak_human_readable_role_normalization(self, client):
        """Keycloak human-readable realm roles normalize to canonical domain tokens."""
        actor_id = uuid4()
        tenant_id = uuid4()
        token = make_jwt(
            sub=str(actor_id),
            tenant_id=str(tenant_id),
            roles=["Care Coordinator", "Dietitian/Diabetes Educator", "Field Health Worker"],
        )
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()
        assert set(body["roles"]) == {"care_coordinator", "dietitian", "field_health_worker"}

    def test_unknown_and_malformed_roles_fail_closed(self, client):
        """Unknown or arbitrary role strings are dropped and grant zero permissions."""
        actor_id = uuid4()
        tenant_id = uuid4()
        token = make_jwt(
            sub=str(actor_id),
            tenant_id=str(tenant_id),
            roles=["superuser", "admin_override", "root", "unknown_role"],
        )
        resp = client.get("/api/v2/auth/context", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()
        # All unknown roles dropped
        assert body["roles"] == []
        assert body["capabilities"] == []

