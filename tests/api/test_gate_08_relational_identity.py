"""Gate 08 — relational identity + clinical authorization (Phase 14 matrix).

Proves the full authorization chain:

- Identity→patient mapping governs patient self-access.
- Caregiver proxy access requires a VERIFIED, non-expired, non-revoked
  relationship with explicit capability grants.
- Facility scoping is driven by CareTeamMember membership (authoritative),
  not by JWT claims alone.
- CareTeamMember-less clinicians are denied.
- Caregiver capability allow-list is enforced.
- Administrator-only identity mapping routes deny all non-admin callers.
- Duplicate active mappings/relationships return 409 Conflict.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from tests.api.conftest import (
    bearer,
    make_jwt,
    seed_caregiver_relationship,
    seed_facility,
    seed_glucose,
    seed_identity_mapping,
    seed_member,
    seed_org,
    seed_patient,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _uid() -> str:
    return str(uuid4())


def _now_minus(seconds: int) -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# ─────────────────────────────────────────────────────────────────────────────
# Identity → Patient mapping
# ─────────────────────────────────────────────────────────────────────────────

class TestIdentityMappingAdmin:

    def test_admin_creates_mapping_201(self, db_client):
        c, sf = db_client
        tid, fid, actor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "idmap-org")
        seed_facility(sf, tid, fid, "Facility A")
        seed_patient(sf, tid, patient_id, facility_id=fid, name="Mapped")
        seed_member(sf, tid, user_id=actor_id, role="care_coordinator", facility_id=fid)

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["admin"])
        resp = c.post(
            "/api/v2/admin/identity-mappings",
            json={"user_id": _uid(), "patient_id": str(patient_id)},
            headers=bearer(token),
        )
        # Admin requires MANAGE_IDENTITY_MAPPINGS; care_coordinator does not
        # hold it. Only 'admin' role does.
        assert resp.status_code == 201
        body = resp.json()
        assert body["active"] is True
        assert body["patient_id"] == str(patient_id)

    def test_non_admin_denied_403(self, db_client):
        c, sf = db_client
        tid, patient_id = uuid4(), uuid4()
        seed_org(sf, tid, "idmap-non")
        seed_patient(sf, tid, patient_id)

        token = make_jwt(sub=_uid(), tenant_id=str(tid), roles=["doctor"])
        resp = c.post(
            "/api/v2/admin/identity-mappings",
            json={"user_id": _uid(), "patient_id": str(patient_id)},
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_deactivate_mapping_revokes_patient_self_access(self, db_client):
        c, sf = db_client
        tid, fid, user_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "idmap-deact")
        seed_facility(sf, tid, fid, "Facility B")
        seed_patient(sf, tid, patient_id, facility_id=fid, name="DeactMe")
        seed_identity_mapping(sf, tid, user_id=user_id, patient_id=patient_id, active=True)
        seed_glucose(sf, tid, patient_id, value=120)

        # First confirm self-access works
        token = make_jwt(sub=str(user_id), tenant_id=str(tid), roles=["patient"])
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 200

        # Deactivate via admin
        seed_member(sf, tid, user_id=user_id, role="care_coordinator", facility_id=fid)
        admin_token = make_jwt(sub=str(user_id), tenant_id=str(tid), roles=["admin"])
        list_resp = c.get("/api/v2/admin/identity-mappings", headers=bearer(admin_token))
        mapping_id = list_resp.json()[0]["mapping_id"]
        deact_resp = c.post(
            f"/api/v2/admin/identity-mappings/{mapping_id}/deactivate",
            headers=bearer(admin_token),
        )
        assert deact_resp.status_code == 200
        assert deact_resp.json()["active"] is False

        # Patient self-access now denied
        resp2 = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp2.status_code == 403


class TestPatientSelfAccess:

    def test_patient_self_access_via_mapping(self, db_client):
        c, sf = db_client
        tid, fid, user_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "self-org")
        seed_facility(sf, tid, fid, "SelfFacility")
        seed_patient(sf, tid, patient_id, facility_id=fid, name="SelfP")
        seed_identity_mapping(sf, tid, user_id=user_id, patient_id=patient_id, active=True)
        seed_glucose(sf, tid, patient_id, value=90)

        token = make_jwt(sub=str(user_id), tenant_id=str(tid), roles=["patient"])
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(i.get("value_mg_dl") == 90 for i in items if i.get("kind") == "glucose")

    def test_patient_denied_when_no_mapping(self, client):
        token = make_jwt(sub=_uid(), tenant_id=_uid(), roles=["patient"])
        resp = client.get(
            f"/api/v2/clinical/observations?patient_id={_uid()}",
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_patient_denied_for_cross_patient_id(self, db_client):
        c, sf = db_client
        tid, fid, user_id = uuid4(), uuid4(), uuid4()
        pid_a, pid_b = uuid4(), uuid4()
        seed_org(sf, tid, "cross-org")
        seed_facility(sf, tid, fid, "CrossFac")
        seed_patient(sf, tid, pid_a, facility_id=fid)
        seed_patient(sf, tid, pid_b, facility_id=fid)
        seed_identity_mapping(sf, tid, user_id=user_id, patient_id=pid_a, active=True)

        token = make_jwt(sub=str(user_id), tenant_id=str(tid), roles=["patient"])
        resp = c.get(f"/api/v2/clinical/observations?patient_id={pid_b}", headers=bearer(token))
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Caregiver proxy access
# ─────────────────────────────────────────────────────────────────────────────

class TestCaregiverProxyAccess:

    def test_caregiver_can_read_observations_when_verified(self, db_client):
        c, sf = db_client
        tid, fid, actor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-org")
        seed_facility(sf, tid, fid, "CGFac")
        seed_patient(sf, tid, patient_id, facility_id=fid, name="CGPatient")
        seed_caregiver_relationship(
            sf, tid, patient_id=patient_id,
            caregiver_user_id=actor_id,
            status="verified",
            capabilities=["read_glucose", "read_meal"],
        )
        seed_glucose(sf, tid, patient_id, value=150)

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["caregiver"])
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(i.get("value_mg_dl") == 150 for i in items if i.get("kind") == "glucose")

    def test_caregiver_denied_when_relationship_pending(self, db_client):
        c, sf = db_client
        tid, fid, actor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-pend")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_caregiver_relationship(
            sf, tid, patient_id=patient_id,
            caregiver_user_id=actor_id,
            status="pending",
            capabilities=["read_glucose", "read_meal"],
        )

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["caregiver"])
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 403

    def test_caregiver_denied_without_required_capability(self, db_client):
        c, sf = db_client
        tid, fid, actor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-nocap")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_caregiver_relationship(
            sf, tid, patient_id=patient_id,
            caregiver_user_id=actor_id,
            status="verified",
            capabilities=[],  # no capabilities
        )

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["caregiver"])
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 403

    def test_caregiver_denied_for_patient_outside_relationship(self, db_client):
        c, sf = db_client
        tid, fid, actor_id = uuid4(), uuid4(), uuid4()
        pid_a, pid_b = uuid4(), uuid4()
        seed_org(sf, tid, "cg-out")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, pid_a, facility_id=fid)
        seed_patient(sf, tid, pid_b, facility_id=fid)
        seed_caregiver_relationship(
            sf, tid, patient_id=pid_a,
            caregiver_user_id=actor_id,
            status="verified",
            capabilities=["read_glucose"],
        )

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["caregiver"])
        resp = c.get(f"/api/v2/clinical/observations?patient_id={pid_b}", headers=bearer(token))
        assert resp.status_code == 403

    def test_caregiver_denied_for_medication_plans_even_with_capabilities(self, db_client):
        c, sf = db_client
        tid, fid, actor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-med")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_caregiver_relationship(
            sf, tid, patient_id=patient_id,
            caregiver_user_id=actor_id,
            status="verified",
            capabilities=["read_glucose", "read_meal"],
        )

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["caregiver"])
        resp = c.post(
            "/api/v2/clinical/medication-plans",
            json={"patient_id": str(patient_id), "medication": "Metformin"},
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_revoke_removes_caregiver_access(self, db_client):
        c, sf = db_client
        tid, fid, actor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-rev")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_caregiver_relationship(
            sf, tid, patient_id=patient_id,
            caregiver_user_id=actor_id,
            status="revoked",
            capabilities=["read_glucose"],
        )

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["caregiver"])
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# 409 Conflict for duplicates
# ─────────────────────────────────────────────────────────────────────────────

class TestDuplicateConflict:

    def test_duplicate_identity_mapping_returns_409(self, db_client):
        c, sf = db_client
        tid, patient_id, user_id = uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "dup-idmap")
        seed_patient(sf, tid, patient_id)

        token = make_jwt(sub=_uid(), tenant_id=str(tid), roles=["admin"])
        c.post(
            "/api/v2/admin/identity-mappings",
            json={"user_id": str(user_id), "patient_id": str(patient_id)},
            headers=bearer(token),
        )
        resp2 = c.post(
            "/api/v2/admin/identity-mappings",
            json={"user_id": str(user_id), "patient_id": str(patient_id)},
            headers=bearer(token),
        )
        assert resp2.status_code == 409

    def test_duplicate_caregiver_relationship_returns_409(self, db_client):
        c, sf = db_client
        tid, fid, coord_id, cg_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "dup-cg")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_member(sf, tid, user_id=coord_id, role="care_coordinator", facility_id=fid)

        coord_token = make_jwt(sub=str(coord_id), tenant_id=str(tid), roles=["care_coordinator"], facility_id=str(fid))
        c.post(
            f"/api/v2/patients/{patient_id}/caregivers",
            json={"caregiver_user_id": str(cg_id), "relationship_label": "parent"},
            headers=bearer(coord_token),
        )
        resp2 = c.post(
            f"/api/v2/patients/{patient_id}/caregivers",
            json={"caregiver_user_id": str(cg_id), "relationship_label": "parent"},
            headers=bearer(coord_token),
        )
        assert resp2.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# CareTeamMember facility authority
# ─────────────────────────────────────────────────────────────────────────────

class TestCareTeamMemberFacilityAuthority:

    def test_doctor_without_member_record_denied_403(self, db_client):
        c, sf = db_client
        tid, fid, actor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "no-member")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        # Deliberately NO seed_member

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["doctor"], facility_id=str(fid))
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 403

    def test_doctor_jwt_facility_conflicts_with_member_facility_403(self, db_client):
        c, sf = db_client
        tid, fid_a, fid_b, actor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "fac-conf")
        seed_facility(sf, tid, fid_a, "FacA")
        seed_facility(sf, tid, fid_b, "FacB")
        seed_patient(sf, tid, patient_id, facility_id=fid_a, name="InA")
        seed_member(sf, tid, user_id=actor_id, role="doctor", facility_id=fid_a)

        # JWT claims facility fid_b; member has fid_a
        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["doctor"], facility_id=str(fid_b))
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Caregiver relationship management lifecycle (HTTP)
# ─────────────────────────────────────────────────────────────────────────────

class TestCaregiverRelationshipManagement:

    def _coordinator(self, c, sf, tid, fid):
        coord_id = uuid4()
        seed_member(sf, tid, user_id=coord_id, role="care_coordinator", facility_id=fid)
        return coord_id

    def test_register_verify_revoke_lifecycle(self, db_client):
        c, sf = db_client
        tid, fid, patient_id, cg_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-mgmt")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_glucose(sf, tid, patient_id, value=110)

        coord_id = self._coordinator(c, sf, tid, fid)
        coord_token = make_jwt(
            sub=str(coord_id), tenant_id=str(tid), roles=["care_coordinator"], facility_id=str(fid)
        )
        cg_token = make_jwt(sub=str(cg_id), tenant_id=str(tid), roles=["caregiver"])

        # 1. Register → PENDING; no access yet
        reg = c.post(
            f"/api/v2/patients/{patient_id}/caregivers",
            json={
                "caregiver_user_id": str(cg_id),
                "relationship_label": "parent",
                "capabilities": ["read_glucose", "read_meal"],
            },
            headers=bearer(coord_token),
        )
        assert reg.status_code == 201
        rel_id = reg.json()["relationship_id"]
        assert reg.json()["status"] == "pending"

        denied = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(cg_token))
        assert denied.status_code == 403

        # 2. Verify → VERIFIED; access now granted
        ver = c.patch(
            f"/api/v2/patients/{patient_id}/caregivers/{rel_id}/verify",
            headers=bearer(coord_token),
        )
        assert ver.status_code == 200
        assert ver.json()["status"] == "verified"

        granted = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(cg_token))
        assert granted.status_code == 200

        # 3. List includes the relationship
        listing = c.get(f"/api/v2/patients/{patient_id}/caregivers", headers=bearer(coord_token))
        assert listing.status_code == 200
        assert any(item["relationship_id"] == rel_id for item in listing.json()["items"])

        # 4. Verify again → 409 conflict (no longer PENDING)
        again = c.patch(
            f"/api/v2/patients/{patient_id}/caregivers/{rel_id}/verify",
            headers=bearer(coord_token),
        )
        assert again.status_code == 409

        # 5. Revoke → access removed
        rev = c.delete(
            f"/api/v2/patients/{patient_id}/caregivers/{rel_id}",
            headers=bearer(coord_token),
        )
        assert rev.status_code == 200
        assert rev.json()["status"] == "revoked"

        after = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(cg_token))
        assert after.status_code == 403

    def test_revoke_twice_returns_conflict(self, db_client):
        c, sf = db_client
        tid, fid, patient_id, cg_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-rev2")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)

        coord_id = self._coordinator(c, sf, tid, fid)
        coord_token = make_jwt(
            sub=str(coord_id), tenant_id=str(tid), roles=["care_coordinator"], facility_id=str(fid)
        )
        reg = c.post(
            f"/api/v2/patients/{patient_id}/caregivers",
            json={"caregiver_user_id": str(cg_id), "relationship_label": "parent"},
            headers=bearer(coord_token),
        )
        rel_id = reg.json()["relationship_id"]
        assert c.delete(
            f"/api/v2/patients/{patient_id}/caregivers/{rel_id}", headers=bearer(coord_token)
        ).status_code == 200
        assert c.delete(
            f"/api/v2/patients/{patient_id}/caregivers/{rel_id}", headers=bearer(coord_token)
        ).status_code == 400

    def test_register_relationship_for_unknown_patient_404(self, db_client):
        c, sf = db_client
        tid, fid = uuid4(), uuid4()
        seed_org(sf, tid, "cg-404")
        seed_facility(sf, tid, fid, "F")
        coord_id = self._coordinator(c, sf, tid, fid)
        coord_token = make_jwt(
            sub=str(coord_id), tenant_id=str(tid), roles=["care_coordinator"], facility_id=str(fid)
        )
        resp = c.post(
            f"/api/v2/patients/{uuid4()}/caregivers",
            json={"caregiver_user_id": str(uuid4()), "relationship_label": "parent"},
            headers=bearer(coord_token),
        )
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Non-manager roles can never manage caregiver relationships
# ─────────────────────────────────────────────────────────────────────────────

class TestCaregiverManagementAuthorization:

    def test_doctor_cannot_register_caregiver(self, db_client):
        c, sf = db_client
        tid, fid, doctor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-nodoc")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_member(sf, tid, user_id=doctor_id, role="doctor", facility_id=fid)

        token = make_jwt(sub=str(doctor_id), tenant_id=str(tid), roles=["doctor"], facility_id=str(fid))
        resp = c.post(
            f"/api/v2/patients/{patient_id}/caregivers",
            json={"caregiver_user_id": str(uuid4()), "relationship_label": "parent"},
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_admin_without_member_record_cannot_register_caregiver(self, db_client):
        c, sf = db_client
        tid, fid, admin_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-noadmin")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        # NO member record for the admin

        token = make_jwt(sub=str(admin_id), tenant_id=str(tid), roles=["admin"])
        resp = c.post(
            f"/api/v2/patients/{patient_id}/caregivers",
            json={"caregiver_user_id": str(uuid4()), "relationship_label": "parent"},
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_patient_role_cannot_register_caregiver(self, db_client):
        c, sf = db_client
        tid, fid, user_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-nopatient")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_identity_mapping(sf, tid, user_id=user_id, patient_id=patient_id, active=True)

        token = make_jwt(sub=str(user_id), tenant_id=str(tid), roles=["patient"])
        resp = c.post(
            f"/api/v2/patients/{patient_id}/caregivers",
            json={"caregiver_user_id": str(uuid4()), "relationship_label": "parent"},
            headers=bearer(token),
        )
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Capability-gated write access + expiration
# ─────────────────────────────────────────────────────────────────────────────

class TestCaregiverWriteOperations:

    def test_write_observations_with_create_glucose_capability(self, db_client):
        c, sf = db_client
        tid, fid, actor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-write")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_caregiver_relationship(
            sf, tid, patient_id=patient_id,
            caregiver_user_id=actor_id,
            status="verified",
            capabilities=["create_glucose"],
        )

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["caregiver"])
        resp = c.post(
            "/api/v2/clinical/observations",
            json={"patient_id": str(patient_id), "value_mg_dl": 140},
            headers=bearer(token),
        )
        assert resp.status_code == 200
        assert resp.json()["value_mg_dl"] == 140

    def test_write_observations_denied_without_create_glucose_capability(self, db_client):
        c, sf = db_client
        tid, fid, actor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-nowrite")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_caregiver_relationship(
            sf, tid, patient_id=patient_id,
            caregiver_user_id=actor_id,
            status="verified",
            capabilities=["read_glucose"],
        )

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["caregiver"])
        resp = c.post(
            "/api/v2/clinical/observations",
            json={"patient_id": str(patient_id), "value_mg_dl": 140},
            headers=bearer(token),
        )
        assert resp.status_code == 403

    def test_patient_self_write_via_identity_mapping(self, db_client):
        c, sf = db_client
        tid, fid, user_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "pt-write")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_identity_mapping(sf, tid, user_id=user_id, patient_id=patient_id, active=True)

        token = make_jwt(sub=str(user_id), tenant_id=str(tid), roles=["patient"])
        resp = c.post(
            "/api/v2/clinical/observations",
            json={"patient_id": str(patient_id), "value_mg_dl": 95},
            headers=bearer(token),
        )
        assert resp.status_code == 200


class TestExpiredCaregiverAccess:

    def test_expired_relationship_denies_read(self, db_client):
        c, sf = db_client
        tid, fid, actor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-exp")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_caregiver_relationship(
            sf, tid, patient_id=patient_id,
            caregiver_user_id=actor_id,
            status="verified",
            capabilities=["read_glucose", "read_meal"],
            expires_at=datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=60),
        )

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["caregiver"])
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Identity-mapping admin robustness
# ─────────────────────────────────────────────────────────────────────────────

class TestIdentityMappingAdminRobustness:

    def test_list_returns_created_mapping(self, db_client):
        c, sf = db_client
        tid, fid, patient_id, user_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "im-list")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_identity_mapping(sf, tid, user_id=user_id, patient_id=patient_id, active=True)

        admin_token = make_jwt(sub=_uid(), tenant_id=str(tid), roles=["admin"])
        resp = c.get("/api/v2/admin/identity-mappings", headers=bearer(admin_token))
        assert resp.status_code == 200
        assert any(m["user_id"] == str(user_id) for m in resp.json())

    def test_deactivate_unknown_mapping_404(self, db_client):
        c, sf = db_client
        tid = uuid4()
        seed_org(sf, tid, "im-404")
        admin_token = make_jwt(sub=_uid(), tenant_id=str(tid), roles=["admin"])
        resp = c.post(
            f"/api/v2/admin/identity-mappings/{uuid4()}/deactivate",
            headers=bearer(admin_token),
        )
        assert resp.status_code == 404

    def test_create_mapping_to_cross_tenant_patient_404(self, db_client):
        c, sf = db_client
        tid, fid = uuid4(), uuid4()
        other_tid, foreign_patient_id = uuid4(), uuid4()
        seed_org(sf, tid, "im-cross")
        seed_facility(sf, tid, fid, "F")
        # Patient belongs to ANOTHER tenant; not visible under this one.
        seed_org(sf, other_tid, "im-other")
        seed_patient(sf, other_tid, foreign_patient_id, facility_id=fid)

        admin_token = make_jwt(sub=_uid(), tenant_id=str(tid), roles=["admin"])
        resp = c.post(
            "/api/v2/admin/identity-mappings",
            json={"user_id": str(uuid4()), "patient_id": str(foreign_patient_id)},
            headers=bearer(admin_token),
        )
        assert resp.status_code == 404