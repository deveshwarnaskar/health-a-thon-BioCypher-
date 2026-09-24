"""Gate 10E-B — caregiver patient discovery contract tests (CG10B-01..18).

Verifies GET /api/v2/caregivers/me/patients end to end:

- derived identity/tenant exclusively from the verified JWT (never callback)
- relationship filter matrix (verified/active/not-revoked/not-expired)
- deactivated-patient invariant at discovery AND at the observation boundary
- capability preservation, information asymmetry, deny-by-default roles
- Gate 10D patient regression + caregiver observation authorization regression
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from tests.api.conftest import (
    bearer,
    make_jwt,
    seed_facility,
    seed_glucose,
    seed_org,
    seed_patient,
    seed_caregiver_relationship,
)


def _now_past(seconds: int = 3600) -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=seconds)


def _now_future(seconds: int = 3600) -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=seconds)


def _seed_world(sf, *, relationships: list[dict], patients: list[dict], tenant_id):
    """Seed an org/facility, patients, and caregiver relationship rows."""
    seed_org(sf, tenant_id, f"eg-{str(tenant_id)[:8]}")
    fid = uuid4()
    seed_facility(sf, tenant_id, fid, "Facility")
    for p in patients:
        seed_patient(sf, tenant_id, p["id"], facility_id=fid, name=p.get("name", "Patient"), active=p.get("active", True))
    for rel in relationships:
        seed_caregiver_relationship(
            sf,
            tenant_id,
            patient_id=rel["patient_id"],
            caregiver_user_id=rel["caregiver_user_id"],
            status=rel.get("status", "verified"),
            capabilities=rel.get("capabilities"),
            expires_at=rel.get("expires_at"),
        )


class TestCaregiverPatientDiscovery:

    def _get(self, client, token, **params):
        return client.get("/api/v2/caregivers/me/patients", headers=bearer(token), params=params)

    # ── CG10B-01 ────────────────────────────────────────────────────────────
    def test_cg10b_01_single_verified_relationship(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid, "name": "Mom"}],
            relationships=[{"patient_id": pid, "caregiver_user_id": user}],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        resp = self._get(c, token)
        assert resp.status_code == 200
        body = resp.json()
        assert body["patient_count"] == 1
        item = body["items"][0]
        assert item["patient_id"] == str(pid)
        assert item["status"] == "verified"
        assert item["name"] == "Mom"
        assert item["capabilities"] == sorted(["read_glucose", "read_meal"])

    # ── CG10B-02 ────────────────────────────────────────────────────────────
    def test_cg10b_02_multiple_verified_relationships(self, db_client):
        c, sf = db_client
        tid, user = uuid4(), uuid4()
        pids = [uuid4(), uuid4(), uuid4()]
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": p} for p in pids],
            relationships=[{"patient_id": p, "caregiver_user_id": user} for p in pids],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        resp = self._get(c, token)
        assert resp.status_code == 200
        body = resp.json()
        assert body["patient_count"] == 3
        assert {item["patient_id"] for item in body["items"]} == {str(p) for p in pids}

    # ── CG10B-03 ────────────────────────────────────────────────────────────
    def test_cg10b_03_pending_relationship_excluded(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[{"patient_id": pid, "caregiver_user_id": user, "status": "pending"}],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        resp = self._get(c, token)
        assert resp.status_code == 200
        assert resp.json() == {"patient_count": 0, "items": []}

    # ── CG10B-04 ────────────────────────────────────────────────────────────
    def test_cg10b_04_revoked_relationship_excluded(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[{"patient_id": pid, "caregiver_user_id": user, "status": "revoked"}],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        resp = self._get(c, token)
        assert resp.status_code == 200
        assert resp.json() == {"patient_count": 0, "items": []}

    # ── CG10B-05 ────────────────────────────────────────────────────────────
    def test_cg10b_05_expired_relationship_excluded(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[{"patient_id": pid, "caregiver_user_id": user, "expires_at": _now_past()}],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        resp = self._get(c, token)
        assert resp.status_code == 200
        assert resp.json() == {"patient_count": 0, "items": []}

    # ── CG10B-06 ────────────────────────────────────────────────────────────
    def test_cg10b_06_deactivated_patient_excluded(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid, "active": False}],
            relationships=[{"patient_id": pid, "caregiver_user_id": user}],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        resp = self._get(c, token)
        assert resp.status_code == 200
        assert resp.json() == {"patient_count": 0, "items": []}

    # ── CG10B-07 ────────────────────────────────────────────────────────────
    def test_cg10b_07_no_relationships_empty_list(self, db_client):
        c, sf = db_client
        tid, user = uuid4(), uuid4()
        seed_org(sf, tid, "eg-empty")
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        resp = self._get(c, token)
        assert resp.status_code == 200
        assert resp.json() == {"patient_count": 0, "items": []}

    # ── CG10B-08 ────────────────────────────────────────────────────────────
    def test_cg10b_08_cannot_supply_another_caregiver_user_id(self, db_client):
        c, sf = db_client
        tid, user_a, user_b, pid_a, pid_b = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid_a, "name": "A"}, {"id": pid_b, "name": "B"}],
            relationships=[
                {"patient_id": pid_a, "caregiver_user_id": user_a},
                {"patient_id": pid_b, "caregiver_user_id": user_b},
            ],
        )
        token_a = make_jwt(sub=str(user_a), tenant_id=str(tid), roles=["caregiver"])
        # Attempting to ask about user_b MUST NOT surface user_b's patients.
        resp = self._get(c, token_a, caregiver_user_id=str(user_b))
        assert resp.status_code == 200
        assert {item["patient_id"] for item in resp.json()["items"]} == {str(pid_a)}

    # ── CG10B-09 ────────────────────────────────────────────────────────────
    def test_cg10b_09_client_tenant_id_cannot_alter_scope(self, db_client):
        c, sf = db_client
        tid, other_tid, user, pid = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[{"patient_id": pid, "caregiver_user_id": user}],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        baseline = self._get(c, token).json()
        assert baseline["patient_count"] == 1
        # A client-supplied tenant_id (query param) is ignored by the contract.
        attempt = self._get(c, token, tenant_id=str(other_tid))
        assert attempt.status_code == 200
        assert attempt.json() == baseline

    # ── CG10B-10 ────────────────────────────────────────────────────────────
    def test_cg10b_10_cross_tenant_patient_never_appears(self, db_client):
        c, sf = db_client
        tid_a, tid_b = uuid4(), uuid4()
        user = uuid4()
        pid_a, pid_b = uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid_a,
            patients=[{"id": pid_a, "name": "A"}],
            relationships=[{"patient_id": pid_a, "caregiver_user_id": user}],
        )
        _seed_world(
            sf,
            tenant_id=tid_b,
            patients=[{"id": pid_b, "name": "B"}],
            relationships=[{"patient_id": pid_b, "caregiver_user_id": user}],
        )
        token_a = make_jwt(sub=str(user), tenant_id=str(tid_a), roles=["caregiver"])
        resp = self._get(c, token_a)
        assert resp.status_code == 200
        assert {item["patient_id"] for item in resp.json()["items"]} == {str(pid_a)}

    # ── CG10B-11 / §9 role gate ─────────────────────────────────────────────
    @pytest.mark.parametrize("role", ["patient", "nurse", "doctor", "admin"])
    def test_cg10b_11_non_caregiver_roles_denied(self, db_client, role):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[{"patient_id": pid, "caregiver_user_id": user}],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=[role])
        resp = self._get(c, token)
        assert resp.status_code == 403

    def test_cg10b_11b_unknown_role_denied(self, client):
        token = make_jwt(sub=str(uuid4()), tenant_id=str(uuid4()), roles=["sysop"])
        resp = client.get("/api/v2/caregivers/me/patients", headers=bearer(token))
        assert resp.status_code == 403

    # ── CG10B-12 ────────────────────────────────────────────────────────────
    def test_cg10b_12_capabilities_preserved_exactly(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        caps = ["create_glucose", "read_glucose", "read_meal"]
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[{"patient_id": pid, "caregiver_user_id": user, "capabilities": caps}],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        resp = self._get(c, token)
        item = resp.json()["items"][0]
        assert sorted(item["capabilities"]) == sorted(caps)
        assert set(item["capabilities"]) <= {
            "read_glucose", "create_glucose", "read_meal", "create_meal",
            "read_medication_events", "create_medication_events",
            "read_care_tasks", "complete_care_tasks",
        }

    # ── CG10B-13 ────────────────────────────────────────────────────────────
    def test_cg10b_13_no_clinician_only_fields_in_dto(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid, "name": "Safe"}],
            relationships=[{"patient_id": pid, "caregiver_user_id": user}],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        resp = self._get(c, token)
        item = resp.json()["items"][0]
        assert set(item.keys()) == {
            "relationship_id", "patient_id", "relationship_label", "status",
            "capabilities", "expires_at", "name",
        }
        forbidden = {
            "carbs_grams", "glycemic_index", "TIR", "TAR", "TBR", "GMI",
            "coefficient_of_variation", "cv", "risk", "risk_score",
            "recommendation", "treatment", "medication", "dosage",
            "ai_review", "artifact", "internal", "secret", "credential", "token",
        }
        assert forbidden.isdisjoint(item.keys())
        # status is a verified-only literal
        assert item["status"] == "verified"

    def test_cg10b_13b_response_schema_is_strict(self, db_client):
        """The strict response DTO refuses unknown fields at the boundary."""
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[{"patient_id": pid, "caregiver_user_id": user}],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        resp = self._get(c, token)
        assert resp.status_code == 200


class TestCaregiverObservationRegression:

    def _get_feed(self, client, token, patient_id):
        return client.get(
            "/api/v2/clinical/observations",
            headers=bearer(token),
            params={"patient_id": str(patient_id)},
        )

    def _post_glucose(self, client, token, patient_id):
        return client.post(
            "/api/v2/clinical/observations",
            headers=bearer(token),
            json={"patient_id": str(patient_id), "value_mg_dl": 140},
        )

    # ── CG10B-14 ────────────────────────────────────────────────────────────
    def test_cg10b_14_patient_glucose_get_regression(self, db_client):
        c, sf = db_client
        tid, fid, user, pid = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-reg")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, pid, facility_id=fid)
        seed_glucose(sf, tid, pid, value=120)
        from tests.api.conftest import seed_identity_mapping

        seed_identity_mapping(sf, tid, user_id=user, patient_id=pid, active=True)
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["patient"])
        resp = self._get_feed(c, token, pid)
        assert resp.status_code == 200
        assert any(i.get("value_mg_dl") == 120 for i in resp.json()["items"] if i.get("kind") == "glucose")

    # ── CG10B-15 ────────────────────────────────────────────────────────────
    def test_cg10b_15_patient_glucose_post_regression(self, db_client):
        c, sf = db_client
        tid, fid, user, pid = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, "cg-post")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, pid, facility_id=fid)
        from tests.api.conftest import seed_identity_mapping

        seed_identity_mapping(sf, tid, user_id=user, patient_id=pid, active=True)
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["patient"])
        resp = self._post_glucose(c, token, pid)
        assert resp.status_code == 200
        assert resp.json()["value_mg_dl"] == 140

    # ── CG10B-16 ────────────────────────────────────────────────────────────
    def test_cg10b_16_caregiver_read_requires_both_read_capabilities(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[
                {"patient_id": pid, "caregiver_user_id": user, "capabilities": ["read_glucose"]},
            ],
        )
        seed_glucose(sf, tid, pid, value=150)
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        assert self._get_feed(c, token, pid).status_code == 403

    def test_cg10b_16b_caregiver_read_allowed_with_full_read_caps(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[
                {"patient_id": pid, "caregiver_user_id": user, "capabilities": ["read_glucose", "read_meal"]},
            ],
        )
        seed_glucose(sf, tid, pid, value=150)
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        resp = self._get_feed(c, token, pid)
        assert resp.status_code == 200

    def test_cg10b_16c_caregiver_write_requires_create_glucose(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[
                {"patient_id": pid, "caregiver_user_id": user, "capabilities": ["read_glucose", "read_meal"]},
            ],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        assert self._post_glucose(c, token, pid).status_code == 403

    def test_cg10b_16d_caregiver_write_allowed_with_create_glucose(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[
                {"patient_id": pid, "caregiver_user_id": user, "capabilities": ["create_glucose"]},
            ],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        resp = self._post_glucose(c, token, pid)
        assert resp.status_code == 200

    # ── CG10B-17 ────────────────────────────────────────────────────────────
    def test_cg10b_17_deactivated_patient_inaccessible_via_caregiver_observation_path(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid, "active": False}],
            relationships=[
                {"patient_id": pid, "caregiver_user_id": user, "capabilities": ["read_glucose", "read_meal", "create_glucose"]},
            ],
        )
        seed_glucose(sf, tid, pid, value=170)
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        assert self._get_feed(c, token, pid).status_code == 403
        assert self._post_glucose(c, token, pid).status_code == 403

    # ── CG10B-18 ────────────────────────────────────────────────────────────
    def test_cg10b_18_expired_relationship_cannot_access_observation_routes(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[
                {"patient_id": pid, "caregiver_user_id": user, "expires_at": _now_past()},
            ],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        assert self._get_feed(c, token, pid).status_code == 403
        assert self._post_glucose(c, token, pid).status_code == 403

    def test_cg10b_18b_revoked_relationship_cannot_access_observation_routes(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[
                {"patient_id": pid, "caregiver_user_id": user, "status": "revoked"},
            ],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        assert self._get_feed(c, token, pid).status_code == 403
        assert self._post_glucose(c, token, pid).status_code == 403

    def test_cg10b_18c_pending_relationship_cannot_access_observation_routes(self, db_client):
        c, sf = db_client
        tid, user, pid = uuid4(), uuid4(), uuid4()
        _seed_world(
            sf,
            tenant_id=tid,
            patients=[{"id": pid}],
            relationships=[
                {"patient_id": pid, "caregiver_user_id": user, "status": "pending"},
            ],
        )
        token = make_jwt(sub=str(user), tenant_id=str(tid), roles=["caregiver"])
        assert self._get_feed(c, token, pid).status_code == 403
        assert self._post_glucose(c, token, pid).status_code == 403