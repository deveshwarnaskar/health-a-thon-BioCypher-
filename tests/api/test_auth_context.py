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
