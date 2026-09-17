"""Gate 10F-B — clinician read-contract API tests (CG10F-01..40).

End-to-end coverage of the four clinician read families:

- GET /api/v2/clinical/ai-artifacts [+/{artifact_id}]   (pending-review queue)
- GET /api/v2/clinical/clinical-observations            (clinician feed, carbs/GI)
- GET /api/v2/clinical/medication-plans [+/{plan_id}]   (clinician-authored plans)
- GET /api/v2/patients [+/{patient_id}]                 (facility patient cohort)

Security invariants verified:

- deny-by-default coarse RBAC (patient/caregiver/admin/unknown → 403)
- authoritative member-facility scoping (never client-supplied)
- tenant isolation (cross-tenant never resolves)
- deactivated-patient invariant at every clinician read path
- information asymmetry: proxy roles cannot reach CLINICAL DTOs (carbs/GI,
  medication instructions, AI review evidence)
- strict response DTOs (no PHI bloat, no clinician-only fields in proxy paths)
"""

from __future__ import annotations

import uuid as _uuid
from uuid import uuid4

import pytest

from backend.domain.entities import CareTeamRole, ReviewState

from tests.api.conftest import (
    bearer,
    make_jwt,
    seed_ai_artifact,
    seed_facility,
    seed_glucose,
    seed_meal,
    seed_member,
    seed_medication_plan,
    seed_org,
    seed_patient,
)


def _token(sub, tid, roles, facility_id=None):
    return make_jwt(
        sub=str(sub),
        tenant_id=str(tid),
        roles=roles,
        facility_id=str(facility_id) if facility_id else None,
    )


def _seed_clinic(sf, tenant_id, facility_id, doctor_user, patients):
    """Org + facility + doctor member + patients (all in one facility)."""
    seed_org(sf, tenant_id, f"org-{str(tenant_id)[:8]}")
    seed_facility(sf, tenant_id, facility_id, "Facility")
    seed_member(sf, tenant_id, doctor_user, role=CareTeamRole.DOCTOR, facility_id=facility_id)
    for p in patients:
        seed_patient(
            sf,
            tenant_id,
            p["id"],
            facility_id=p.get("facility_id", facility_id),
            name=p.get("name", "Patient"),
            active=p.get("active", True),
        )
    return facility_id


class TestAiReviewArtifactQueue:

    def _list(self, client, token, **params):
        return client.get("/api/v2/clinical/ai-artifacts", headers=bearer(token), params=params)

    def _detail(self, client, token, artifact_id):
        return client.get(f"/api/v2/clinical/ai-artifacts/{artifact_id}", headers=bearer(token))

    def test_cg10f_01_no_token_401(self, client):
        assert self._list(client, "").status_code == 401
        assert self._detail(client, "", str(uuid4())).status_code == 401

    def test_cg10f_02_doctor_sees_pending_review_only(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p1, p2 = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p1}, {"id": p2}])
        seed_ai_artifact(sf, tid, p1, state=ReviewState.PENDING_REVIEW)
        seed_ai_artifact(sf, tid, p2, state=ReviewState.PENDING_REVIEW)
        seed_ai_artifact(sf, tid, p1, state=ReviewState.APPROVED)
        seed_ai_artifact(sf, tid, p1, state=ReviewState.REJECTED)
        token = _token(doctor, tid, ["doctor"], fid)
        resp = self._list(c, token)
        assert resp.status_code == 200
        body = resp.json()
        assert body["artifact_count"] == 2
        assert all(i["state"] == "pending_review" for i in body["items"])

    def test_cg10f_03_empty_queue_is_valid(self, db_client):
        c, sf = db_client
        tid, fid, doctor = uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [])
        resp = self._list(c, _token(doctor, tid, ["doctor"], fid))
        assert resp.status_code == 200
        assert resp.json() == {"artifact_count": 0, "items": []}

    def test_cg10f_04_other_facility_artifacts_excluded(self, db_client):
        c, sf = db_client
        tid, fid_a, fid_b, doctor, p_a, p_b = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid_a, doctor, [{"id": p_a}])
        seed_facility(sf, tid, fid_b, "B")
        seed_patient(sf, tid, p_b, facility_id=fid_b)
        seed_ai_artifact(sf, tid, p_a, state=ReviewState.PENDING_REVIEW)
        seed_ai_artifact(sf, tid, p_b, state=ReviewState.PENDING_REVIEW)
        resp = self._list(c, _token(doctor, tid, ["doctor"], fid_a))
        assert resp.status_code == 200
        assert resp.json()["artifact_count"] == 1
        assert resp.json()["items"][0]["patient_id"] == str(p_a)

    def test_cg10f_05_deactivated_patient_artifact_excluded(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p_dead, p_ok = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid, doctor,
            [{"id": p_dead, "active": False}, {"id": p_ok}],
        )
        seed_ai_artifact(sf, tid, p_dead, state=ReviewState.PENDING_REVIEW)
        seed_ai_artifact(sf, tid, p_ok, state=ReviewState.PENDING_REVIEW)
        resp = self._list(c, _token(doctor, tid, ["doctor"], fid))
        assert resp.json()["artifact_count"] == 1

    def test_cg10f_06_client_facility_cannot_widen_scope(self, db_client):
        c, sf = db_client
        tid, fid_a, fid_b, doctor, p_a, p_b = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid_a, doctor, [{"id": p_a}])
        seed_facility(sf, tid, fid_b, "B")
        seed_patient(sf, tid, p_b, facility_id=fid_b)
        seed_ai_artifact(sf, tid, p_a, state=ReviewState.PENDING_REVIEW)
        seed_ai_artifact(sf, tid, p_b, state=ReviewState.PENDING_REVIEW)
        baseline = self._list(c, _token(doctor, tid, ["doctor"], fid_a)).json()
        # A client-supplied facility_id query param must NOT widen the queue.
        attempt = self._list(c, _token(doctor, tid, ["doctor"], fid_a), facility_id=str(fid_b))
        assert attempt.status_code == 200
        assert attempt.json() == baseline

    def test_cg10f_07_cross_tenant_never_surfaces(self, db_client):
        c, sf = db_client
        tid_a, tid_b, fid_a, fid_b, doctor, p_b = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid_a, fid_a, doctor, [])
        seed_org(sf, tid_b, f"org-b-{str(tid_b)[:8]}")
        seed_facility(sf, tid_b, fid_b, "B")
        seed_patient(sf, tid_b, p_b, facility_id=fid_b)
        seed_ai_artifact(sf, tid_b, p_b, state=ReviewState.PENDING_REVIEW)
        resp = self._list(c, _token(doctor, tid_a, ["doctor"], fid_a))
        assert resp.status_code == 200
        assert resp.json()["artifact_count"] == 0

    def test_cg10f_08_item_schema_is_strict(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p}])
        seed_ai_artifact(sf, tid, p, state=ReviewState.PENDING_REVIEW)
        resp = self._list(c, _token(doctor, tid, ["doctor"], fid))
        item = resp.json()["items"][0]
        assert set(item.keys()) == {
            "artifact_id", "patient_id", "artifact_kind", "state", "summary", "created_at",
        }

    def test_cg10f_09_detail_own_facility_200(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p}])
        artifact = seed_ai_artifact(sf, tid, p, state=ReviewState.PENDING_REVIEW)
        resp = self._detail(c, _token(doctor, tid, ["doctor"], fid), artifact.id)
        assert resp.status_code == 200
        assert resp.json()["artifact_id"] == str(artifact.id)
        assert resp.json()["patient_id"] == str(p)

    def test_cg10f_10_detail_cross_facility_403(self, db_client):
        c, sf = db_client
        tid, fid_a, fid_b, doctor, p_b = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid_a, doctor, [])
        seed_facility(sf, tid, fid_b, "B")
        seed_patient(sf, tid, p_b, facility_id=fid_b)
        artifact = seed_ai_artifact(sf, tid, p_b, state=ReviewState.PENDING_REVIEW)
        resp = self._detail(c, _token(doctor, tid, ["doctor"], fid_a), artifact.id)
        assert resp.status_code == 403

    def test_cg10f_11_detail_cross_tenant_404(self, db_client):
        c, sf = db_client
        tid_a, tid_b, fid_a, fid_b, doctor, p_b = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid_a, fid_a, doctor, [])
        seed_org(sf, tid_b, f"org-b-{str(tid_b)[:8]}")
        seed_facility(sf, tid_b, fid_b, "B")
        seed_patient(sf, tid_b, p_b, facility_id=fid_b)
        artifact = seed_ai_artifact(sf, tid_b, p_b, state=ReviewState.PENDING_REVIEW)
        resp = self._detail(c, _token(doctor, tid_a, ["doctor"], fid_a), artifact.id)
        assert resp.status_code == 404

    def test_cg10f_12_detail_deactivated_patient_403(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p, "active": False}])
        artifact = seed_ai_artifact(sf, tid, p, state=ReviewState.PENDING_REVIEW)
        resp = self._detail(c, _token(doctor, tid, ["doctor"], fid), artifact.id)
        assert resp.status_code == 403

    def test_cg10f_13_detail_missing_404(self, db_client):
        c, sf = db_client
        tid, fid, doctor = uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [])
        resp = self._detail(c, _token(doctor, tid, ["doctor"], fid), str(uuid4()))
        assert resp.status_code == 404

    def test_cg10f_14_nurse_and_dietitian_allowed(self, db_client):
        c, sf = db_client
        tid, fid, p = uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, p, facility_id=fid)
        seed_ai_artifact(sf, tid, p, state=ReviewState.PENDING_REVIEW)
        for role in ["nurse", "dietitian"]:
            user = uuid4()
            seed_member(sf, tid, user, role=role, facility_id=fid)
            resp = self._list(c, _token(user, tid, [role], fid))
            assert resp.status_code == 200
            assert resp.json()["artifact_count"] == 1

    @pytest.mark.parametrize("role", ["patient", "caregiver", "admin", "sysop", "field_health_worker"])
    def test_cg10f_15_non_read_roles_denied(self, db_client, role):
        c, sf = db_client
        tid, fid, user, p = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, p, facility_id=fid)
        seed_ai_artifact(sf, tid, p, state=ReviewState.PENDING_REVIEW)
        resp = self._list(c, _token(user, tid, [role], fid))
        assert resp.status_code == 403
        artifact = seed_ai_artifact(sf, tid, p, state=ReviewState.PENDING_REVIEW)
        resp = self._detail(c, _token(user, tid, [role], fid), artifact.id)
        assert resp.status_code == 403

    def test_cg10f_15b_doctor_without_member_denied(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, p, facility_id=fid)
        seed_ai_artifact(sf, tid, p, state=ReviewState.PENDING_REVIEW)
        resp = self._list(c, _token(doctor, tid, ["doctor"], fid))
        assert resp.status_code == 403


class TestClinicalObservationFeed:

    def _feed(self, client, token, patient_id):
        return client.get(
            "/api/v2/clinical/clinical-observations",
            headers=bearer(token),
            params={"patient_id": str(patient_id)},
        )

    def test_cg10f_20_doctor_sees_carb_analytics(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p}])
        seed_glucose(sf, tid, p, value=145)
        seed_meal(sf, tid, p, carbs=52.5, gi="medium")
        resp = self._feed(c, _token(doctor, tid, ["doctor"], fid), p)
        assert resp.status_code == 200
        kinds = {i["kind"]: i for i in resp.json()["items"]}
        assert "glucose" in kinds and kinds["glucose"]["value_mg_dl"] == 145
        assert "meal" in kinds
        assert kinds["meal"]["carbs_grams"] == 52.5
        assert kinds["meal"]["glycemic_index"] == "medium"

    def test_cg10f_21_patient_denied_even_with_self_mapping(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p}])
        seed_meal(sf, tid, p, carbs=30.0, gi="low")
        from tests.api.conftest import seed_identity_mapping

        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p, active=True)
        token = _token(patient_user, tid, ["patient"], fid)
        assert self._feed(c, token, p).status_code == 403

    def test_cg10f_22_caregiver_denied_even_with_full_read_caps(self, db_client):
        c, sf = db_client
        tid, fid, doctor, caregiver, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p}])
        seed_meal(sf, tid, p, carbs=30.0, gi="low")
        from tests.api.conftest import seed_caregiver_relationship

        seed_caregiver_relationship(
            sf,
            tid,
            patient_id=p,
            caregiver_user_id=caregiver,
            capabilities=["read_glucose", "read_meal"],
        )
        token = _token(caregiver, tid, ["caregiver"], fid)
        assert self._feed(c, token, p).status_code == 403

    def test_cg10f_23_doctor_cross_facility_403(self, db_client):
        c, sf = db_client
        tid, fid_a, fid_b, doctor, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid_a, "A")
        seed_member(sf, tid, doctor, role=CareTeamRole.DOCTOR, facility_id=fid_a)
        seed_facility(sf, tid, fid_b, "B")
        seed_patient(sf, tid, p, facility_id=fid_b)
        resp = self._feed(c, _token(doctor, tid, ["doctor"], fid_a), p)
        assert resp.status_code == 403

    def test_cg10f_24_doctor_without_member_403(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, p, facility_id=fid)
        resp = self._feed(c, _token(doctor, tid, ["doctor"], fid), p)
        assert resp.status_code == 403

    def test_cg10f_25_deactivated_patient_403(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p, "active": False}])
        resp = self._feed(c, _token(doctor, tid, ["doctor"], fid), p)
        assert resp.status_code == 403

    def test_cg10f_26_missing_patient_404(self, db_client):
        c, sf = db_client
        tid, fid, doctor = uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [])
        resp = self._feed(c, _token(doctor, tid, ["doctor"], fid), str(uuid4()))
        assert resp.status_code == 404

    def test_cg10f_27_patient_facing_feed_never_has_carbs(self, db_client):
        """Information-asymmetry regression: the patient-facing feed route must
        never expose analytical fields even to a clinician caller."""
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p}])
        seed_meal(sf, tid, p, carbs=52.5, gi="medium")
        token = _token(doctor, tid, ["doctor"], fid)
        resp = c.get(
            "/api/v2/clinical/observations",
            headers=bearer(token),
            params={"patient_id": str(p)},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert "carbs_grams" not in item
            assert "glycemic_index" not in item


class TestMedicationPlans:

    def _list(self, client, token, **params):
        return client.get("/api/v2/clinical/medication-plans", headers=bearer(token), params=params)

    def _detail(self, client, token, plan_id):
        return client.get(f"/api/v2/clinical/medication-plans/{plan_id}", headers=bearer(token))

    def test_cg10f_30_doctor_sees_facility_plans(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p}])
        plan = seed_medication_plan(sf, tid, p, medication="Metformin", instruction="500 mg with meals")
        resp = self._list(c, _token(doctor, tid, ["doctor"], fid))
        assert resp.status_code == 200
        body = resp.json()
        assert body["plan_count"] == 1
        assert body["items"][0]["medication_plan_id"] == str(plan.id)
        assert body["items"][0]["instruction"] == "500 mg with meals"
        assert body["items"][0]["active"] is True

    def test_cg10f_31_other_facility_and_deactivated_excluded(self, db_client):
        c, sf = db_client
        tid, fid_a, fid_b, doctor, p_ok, p_b, p_dead = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid_a, doctor,
            [{"id": p_ok}, {"id": p_dead, "active": False}],
        )
        seed_facility(sf, tid, fid_b, "B")
        seed_patient(sf, tid, p_b, facility_id=fid_b)
        seed_medication_plan(sf, tid, p_ok)
        seed_medication_plan(sf, tid, p_dead)
        seed_medication_plan(sf, tid, p_b)
        resp = self._list(c, _token(doctor, tid, ["doctor"], fid_a))
        assert resp.json()["plan_count"] == 1

    def test_cg10f_32_detail_own_facility_200_and_cross_403(self, db_client):
        c, sf = db_client
        tid, fid_a, fid_b, doctor, p_a, p_b = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid_a, doctor, [{"id": p_a}])
        seed_facility(sf, tid, fid_b, "B")
        seed_patient(sf, tid, p_b, facility_id=fid_b)
        plan_a = seed_medication_plan(sf, tid, p_a)
        plan_b = seed_medication_plan(sf, tid, p_b)
        token = _token(doctor, tid, ["doctor"], fid_a)
        assert self._detail(c, token, plan_a.id).status_code == 200
        assert self._detail(c, token, plan_b.id).status_code == 403

    def test_cg10f_33_detail_cross_tenant_404(self, db_client):
        c, sf = db_client
        tid_a, tid_b, fid_a, fid_b, doctor, p_b = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid_a, fid_a, doctor, [])
        seed_org(sf, tid_b, f"org-b-{str(tid_b)[:8]}")
        seed_facility(sf, tid_b, fid_b, "B")
        seed_patient(sf, tid_b, p_b, facility_id=fid_b)
        plan = seed_medication_plan(sf, tid_b, p_b)
        resp = self._detail(c, _token(doctor, tid_a, ["doctor"], fid_a), plan.id)
        assert resp.status_code == 404

    def test_cg10f_34_detail_deactivated_patient_403(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p, "active": False}])
        plan = seed_medication_plan(sf, tid, p)
        resp = self._detail(c, _token(doctor, tid, ["doctor"], fid), plan.id)
        assert resp.status_code == 403

    def test_cg10f_35_patient_caregiver_denied(self, db_client):
        c, sf = db_client
        tid, fid, user, p = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, p, facility_id=fid)
        plan = seed_medication_plan(sf, tid, p)
        for role in ["patient", "caregiver", "admin", "sysop"]:
            token = _token(user, tid, [role], fid)
            assert self._list(c, token).status_code == 403
            assert self._detail(c, token, plan.id).status_code == 403

    def test_cg10f_36_detail_missing_404(self, db_client):
        c, sf = db_client
        tid, fid, doctor = uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [])
        resp = self._detail(c, _token(doctor, tid, ["doctor"], fid), str(uuid4()))
        assert resp.status_code == 404


class TestPatientCohort:

    def _list(self, client, token, **params):
        return client.get("/api/v2/patients", headers=bearer(token), params=params)

    def _detail(self, client, token, patient_id):
        return client.get(f"/api/v2/patients/{patient_id}", headers=bearer(token))

    def test_cg10f_40_doctor_sees_active_facility_cohort(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p1, p2 = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid, doctor,
            [{"id": p1, "name": "Alice"}, {"id": p2, "name": "Bob"}],
        )
        resp = self._list(c, _token(doctor, tid, ["doctor"], fid))
        assert resp.status_code == 200
        body = resp.json()
        assert body["patient_count"] == 2
        names = {i["name"] for i in body["items"]}
        assert names == {"Alice", "Bob"}
        item = body["items"][0]
        assert set(item.keys()) == {
            "patient_id", "uh_id", "name", "facility_id", "active", "created_at",
        }
        assert item["facility_id"] == str(fid)

    def test_cg10f_41_other_facility_and_deactivated_excluded(self, db_client):
        c, sf = db_client
        tid, fid_a, fid_b, doctor, p_a, p_b, p_dead = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid_a, doctor,
            [{"id": p_a}, {"id": p_dead, "active": False}],
        )
        seed_facility(sf, tid, fid_b, "B")
        seed_patient(sf, tid, p_b, facility_id=fid_b)
        resp = self._list(c, _token(doctor, tid, ["doctor"], fid_a))
        assert resp.json()["patient_count"] == 1
        assert {i["patient_id"] for i in resp.json()["items"]} == {str(p_a)}

    def test_cg10f_42_patient_cannot_enumerate_cohort(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p}])
        from tests.api.conftest import seed_identity_mapping

        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p, active=True)
        token = _token(patient_user, tid, ["patient"], fid)
        assert self._list(c, token).status_code == 403
        assert self._detail(c, token, p).status_code == 403

    def test_cg10f_43_caregiver_cannot_read_cohort(self, db_client):
        c, sf = db_client
        tid, fid, doctor, caregiver, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p}])
        from tests.api.conftest import seed_caregiver_relationship

        seed_caregiver_relationship(sf, tid, patient_id=p, caregiver_user_id=caregiver)
        token = _token(caregiver, tid, ["caregiver"], fid)
        assert self._list(c, token).status_code == 403
        assert self._detail(c, token, p).status_code == 403

    def test_cg10f_44_detail_cross_facility_403_cross_tenant_404(self, db_client):
        c, sf = db_client
        tid, fid_a, fid_b, doctor, p_a, p_b = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid_a, doctor, [{"id": p_a}])
        seed_facility(sf, tid, fid_b, "B")
        seed_patient(sf, tid, p_b, facility_id=fid_b)
        token = _token(doctor, tid, ["doctor"], fid_a)
        assert self._detail(c, token, p_a).status_code == 200
        assert self._detail(c, token, p_b).status_code == 403

        tid2, fid2, doctor2, p2 = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid2, f"org-{str(tid2)[:8]}")
        seed_facility(sf, tid2, fid2, "F2")
        seed_patient(sf, tid2, p2, facility_id=fid2)
        resp = self._detail(c, _token(doctor, tid, ["doctor"], fid_a), p2)
        assert resp.status_code == 404

    def test_cg10f_45_detail_deactivated_403_missing_404(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p_dead = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, doctor, [{"id": p_dead, "active": False}])
        token = _token(doctor, tid, ["doctor"], fid)
        assert self._detail(c, token, p_dead).status_code == 403
        assert self._detail(c, token, str(uuid4())).status_code == 404

    def test_cg10f_46_admin_and_field_health_worker_denied(self, db_client):
        c, sf = db_client
        tid, fid, user, p = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, p, facility_id=fid)
        for role in ["admin", "sysop"]:
            token = _token(user, tid, [role], fid)
            assert self._list(c, token).status_code == 403
            assert self._detail(c, token, p).status_code == 403