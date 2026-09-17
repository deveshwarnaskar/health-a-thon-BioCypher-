"""Gate 10H-B — contract-surface API tests (CG10H-B-01..).

End-to-end coverage of the new mutation + provisioning contracts:

- POST /api/v2/clinical/meals                    (meal documentation: draft)
- POST /api/v2/clinical/meals/{id}/confirm       (patient confirmation authority)
- POST /api/v2/clinical/medication-administrations (patient adherence event)
- GET/POST /api/v2/care-tasks, POST .../complete (care-team workflow)
- POST /api/v2/patients                          (administrator provisioning)
- POST /api/v2/admin/care-team-members           (administrator provisioning)

Security invariants verified:

- deny-by-default coarse RBAC for every new operation (unknown roles → 403)
- patient self-access ONLY through an active identity mapping (never via role)
- caregiver mutation access ONLY through VERIFIED relationship + capability
- deactivated-patient invariant at every proxy path
- authoritative member-facility scoping (never client-supplied) on clinician paths
- patient-facing DTOs never expose carbs_grams / glycemic_index
- meal confirmation + medication-administration are PATIENT-authority only
- provisioning is ADMIN-role only (tenant from JWT, never the body)
- idempotency applied to every mutation (replay verbatim / mismatch 409)
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.domain.entities import CareTeamRole

from tests.api.conftest import (
    bearer,
    make_jwt,
    seed_caregiver_relationship,
    seed_facility,
    seed_identity_mapping,
    seed_meal,
    seed_medication_plan,
    seed_member,
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


def _seed_clinic(sf, tenant_id, facility_id, users=None, patients=None, roles=None):
    """Org + facility + members + patients (all in one facility)."""
    seed_org(sf, tenant_id, f"org-{str(tenant_id)[:8]}")
    seed_facility(sf, tenant_id, facility_id, "Facility")
    users = users or []
    roles = roles or []
    for user, role in zip(users, roles):
        seed_member(sf, tenant_id, user, role=role, facility_id=facility_id)
    for p in (patients or []):
        seed_patient(
            sf,
            tenant_id,
            p["id"],
            facility_id=p.get("facility_id", facility_id),
            name=p.get("name", "Patient"),
            active=p.get("active", True),
        )
    return facility_id


def _seed_patient_with_phone(sf, tenant_id, patient_id, facility_id, phone="+919000000001", active=True, uh_id="P-0001"):
    from backend.infrastructure.persistence.models.patient_models import PatientModel

    now = datetime.now(timezone.utc)
    with sf() as s:
        s.add(
            PatientModel(
                id=patient_id,
                tenant_id=tenant_id,
                facility_id=facility_id,
                uh_id=uh_id,
                name="Has Phone",
                phone=phone,
                active=active,
                created_at=now,
            )
        )
        s.commit()


def _seed_care_task(sf, tenant_id, patient_id, assigned_to_user_id, description="Follow up"):
    from backend.domain.entities import CareTask
    from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork

    task = CareTask(
        id=uuid4(),
        patient_id=patient_id,
        assigned_to_user_id=assigned_to_user_id,
        description=description,
    )
    with SqlAlchemyUnitOfWork(sf, tenant_id) as uow:
        uow.care_tasks.add(task)
        uow.commit()
    return task


class TestMealDocumentationDraft:

    def _draft(self, client, token, payload, key=None):
        headers = bearer(token)
        if key:
            headers["Idempotency-Key"] = key
        return client.post("/api/v2/clinical/meals", json=payload, headers=headers)

    def test_cg10hb_01_no_token_401(self, client):
        resp = self._draft(client, "", {"patient_id": str(uuid4()), "description": "dal rice"})
        assert resp.status_code == 401

    def test_cg10hb_02_doctor_drafts_meal(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        resp = self._draft(
            c,
            _token(doctor, tid, ["doctor"], fid),
            {"patient_id": str(p), "description": "dal rice", "portion": {"food_key": "rice", "katori_volume_ml": 220, "quantity": 1.0}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"meal_observation_id", "patient_id", "portion_label", "quantity"}
        assert body["patient_id"] == str(p)
        assert body["portion_label"] == "medium"
        assert body["quantity"] == 1.0
        assert "carbs_grams" not in body
        assert "glycemic_index" not in body

    def test_cg10hb_03_patient_self_drafts_meal(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p, active=True)
        resp = self._draft(
            c,
            _token(patient_user, tid, ["patient"], p and fid),
            {"patient_id": str(p), "description": "chapati"},
        )
        assert resp.status_code == 200
        assert resp.json()["patient_id"] == str(p)

    def test_cg10hb_04_patient_self_without_mapping_denied(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        resp = self._draft(
            c,
            _token(patient_user, tid, ["patient"], fid),
            {"patient_id": str(p), "description": "chapati"},
        )
        assert resp.status_code == 403

    def test_cg10hb_05_patient_cannot_draft_for_another_patient(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p_self, p_other = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR],
            patients=[{"id": p_self}, {"id": p_other}],
        )
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p_self, active=True)
        resp = self._draft(
            c,
            _token(patient_user, tid, ["patient"], fid),
            {"patient_id": str(p_other), "description": "chapati"},
        )
        assert resp.status_code == 403

    def test_cg10hb_06_caregiver_create_meal_capability(self, db_client):
        c, sf = db_client
        tid, fid, doctor, caregiver, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        seed_caregiver_relationship(
            sf, tid, patient_id=p, caregiver_user_id=caregiver, capabilities=["create_meal"]
        )
        resp = self._draft(
            c,
            _token(caregiver, tid, ["caregiver"], fid),
            {"patient_id": str(p), "description": "dal"},
        )
        assert resp.status_code == 200

    def test_cg10hb_07_caregiver_without_create_meal_denied(self, db_client):
        c, sf = db_client
        tid, fid, doctor, caregiver, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        seed_caregiver_relationship(
            sf, tid, patient_id=p, caregiver_user_id=caregiver, capabilities=["read_glucose", "read_meal"]
        )
        resp = self._draft(
            c,
            _token(caregiver, tid, ["caregiver"], fid),
            {"patient_id": str(p), "description": "dal"},
        )
        assert resp.status_code == 403

    def test_cg10hb_08_caregiver_deactivated_patient_denied(self, db_client):
        c, sf = db_client
        tid, fid, doctor, caregiver, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR],
            patients=[{"id": p, "active": False}],
        )
        seed_caregiver_relationship(
            sf, tid, patient_id=p, caregiver_user_id=caregiver, capabilities=["create_meal"]
        )
        resp = self._draft(
            c,
            _token(caregiver, tid, ["caregiver"], fid),
            {"patient_id": str(p), "description": "dal"},
        )
        assert resp.status_code == 403

    def test_cg10hb_09_clinician_role_matrix(self, db_client):
        c, sf = db_client
        tid, fid, p = uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, p, facility_id=fid)
        payload = {"patient_id": str(p), "description": "meal"}
        for role in ["nurse", "dietitian", "field_health_worker"]:
            user = uuid4()
            seed_member(sf, tid, user, role=role, facility_id=fid)
            assert self._draft(c, _token(user, tid, [role], fid), payload).status_code == 200
        # care_coordinator and admin/sysop hold no WRITE_MEAL surface.
        for role in ["care_coordinator", "admin", "sysop"]:
            user = uuid4()
            if role == "care_coordinator":
                seed_member(sf, tid, user, role=CareTeamRole.CARE_COORDINATOR, facility_id=fid)
            resp = self._draft(c, _token(user, tid, [role], fid), payload)
            assert resp.status_code == 403

    def test_cg10hb_10_doctor_without_member_denied(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, p, facility_id=fid)
        resp = self._draft(
            c,
            _token(doctor, tid, ["doctor"], fid),
            {"patient_id": str(p), "description": "meal"},
        )
        assert resp.status_code == 403

    def test_cg10hb_11_cross_facility_403(self, db_client):
        c, sf = db_client
        tid, fid_a, fid_b, doctor, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid_a, "A")
        seed_member(sf, tid, doctor, role=CareTeamRole.DOCTOR, facility_id=fid_a)
        seed_facility(sf, tid, fid_b, "B")
        seed_patient(sf, tid, p, facility_id=fid_b)
        resp = self._draft(
            c,
            _token(doctor, tid, ["doctor"], fid_a),
            {"patient_id": str(p), "description": "meal"},
        )
        assert resp.status_code == 403

    def test_cg10hb_12_validation_422_and_katori_enum(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        token = _token(doctor, tid, ["doctor"], fid)
        # Empty description.
        assert self._draft(c, token, {"patient_id": str(p), "description": ""}).status_code == 422
        # Non-canonical katori volume must be schema-rejected (422).
        resp = self._draft(
            c, token,
            {"patient_id": str(p), "description": "meal", "portion": {"food_key": "rice", "katori_volume_ml": 130, "quantity": 1.0}},
        )
        assert resp.status_code == 422
        # Strict schema: unknown field rejected.
        resp = self._draft(c, token, {"patient_id": str(p), "description": "meal", "carbs_grams": 50.0})
        assert resp.status_code == 422

    def test_cg10hb_13_idempotent_replay_and_mismatch(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        token = _token(doctor, tid, ["doctor"], fid)
        payload = {"patient_id": str(p), "description": "dal rice"}
        first = self._draft(c, token, payload, key="meal-001")
        assert first.status_code == 200
        replay = self._draft(c, token, payload, key="meal-001")
        assert replay.status_code == 200
        assert replay.headers.get("idempotent-replayed") == "true"
        assert replay.json() == first.json()
        conflict = self._draft(c, token, {"patient_id": str(p), "description": "different"}, key="meal-001")
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_MISMATCH"


class TestMealConfirmation:

    def _confirm(self, client, token, meal_id, payload=None, key=None):
        headers = bearer(token)
        if key:
            headers["Idempotency-Key"] = key
        return client.post(
            f"/api/v2/clinical/meals/{meal_id}/confirm",
            json=payload if payload is not None else {},
            headers=headers,
        )

    def test_cg10hb_20_clinician_cannot_confirm(self, db_client):
        """Confirmation authority is PATIENT-ONLY; no clinician role holds it."""
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        meal = seed_meal(sf, tid, p)
        resp = self._confirm(c, _token(doctor, tid, ["doctor"], fid), meal.id)
        assert resp.status_code == 403

    def test_cg10hb_21_patient_self_confirms_with_phone(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[])
        _seed_patient_with_phone(sf, tid, p, fid)
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p, active=True)
        meal = seed_meal(sf, tid, p)
        resp = self._confirm(c, _token(patient_user, tid, ["patient"], fid), meal.id)
        assert resp.status_code == 200
        body = resp.json()
        assert body["meal_observation_id"] == str(meal.id)
        assert body["confirmation"] == "confirmed"

    def test_cg10hb_22_patient_self_without_phone_409(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p, active=True)
        meal = seed_meal(sf, tid, p)
        resp = self._confirm(c, _token(patient_user, tid, ["patient"], fid), meal.id)
        assert resp.status_code == 409

    def test_cg10hb_23_patient_cannot_confirm_others_meal(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p_self, p_other = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR],
            patients=[],
        )
        _seed_patient_with_phone(sf, tid, p_self, fid)
        _seed_patient_with_phone(sf, tid, p_other, fid)
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p_self, active=True)
        meal = seed_meal(sf, tid, p_other)
        resp = self._confirm(c, _token(patient_user, tid, ["patient"], fid), meal.id)
        assert resp.status_code == 403

    def test_cg10hb_24_caregiver_denied_confirm(self, db_client):
        c, sf = db_client
        tid, fid, doctor, caregiver, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[])
        _seed_patient_with_phone(sf, tid, p, fid)
        seed_caregiver_relationship(
            sf, tid, patient_id=p, caregiver_user_id=caregiver,
            capabilities=["read_glucose", "read_meal", "create_meal", "read_care_tasks", "complete_care_tasks"],
        )
        meal = seed_meal(sf, tid, p)
        resp = self._confirm(c, _token(caregiver, tid, ["caregiver"], fid), meal.id)
        assert resp.status_code == 403

    def test_cg10hb_25_correction_confirms_as_corrected(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[])
        _seed_patient_with_phone(sf, tid, p, fid)
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p, active=True)
        meal = seed_meal(sf, tid, p)
        resp = self._confirm(
            c,
            _token(patient_user, tid, ["patient"], fid),
            meal.id,
            {"corrected_description": "dal rice with ghee", "corrected_portion": {"food_key": "rice", "katori_volume_ml": 150, "quantity": 1.0}},
        )
        assert resp.status_code == 200
        assert resp.json()["confirmation"] == "corrected"

    def test_cg10hb_26_double_confirm_409_invalid_state(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[])
        _seed_patient_with_phone(sf, tid, p, fid)
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p, active=True)
        meal = seed_meal(sf, tid, p)
        token = _token(patient_user, tid, ["patient"], fid)
        assert self._confirm(c, token, meal.id).status_code == 200
        resp = self._confirm(c, token, meal.id)
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INVALID_STATE"

    def test_cg10hb_27_missing_meal_404_invalid_id_400(self, db_client):
        c, sf = db_client
        tid, fid, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        _seed_patient_with_phone(sf, tid, p, fid)
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p, active=True)
        token = _token(patient_user, tid, ["patient"], fid)
        assert self._confirm(c, token, uuid4()).status_code == 404
        assert self._confirm(c, token, "not-a-uuid").status_code == 400


class TestMedicationAdministration:

    def _record(self, client, token, payload, key=None):
        headers = bearer(token)
        if key:
            headers["Idempotency-Key"] = key
        return client.post("/api/v2/clinical/medication-administrations", json=payload, headers=headers)

    def test_cg10hb_30_patient_self_records_adherence(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[])
        _seed_patient_with_phone(sf, tid, p, fid)
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p, active=True)
        plan = seed_medication_plan(sf, tid, p)
        resp = self._record(
            c,
            _token(patient_user, tid, ["patient"], fid),
            {"medication_plan_id": str(plan.id)},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["medication_plan_id"] == str(plan.id)
        assert body["patient_id"] == str(p)
        assert body["administered_at"] is not None

    def test_cg10hb_31_patient_without_mapping_403(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[])
        _seed_patient_with_phone(sf, tid, p, fid)
        plan = seed_medication_plan(sf, tid, p)
        resp = self._record(
            c,
            _token(patient_user, tid, ["patient"], fid),
            {"medication_plan_id": str(plan.id)},
        )
        assert resp.status_code == 403

    def test_cg10hb_32_doctor_role_denied(self, db_client):
        """Medication administration is a PATIENT adherence event — clinicians
        do not hold WRITE_MEDICATION_ADMINISTRATION (medication authority is
        clinician-only and stays plan-authorship)."""
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[])
        _seed_patient_with_phone(sf, tid, p, fid)
        plan = seed_medication_plan(sf, tid, p)
        resp = self._record(
            c,
            _token(doctor, tid, ["doctor"], fid),
            {"medication_plan_id": str(plan.id)},
        )
        assert resp.status_code == 403

    def test_cg10hb_33_caregiver_without_capability_denied(self, db_client):
        c, sf = db_client
        tid, fid, doctor, caregiver, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[])
        _seed_patient_with_phone(sf, tid, p, fid)
        seed_caregiver_relationship(
            sf, tid, patient_id=p, caregiver_user_id=caregiver, capabilities=["read_meal"]
        )
        plan = seed_medication_plan(sf, tid, p)
        resp = self._record(
            c,
            _token(caregiver, tid, ["caregiver"], fid),
            {"medication_plan_id": str(plan.id)},
        )
        assert resp.status_code == 403

    def test_cg10hb_34_patient_without_phone_409(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p, active=True)
        plan = seed_medication_plan(sf, tid, p)
        resp = self._record(
            c,
            _token(patient_user, tid, ["patient"], fid),
            {"medication_plan_id": str(plan.id)},
        )
        assert resp.status_code == 409

    def test_cg10hb_35_inactive_plan_domain_400(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[])
        _seed_patient_with_phone(sf, tid, p, fid)
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p, active=True)
        plan = seed_medication_plan(sf, tid, p, active=False)
        resp = self._record(
            c,
            _token(patient_user, tid, ["patient"], fid),
            {"medication_plan_id": str(plan.id)},
        )
        assert resp.status_code == 400

    def test_cg10hb_36_patient_cannot_record_for_other_plan(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p_self, p_other = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[])
        _seed_patient_with_phone(sf, tid, p_self, fid)
        _seed_patient_with_phone(sf, tid, p_other, fid)
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p_self, active=True)
        plan_other = seed_medication_plan(sf, tid, p_other)
        resp = self._record(
            c,
            _token(patient_user, tid, ["patient"], fid),
            {"medication_plan_id": str(plan_other.id)},
        )
        assert resp.status_code == 403

    def test_cg10hb_37_missing_plan_404_idempotent_replay(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[])
        _seed_patient_with_phone(sf, tid, p, fid)
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p, active=True)
        token = _token(patient_user, tid, ["patient"], fid)
        assert self._record(c, token, {"medication_plan_id": str(uuid4())}).status_code == 404
        plan = seed_medication_plan(sf, tid, p)
        payload = {"medication_plan_id": str(plan.id)}
        first = self._record(c, token, payload, key="med-001")
        assert first.status_code == 200
        replay = self._record(c, token, payload, key="med-001")
        assert replay.headers.get("idempotent-replayed") == "true"
        assert replay.json() == first.json()


class TestCareTasks:

    def _list(self, client, token, patient_id, **params):
        return client.get("/api/v2/care-tasks", headers=bearer(token), params={"patient_id": str(patient_id), **params})

    def _create(self, client, token, payload, key=None):
        headers = bearer(token)
        if key:
            headers["Idempotency-Key"] = key
        return client.post("/api/v2/care-tasks", json=payload, headers=headers)

    def _complete(self, client, token, task_id, key=None):
        headers = bearer(token)
        if key:
            headers["Idempotency-Key"] = key
        return client.post(f"/api/v2/care-tasks/{task_id}/complete", headers=headers)

    def test_cg10hb_40_doctor_reads_and_creates_tasks(self, db_client):
        c, sf = db_client
        tid, fid, doctor, coord, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid,
            users=[doctor, coord],
            roles=[CareTeamRole.DOCTOR, CareTeamRole.CARE_COORDINATOR],
            patients=[{"id": p}],
        )
        _seed_care_task(sf, tid, p, assigned_to_user_id=coord)
        token = _token(doctor, tid, ["doctor"], fid)
        listing = self._list(c, token, p)
        assert listing.status_code == 200
        body = listing.json()
        assert body["task_count"] == 1
        item = body["items"][0]
        assert set(item.keys()) == {
            "care_task_id", "patient_id", "assigned_to_user_id", "description", "status", "created_at", "completed_at",
        }
        assert item["status"] == "open"

        created = self._create(
            c, token,
            {"patient_id": str(p), "assigned_to_user_id": str(coord), "description": "Daily follow-up"},
        )
        assert created.status_code == 200
        assert created.json()["status"] == "open"
        assert created.json()["assigned_to_user_id"] == str(coord)

    def test_cg10hb_41_list_requires_patient_id(self, client):
        resp = client.get("/api/v2/care-tasks")
        assert resp.status_code in (401, 422)

    def test_cg10hb_42_patient_role_denied_list(self, db_client):
        c, sf = db_client
        tid, fid, doctor, patient_user, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        seed_identity_mapping(sf, tid, user_id=patient_user, patient_id=p, active=True)
        token = _token(patient_user, tid, ["patient"], fid)
        assert self._list(c, token, p).status_code == 403
        assert self._create(
            c, token,
            {"patient_id": str(p), "assigned_to_user_id": str(uuid4()), "description": "x"},
        ).status_code == 403

    def test_cg10hb_43_caregiver_read_task_capability(self, db_client):
        c, sf = db_client
        tid, fid, doctor, caregiver, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        seed_caregiver_relationship(
            sf, tid, patient_id=p, caregiver_user_id=caregiver, capabilities=["read_care_tasks"]
        )
        _seed_care_task(sf, tid, p, assigned_to_user_id=doctor)
        resp = self._list(c, _token(caregiver, tid, ["caregiver"], fid), p)
        assert resp.status_code == 200
        assert resp.json()["task_count"] == 1

    def test_cg10hb_44_caregiver_without_read_capability_denied(self, db_client):
        c, sf = db_client
        tid, fid, doctor, caregiver, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        seed_caregiver_relationship(
            sf, tid, patient_id=p, caregiver_user_id=caregiver, capabilities=["read_glucose"]
        )
        assert self._list(c, _token(caregiver, tid, ["caregiver"], fid), p).status_code == 403

    def test_cg10hb_45_coordinator_and_fhw_workflow(self, db_client):
        c, sf = db_client
        tid, fid, coord, fhw, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid,
            users=[coord, fhw],
            roles=[CareTeamRole.CARE_COORDINATOR, CareTeamRole.FIELD_HEALTH_WORKER],
            patients=[{"id": p}],
        )
        created = self._create(
            c,
            _token(coord, tid, ["care_coordinator"], fid),
            {"patient_id": str(p), "assigned_to_user_id": str(fhw), "description": "Home visit"},
        )
        assert created.status_code == 200
        task_id = created.json()["care_task_id"]
        # FHW can complete tasks but cannot create them.
        fhw_token = _token(fhw, tid, ["field_health_worker"], fid)
        assert fhw_token
        denied_create = self._create(
            c, fhw_token,
            {"patient_id": str(p), "assigned_to_user_id": str(fhw), "description": "x"},
        )
        assert denied_create.status_code == 403
        completed = self._complete(c, fhw_token, task_id)
        assert completed.status_code == 200
        body = completed.json()
        assert body["status"] == "completed"
        assert body["completed_at"] is not None

    def test_cg10hb_46_caregiver_complete_capability(self, db_client):
        c, sf = db_client
        tid, fid, doctor, caregiver, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        seed_caregiver_relationship(
            sf, tid, patient_id=p, caregiver_user_id=caregiver,
            capabilities=["read_care_tasks", "complete_care_tasks"],
        )
        task = _seed_care_task(sf, tid, p, assigned_to_user_id=doctor)
        resp = self._complete(c, _token(caregiver, tid, ["caregiver"], fid), task.id)
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_cg10hb_47_double_complete_409(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        task = _seed_care_task(sf, tid, p, assigned_to_user_id=doctor)
        token = _token(doctor, tid, ["doctor"], fid)
        assert self._complete(c, token, task.id).status_code == 200
        resp = self._complete(c, token, task.id)
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INVALID_STATE"

    def test_cg10hb_48_cross_facility_and_deactivated(self, db_client):
        c, sf = db_client
        tid, fid_a, fid_b, doctor, p_a, p_dead = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid_a, users=[doctor], roles=[CareTeamRole.DOCTOR],
            patients=[{"id": p_a}, {"id": p_dead, "active": False}],
        )
        seed_facility(sf, tid, fid_b, "B")
        seed_patient(sf, tid, p_b := uuid4(), facility_id=fid_b)
        token = _token(doctor, tid, ["doctor"], fid_a)
        assert self._list(c, token, p_b).status_code == 403
        # Deactivated patient invariant on the clinician list path.
        assert self._list(c, token, p_dead).status_code == 403
        # Create for a deactivated patient is denied for clinicians too.
        denied = self._create(
            c, token,
            {"patient_id": str(p_dead), "assigned_to_user_id": str(doctor), "description": "x"},
        )
        assert denied.status_code == 403

    def test_cg10hb_49_missing_task_404_create_idempotent(self, db_client):
        c, sf = db_client
        tid, fid, doctor, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doctor], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        token = _token(doctor, tid, ["doctor"], fid)
        assert self._complete(c, token, uuid4()).status_code == 404
        assert self._create(c, token, {"patient_id": str(p), "assigned_to_user_id": str(doctor), "description": ""}).status_code == 422
        payload = {"patient_id": str(p), "assigned_to_user_id": str(doctor), "description": "Follow-up"}
        first = self._create(c, token, payload, key="task-001")
        assert first.status_code == 200
        replay = self._create(c, token, payload, key="task-001")
        assert replay.headers.get("idempotent-replayed") == "true"
        assert replay.json() == first.json()


class TestPatientProvisioning:

    def _provision(self, client, token, payload, key=None):
        headers = bearer(token)
        if key:
            headers["Idempotency-Key"] = key
        return client.post("/api/v2/patients", json=payload, headers=headers)

    def test_cg10hb_50_admin_provisions_patient(self, db_client):
        c, sf = db_client
        tid, fid, admin = uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        resp = self._provision(
            c,
            _token(admin, tid, ["admin"]),
            {"name": "Provisioned Patient", "facility_id": str(fid), "uh_id": "P-9001", "phone": "+919876543210"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert set(body.keys()) == {"patient_id", "uh_id", "name", "facility_id", "active", "created_at"}
        assert body["uh_id"] == "P-9001"
        assert body["facility_id"] == str(fid)
        assert body["active"] is True

    def test_cg10hb_51_non_admin_roles_denied(self, db_client):
        c, sf = db_client
        tid, fid, user, p = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        seed_patient(sf, tid, p, facility_id=fid)
        seed_member(sf, tid, user, role=CareTeamRole.DOCTOR, facility_id=fid)
        payload = {"name": "X", "facility_id": str(fid)}
        for role in ["doctor", "nurse", "care_coordinator", "patient", "caregiver", "sysop", "field_health_worker"]:
            resp = self._provision(c, _token(uuid4(), tid, [role]), payload)
            assert resp.status_code == 403, role

    def test_cg10hb_52_invalid_uhid_400_strict_schema_422(self, db_client):
        c, sf = db_client
        tid, fid, admin = uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        token = _token(admin, tid, ["admin"])
        bad = self._provision(c, token, {"name": "X", "facility_id": str(fid), "uh_id": "x"})
        assert bad.status_code == 400
        assert bad.json()["error"]["code"] == "DOMAIN_ERROR"
        assert self._provision(c, token, {"name": "", "facility_id": str(fid)}).status_code == 422
        assert self._provision(c, token, {"name": "X", "facility_id": str(fid), "tenant_id": str(uuid4())}).status_code == 422

    def test_cg10hb_53_provisioned_patient_reaches_clinician_cohort(self, db_client):
        """Write+read integration: an admin-provisioned, facility-bound patient
        is immediately visible to a clinician member of that facility."""
        c, sf = db_client
        tid, fid, admin, doctor = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        seed_member(sf, tid, doctor, role=CareTeamRole.DOCTOR, facility_id=fid)
        provisioned = self._provision(
            c,
            _token(admin, tid, ["admin"]),
            {"name": "Cohort Patient", "facility_id": str(fid)},
        )
        assert provisioned.status_code == 201
        patient_id = provisioned.json()["patient_id"]
        cohort = c.get("/api/v2/patients", headers=bearer(_token(doctor, tid, ["doctor"], fid)))
        assert cohort.status_code == 200
        assert {i["patient_id"] for i in cohort.json()["items"]} == {patient_id}

    def test_cg10hb_54_provision_idempotent_replay(self, db_client):
        c, sf = db_client
        tid, fid, admin = uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        token = _token(admin, tid, ["admin"])
        payload = {"name": "Idem Patient", "facility_id": str(fid)}
        first = self._provision(c, token, payload, key="prov-001")
        assert first.status_code == 201
        replay = self._provision(c, token, payload, key="prov-001")
        assert replay.status_code == 201
        assert replay.headers.get("idempotent-replayed") == "true"
        assert replay.json() == first.json()


class TestCareTeamProvisioning:

    def _provision(self, client, token, payload, key=None):
        headers = bearer(token)
        if key:
            headers["Idempotency-Key"] = key
        return client.post("/api/v2/admin/care-team-members", json=payload, headers=headers)

    def test_cg10hb_60_admin_provisions_member(self, db_client):
        c, sf = db_client
        tid, fid, admin = uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        resp = self._provision(
            c,
            _token(admin, tid, ["admin"]),
            {"user_id": str(uuid4()), "role": "nurse", "display_name": "Nurse A", "facility_id": str(fid)},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert set(body.keys()) == {"member_id", "user_id", "role", "display_name", "facility_id", "active"}
        assert body["role"] == "nurse"
        assert body["active"] is True

    def test_cg10hb_61_non_admin_denied(self, db_client):
        c, sf = db_client
        tid, fid = uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        payload = {"user_id": str(uuid4()), "role": "nurse", "display_name": "N", "facility_id": str(fid)}
        for role in ["doctor", "caregiver", "sysop"]:
            resp = self._provision(c, _token(uuid4(), tid, [role]), payload)
            assert resp.status_code == 403, role

    def test_cg10hb_62_invalid_role_422(self, db_client):
        c, sf = db_client
        tid, fid, admin = uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        resp = self._provision(
            c,
            _token(admin, tid, ["admin"]),
            {"user_id": str(uuid4()), "role": "surgeon", "display_name": "N", "facility_id": str(fid)},
        )
        assert resp.status_code == 422

    def test_cg10hb_63_provisioned_member_gets_facility_scope(self, db_client):
        """The member record created by admin provisioning is the SAME
        authoritative membership surface used by the scoping layer."""
        c, sf = db_client
        tid, fid, admin = uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        nurse_user = uuid4()
        resp = self._provision(
            c,
            _token(admin, tid, ["admin"]),
            {"user_id": str(nurse_user), "role": "nurse", "display_name": "Nurse", "facility_id": str(fid)},
        )
        assert resp.status_code == 201
        # The nurse now passes member-facility scoping for a patient read.
        from tests.api.conftest import seed_patient

        p = uuid4()
        seed_patient(sf, tid, p, facility_id=fid)
        cohort = c.get("/api/v2/patients", headers=bearer(_token(nurse_user, tid, ["nurse"], fid)))
        assert cohort.status_code == 200
        assert cohort.json()["patient_count"] == 1

    def test_cg10hb_64_member_provision_idempotent_replay(self, db_client):
        c, sf = db_client
        tid, fid, admin = uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, f"org-{str(tid)[:8]}")
        seed_facility(sf, tid, fid, "F")
        token = _token(admin, tid, ["admin"])
        payload = {"user_id": str(uuid4()), "role": "field_health_worker", "display_name": "FHW", "facility_id": str(fid)}
        first = self._provision(c, token, payload, key="ctm-001")
        assert first.status_code == 201
        replay = self._provision(c, token, payload, key="ctm-001")
        assert replay.status_code == 201
        assert replay.headers.get("idempotent-replayed") == "true"
        assert replay.json() == first.json()