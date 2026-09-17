"""Gate 10J-B — Care Tasks + FHW/Coordinator Depth + Meal Carb Calculator + Target-Stack Demo Seed.

Comprehensive verification of:
10J-B-01: Care task create with due_at persists and returns due_at
10J-B-02: Care task transition open -> in_progress
10J-B-03: Care task transition in_progress -> completed
10J-B-04: Care task invalid transition completed -> in_progress returns 409
10J-B-05: FHW can list own assigned tasks (assigned_to_me=true)
10J-B-06: FHW can start own assigned task
10J-B-07: FHW can complete own assigned task
10J-B-08: FHW cannot start another worker's assigned task (403)
10J-B-09: FHW cannot create care task (403 forbidden)
10J-B-10: Coordinator can list facility-wide tasks
10J-B-11: Coordinator can create care task for patient in facility
10J-B-12: Coordinator can reassign open task to another worker
10J-B-13: Coordinator cannot reassign completed task (409 conflict)
10J-B-14: Doctor can list, create, reassign, complete tasks
10J-B-15: Cross-facility task access blocked (403/404)
10J-B-16: Cross-tenant task access blocked (404/403)
10J-B-17: Deterministic carb calculator: standard food items return expected carbs
10J-B-18: Deterministic carb calculator: katori sizing (150, 220, 350 ml) scales accurately
10J-B-19: Deterministic carb calculator: unknown food raises domain error / 422
10J-B-20: Deterministic carb calculator: negative/zero quantity rejected
10J-B-21: Meal confirm computes carbs/GI for clinician view
10J-B-22: Patient projection strictly omits computed carbs and GI
10J-B-23: Target-stack demo seed creates expected entities
10J-B-24: Target-stack demo seed is idempotent or re-runnable
10J-B-25: Target-stack demo seed verifies multi-facility patient isolation
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from backend.domain.entities import CareTask, CareTaskStatus, CareTeamRole
from backend.domain.exceptions import (
    InvalidKatoriVolume,
    InvalidPortionQuantityError,
    UnknownFoodItemError,
)
from backend.domain.services.carbohydrate_calculator import (
    CarbohydrateCalculator,
    FOOD_CATALOG,
)
from backend.domain.value_objects import KatoriVolume, MealPortion, ReadingTag
from backend.infrastructure.persistence.models.base import Base
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from scripts.seed_target_stack import seed_target_stack
from tests.api.conftest import (
    bearer,
    make_jwt,
    seed_caregiver_relationship,
    seed_facility,
    seed_identity_mapping,
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
    from backend.infrastructure.persistence.models.tenant_models import OrganizationModel

    with sf() as s:
        existing = s.get(OrganizationModel, tenant_id)
        if not existing:
            s.add(OrganizationModel(id=tenant_id, name=f"Org {str(tenant_id)[:8]}", slug=f"org-{str(tenant_id)[:8]}"))
            s.commit()
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
            facility_id=facility_id,
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


def _seed_care_task(
    sf,
    tenant_id,
    patient_id,
    assigned_to_user_id,
    description="Follow up",
    due_at=None,
    status=CareTaskStatus.OPEN,
):
    task = CareTask(
        id=uuid4(),
        patient_id=patient_id,
        assigned_to_user_id=assigned_to_user_id,
        description=description,
        status=status,
        due_at=due_at,
    )
    with SqlAlchemyUnitOfWork(sf, tenant_id) as uow:
        uow.care_tasks.add(task)
        uow.commit()
    return task.id


class TestGate10JBCareTasks:
    """Tests 10J-B-01 through 10J-B-16."""

    def test_10j_b_01_care_task_create_with_due_at_persists_and_returns_due_at(self, db_client):
        c, sf = db_client
        tid, fid, doc, coord, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doc, coord], roles=[CareTeamRole.DOCTOR, CareTeamRole.CARE_COORDINATOR], patients=[{"id": p}])

        due = datetime(2026, 10, 15, 10, 0, 0, tzinfo=timezone.utc)
        payload = {
            "patient_id": str(p),
            "assigned_to_user_id": str(coord),
            "description": "Fasting blood sugar follow-up",
            "due_at": due.isoformat(),
        }
        token = _token(doc, tid, ["doctor"], fid)
        res = c.post("/api/v2/care-tasks", json=payload, headers=bearer(token))
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["due_at"] is not None
        assert data["description"] == "Fasting blood sugar follow-up"
        task_id = data["care_task_id"]

        # Detail retrieval also returns due_at
        detail_res = c.get(f"/api/v2/care-tasks/{task_id}", headers=bearer(token))
        assert detail_res.status_code == 200
        assert detail_res.json()["due_at"] == data["due_at"]

    def test_10j_b_02_care_task_transition_open_to_in_progress(self, db_client):
        c, sf = db_client
        tid, fid, doc, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doc], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        task_id = _seed_care_task(sf, tid, p, doc)

        token = _token(doc, tid, ["doctor"], fid)
        res = c.post(f"/api/v2/care-tasks/{task_id}/start", headers=bearer(token))
        assert res.status_code == 200
        assert res.json()["status"] == "in_progress"

        detail = c.get(f"/api/v2/care-tasks/{task_id}", headers=bearer(token)).json()
        assert detail["status"] == "in_progress"

    def test_10j_b_03_care_task_transition_in_progress_to_completed(self, db_client):
        c, sf = db_client
        tid, fid, doc, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doc], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        task_id = _seed_care_task(sf, tid, p, doc, status=CareTaskStatus.IN_PROGRESS)

        token = _token(doc, tid, ["doctor"], fid)
        res = c.post(f"/api/v2/care-tasks/{task_id}/complete", headers=bearer(token))
        assert res.status_code == 200
        assert res.json()["status"] == "completed"
        assert res.json()["completed_at"] is not None

    def test_10j_b_04_care_task_invalid_transition_completed_to_in_progress_returns_409(self, db_client):
        c, sf = db_client
        tid, fid, doc, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doc], roles=[CareTeamRole.DOCTOR], patients=[{"id": p}])
        task_id = _seed_care_task(sf, tid, p, doc, status=CareTaskStatus.COMPLETED)

        token = _token(doc, tid, ["doctor"], fid)
        res = c.post(f"/api/v2/care-tasks/{task_id}/start", headers=bearer(token))
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "INVALID_STATE"

    def test_10j_b_05_fhw_can_list_own_assigned_tasks(self, db_client):
        c, sf = db_client
        tid, fid, fhw, doc, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[fhw, doc], roles=[CareTeamRole.FIELD_HEALTH_WORKER, CareTeamRole.DOCTOR], patients=[{"id": p}])

        task_fhw = _seed_care_task(sf, tid, p, fhw, description="FHW task")
        task_doc = _seed_care_task(sf, tid, p, doc, description="Doc task")

        token = _token(fhw, tid, ["field_health_worker"], fid)
        res = c.get("/api/v2/care-tasks?assigned_to_me=true", headers=bearer(token))
        assert res.status_code == 200
        body = res.json()
        assert body["task_count"] == 1
        assert body["items"][0]["care_task_id"] == str(task_fhw)
        assert body["items"][0]["description"] == "FHW task"

    def test_10j_b_06_fhw_can_start_own_assigned_task(self, db_client):
        c, sf = db_client
        tid, fid, fhw, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[fhw], roles=[CareTeamRole.FIELD_HEALTH_WORKER], patients=[{"id": p}])
        task_id = _seed_care_task(sf, tid, p, fhw)

        token = _token(fhw, tid, ["field_health_worker"], fid)
        res = c.post(f"/api/v2/care-tasks/{task_id}/start", headers=bearer(token))
        assert res.status_code == 200
        assert res.json()["status"] == "in_progress"

    def test_10j_b_07_fhw_can_complete_own_assigned_task(self, db_client):
        c, sf = db_client
        tid, fid, fhw, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[fhw], roles=[CareTeamRole.FIELD_HEALTH_WORKER], patients=[{"id": p}])
        task_id = _seed_care_task(sf, tid, p, fhw, status=CareTaskStatus.IN_PROGRESS)

        token = _token(fhw, tid, ["field_health_worker"], fid)
        res = c.post(f"/api/v2/care-tasks/{task_id}/complete", headers=bearer(token))
        assert res.status_code == 200
        assert res.json()["status"] == "completed"

    def test_10j_b_08_fhw_cannot_start_another_worker_assigned_task(self, db_client):
        c, sf = db_client
        tid, fid, fhw, doc, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[fhw, doc], roles=[CareTeamRole.FIELD_HEALTH_WORKER, CareTeamRole.DOCTOR], patients=[{"id": p}])
        doc_task = _seed_care_task(sf, tid, p, doc)

        token = _token(fhw, tid, ["field_health_worker"], fid)
        res = c.post(f"/api/v2/care-tasks/{doc_task}/start", headers=bearer(token))
        assert res.status_code == 403

    def test_10j_b_09_fhw_cannot_create_care_task(self, db_client):
        c, sf = db_client
        tid, fid, fhw, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[fhw], roles=[CareTeamRole.FIELD_HEALTH_WORKER], patients=[{"id": p}])

        token = _token(fhw, tid, ["field_health_worker"], fid)
        res = c.post(
            "/api/v2/care-tasks",
            json={"patient_id": str(p), "assigned_to_user_id": str(fhw), "description": "FHW creation attempt"},
            headers=bearer(token),
        )
        assert res.status_code == 403

    def test_10j_b_10_coordinator_can_list_facility_wide_tasks(self, db_client):
        c, sf = db_client
        tid, fid, coord, fhw, doc, p1, p2 = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid,
            users=[coord, fhw, doc],
            roles=[CareTeamRole.CARE_COORDINATOR, CareTeamRole.FIELD_HEALTH_WORKER, CareTeamRole.DOCTOR],
            patients=[{"id": p1}, {"id": p2}],
        )
        _seed_care_task(sf, tid, p1, fhw, description="T1")
        _seed_care_task(sf, tid, p2, doc, description="T2")

        token = _token(coord, tid, ["care_coordinator"], fid)
        res = c.get("/api/v2/care-tasks", headers=bearer(token))
        assert res.status_code == 200
        body = res.json()
        assert body["task_count"] == 2

    def test_10j_b_11_coordinator_can_create_care_task_for_patient_in_facility(self, db_client):
        c, sf = db_client
        tid, fid, coord, fhw, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid,
            users=[coord, fhw],
            roles=[CareTeamRole.CARE_COORDINATOR, CareTeamRole.FIELD_HEALTH_WORKER],
            patients=[{"id": p}],
        )

        token = _token(coord, tid, ["care_coordinator"], fid)
        res = c.post(
            "/api/v2/care-tasks",
            json={"patient_id": str(p), "assigned_to_user_id": str(fhw), "description": "Check vitals"},
            headers=bearer(token),
        )
        assert res.status_code == 200
        assert res.json()["status"] == "open"
        assert res.json()["assigned_to_user_id"] == str(fhw)

    def test_10j_b_12_coordinator_can_reassign_open_task_to_another_worker(self, db_client):
        c, sf = db_client
        tid, fid, coord, fhw, nurse, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid,
            users=[coord, fhw, nurse],
            roles=[CareTeamRole.CARE_COORDINATOR, CareTeamRole.FIELD_HEALTH_WORKER, CareTeamRole.NURSE],
            patients=[{"id": p}],
        )
        task_id = _seed_care_task(sf, tid, p, fhw)

        token = _token(coord, tid, ["care_coordinator"], fid)
        res = c.post(
            f"/api/v2/care-tasks/{task_id}/reassign",
            json={"new_user_id": str(nurse)},
            headers=bearer(token),
        )
        assert res.status_code == 200
        assert res.json()["assigned_to_user_id"] == str(nurse)

        # Verify detail
        detail = c.get(f"/api/v2/care-tasks/{task_id}", headers=bearer(token)).json()
        assert detail["assigned_to_user_id"] == str(nurse)

    def test_10j_b_13_coordinator_cannot_reassign_completed_task(self, db_client):
        c, sf = db_client
        tid, fid, coord, fhw, nurse, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid,
            users=[coord, fhw, nurse],
            roles=[CareTeamRole.CARE_COORDINATOR, CareTeamRole.FIELD_HEALTH_WORKER, CareTeamRole.NURSE],
            patients=[{"id": p}],
        )
        task_id = _seed_care_task(sf, tid, p, fhw, status=CareTaskStatus.COMPLETED)

        token = _token(coord, tid, ["care_coordinator"], fid)
        res = c.post(
            f"/api/v2/care-tasks/{task_id}/reassign",
            json={"new_user_id": str(nurse)},
            headers=bearer(token),
        )
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "INVALID_STATE"

    def test_10j_b_14_doctor_can_list_create_reassign_complete_tasks(self, db_client):
        c, sf = db_client
        tid, fid, doc, nurse, p = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(
            sf, tid, fid,
            users=[doc, nurse],
            roles=[CareTeamRole.DOCTOR, CareTeamRole.NURSE],
            patients=[{"id": p}],
        )
        token = _token(doc, tid, ["doctor"], fid)

        # Create
        created = c.post(
            "/api/v2/care-tasks",
            json={"patient_id": str(p), "assigned_to_user_id": str(doc), "description": "Doctor order"},
            headers=bearer(token),
        )
        assert created.status_code == 200
        task_id = created.json()["care_task_id"]

        # List
        listing = c.get(f"/api/v2/care-tasks?patient_id={p}", headers=bearer(token))
        assert listing.status_code == 200
        assert listing.json()["task_count"] >= 1

        # Reassign
        reassign = c.post(
            f"/api/v2/care-tasks/{task_id}/reassign",
            json={"new_user_id": str(nurse)},
            headers=bearer(token),
        )
        assert reassign.status_code == 200
        assert reassign.json()["assigned_to_user_id"] == str(nurse)

        # Complete
        completed = c.post(f"/api/v2/care-tasks/{task_id}/complete", headers=bearer(token))
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"

    def test_10j_b_15_cross_facility_task_access_blocked(self, db_client):
        c, sf = db_client
        tid, fid_a, fid_b = uuid4(), uuid4(), uuid4()
        doc_a, doc_b, p_b = uuid4(), uuid4(), uuid4()

        _seed_clinic(sf, tid, fid_a, users=[doc_a], roles=[CareTeamRole.DOCTOR])
        _seed_clinic(sf, tid, fid_b, users=[doc_b], roles=[CareTeamRole.DOCTOR], patients=[{"id": p_b}])
        task_b = _seed_care_task(sf, tid, p_b, doc_b)

        token_a = _token(doc_a, tid, ["doctor"], fid_a)
        # Doctor A cannot read task belonging to Facility B patient
        assert c.get(f"/api/v2/care-tasks/{task_b}", headers=bearer(token_a)).status_code == 403
        # Doctor A cannot complete task in Facility B
        assert c.post(f"/api/v2/care-tasks/{task_b}/complete", headers=bearer(token_a)).status_code == 403

    def test_10j_b_16_cross_tenant_task_access_blocked(self, db_client):
        c, sf = db_client
        tid_a, fid_a, doc_a, p_a = uuid4(), uuid4(), uuid4(), uuid4()
        tid_b, fid_b, doc_b = uuid4(), uuid4(), uuid4()

        _seed_clinic(sf, tid_a, fid_a, users=[doc_a], roles=[CareTeamRole.DOCTOR], patients=[{"id": p_a}])
        _seed_clinic(sf, tid_b, fid_b, users=[doc_b], roles=[CareTeamRole.DOCTOR])
        task_a = _seed_care_task(sf, tid_a, p_a, doc_a)

        token_b = _token(doc_b, tid_b, ["doctor"], fid_b)
        # Doctor in Tenant B cannot find or access task in Tenant A
        res = c.get(f"/api/v2/care-tasks/{task_a}", headers=bearer(token_b))
        assert res.status_code == 404


class TestGate10JBDeterministicCarbCalculator:
    """Tests 10J-B-17 through 10J-B-22."""

    def test_10j_b_17_deterministic_carb_calculator_standard_food_items(self):
        calc = CarbohydrateCalculator()
        # White rice: 28.0 g/100g, GI high
        # 1 medium katori (220 ml) = round(28.0 * 220 * 1.0 * 0.009, 1) = 55.4
        res_rice = calc.calculate("white rice", volume_ml=220, quantity=1.0)
        assert res_rice.carbs_grams == 55.4
        assert res_rice.glycemic_index == "high"

        # Dal: 15.0 g/100g, GI low
        # 1 medium katori = round(15.0 * 220 * 1.0 * 0.009, 1) = 29.7
        res_dal = calc.calculate("dal", volume_ml=220, quantity=1.0)
        assert res_dal.carbs_grams == 29.7
        assert res_dal.glycemic_index == "low"

        # Colloquial alias "roti": 24.0 g/100g, GI med
        res_roti = calc.calculate("roti", volume_ml=150, quantity=1.0)
        assert res_roti.carbs_grams == 32.4
        assert res_roti.glycemic_index == "med"

    def test_10j_b_18_deterministic_carb_calculator_katori_sizing_scales_accurately(self):
        calc = CarbohydrateCalculator()
        # Roti: 24.0 g/100g
        # Small (150 ml)
        r_small = calc.calculate("roti", volume_ml=150, quantity=1.0)
        assert r_small.carbs_grams == 32.4  # round(24.0 * 150 * 0.009, 1)

        # Medium (220 ml)
        r_med = calc.calculate("roti", volume_ml=220, quantity=1.0)
        assert r_med.carbs_grams == 47.5   # round(24.0 * 220 * 0.009, 1)

        # Large (350 ml)
        r_large = calc.calculate("roti", volume_ml=350, quantity=1.0)
        assert r_large.carbs_grams == 75.6  # round(24.0 * 350 * 0.009, 1)

        # Quantity scaling: 2.5 rotis in Small katori
        r_multi = calc.calculate("roti", volume_ml=150, quantity=2.5)
        assert r_multi.carbs_grams == 81.0  # round(24.0 * 150 * 2.5 * 0.009, 1)

    def test_10j_b_19_deterministic_carb_calculator_unknown_food_raises_domain_error(self):
        calc = CarbohydrateCalculator()
        with pytest.raises(UnknownFoodItemError):
            calc.calculate("completely_unknown_staple_xyz", volume_ml=220)

    def test_10j_b_20_deterministic_carb_calculator_negative_or_zero_quantity_rejected(self):
        calc = CarbohydrateCalculator()
        with pytest.raises(InvalidPortionQuantityError):
            calc.calculate("roti", volume_ml=220, quantity=0.0)

        with pytest.raises(InvalidPortionQuantityError):
            calc.calculate("roti", volume_ml=220, quantity=-2.0)

    def test_10j_b_21_meal_confirm_computes_carbs_and_gi_for_clinician_view(self, db_client):
        c, sf = db_client
        tid, fid, doc, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doc], roles=[CareTeamRole.DOCTOR])
        _seed_patient_with_phone(sf, tid, p, fid, phone="+919876543210")
        seed_identity_mapping(sf, tid, user_id=p, patient_id=p, active=True)

        patient_token = _token(p, tid, ["patient"], fid)
        doc_token = _token(doc, tid, ["doctor"], fid)

        # Patient drafts meal with portion (roti, 220ml, 1.0)
        draft = c.post(
            "/api/v2/clinical/meals",
            json={
                "patient_id": str(p),
                "description": "1 roti",
                "portion": {"food_key": "roti", "katori_volume_ml": 220, "quantity": 1.0},
            },
            headers=bearer(patient_token),
        )
        assert draft.status_code == 200
        meal_id = draft.json()["meal_observation_id"]

        # Patient confirms meal
        confirm = c.post(
            f"/api/v2/clinical/meals/{meal_id}/confirm",
            json={},
            headers=bearer(patient_token),
        )
        assert confirm.status_code == 200

        # Clinician reads clinical observation feed
        clinician_feed = c.get(
            f"/api/v2/clinical/clinical-observations?patient_id={p}",
            headers=bearer(doc_token),
        )
        assert clinician_feed.status_code == 200
        items = clinician_feed.json()["items"]
        assert len(items) == 1
        meal_item = items[0]
        assert meal_item["kind"] == "meal"
        assert meal_item["carbs_grams"] == 47.5
        assert meal_item["glycemic_index"] == "med"

    def test_10j_b_22_patient_projection_strictly_omits_computed_carbs_and_gi(self, db_client):
        c, sf = db_client
        tid, fid, doc, p = uuid4(), uuid4(), uuid4(), uuid4()
        _seed_clinic(sf, tid, fid, users=[doc], roles=[CareTeamRole.DOCTOR])
        _seed_patient_with_phone(sf, tid, p, fid, phone="+919876543210")
        seed_identity_mapping(sf, tid, user_id=p, patient_id=p, active=True)

        patient_token = _token(p, tid, ["patient"], fid)

        # Draft and confirm
        draft = c.post(
            "/api/v2/clinical/meals",
            json={
                "patient_id": str(p),
                "description": "1 bowl dal",
                "portion": {"food_key": "dal", "katori_volume_ml": 220, "quantity": 1.0},
            },
            headers=bearer(patient_token),
        )
        meal_id = draft.json()["meal_observation_id"]
        c.post(f"/api/v2/clinical/meals/{meal_id}/confirm", json={}, headers=bearer(patient_token))

        # Patient reads patient observation feed
        patient_feed = c.get(
            f"/api/v2/clinical/observations?patient_id={p}",
            headers=bearer(patient_token),
        )
        assert patient_feed.status_code == 200
        items = patient_feed.json()["items"]
        assert len(items) == 1
        item = items[0]
        # Verify patient projection fields
        assert item["description"] == "1 bowl dal"
        assert item["portion_label"] == "medium"
        assert item["quantity"] == 1.0
        assert item["confirmed"] is True
        # Asymmetry invariant: strictly forbidden to leak carbs_grams or glycemic_index
        assert "carbs_grams" not in item
        assert "glycemic_index" not in item


class TestGate10JBTargetStackDemoSeed:
    """Tests 10J-B-23 through 10J-B-25."""

    def test_10j_b_23_target_stack_demo_seed_creates_expected_entities(self, db_session_factory):
        with db_session_factory() as session:
            summary = seed_target_stack(session)

            assert summary["tenant_id"] is not None
            assert summary["facility_a_id"] is not None
            assert summary["facility_b_id"] is not None
            assert len(summary["workforce"]) == 6
            assert len(summary["patients"]) == 4
            assert len(summary["tasks"]) == 4
            assert len(summary["glucose"]) == 2
            assert len(summary["meals"]) == 2

    def test_10j_b_24_target_stack_demo_seed_is_idempotent(self, db_session_factory):
        with db_session_factory() as session:
            # First seed run
            s1 = seed_target_stack(session)
            # Second seed run must complete without errors
            s2 = seed_target_stack(session)

            assert s1["tenant_id"] == s2["tenant_id"]
            assert len(s1["tasks"]) == len(s2["tasks"])
            assert len(s1["patients"]) == len(s2["patients"])

    def test_10j_b_25_target_stack_demo_seed_verifies_multi_facility_isolation(self, db_client):
        c, sf = db_client
        with sf() as session:
            summary = seed_target_stack(session)

        tid = summary["tenant_id"]
        fid_a = summary["facility_a_id"]
        fid_b = summary["facility_b_id"]
        doc_a = summary["workforce"]["doctor"]
        doc_b = summary["workforce"]["doctor_b"]
        p1_a = summary["patients"]["active_p1"]
        p4_b = summary["patients"]["facility_b_p4"]

        token_a = _token(doc_a, tid, ["doctor"], fid_a)
        token_b = _token(doc_b, tid, ["doctor"], fid_b)

        # Doctor A in Facility A can read Patient 1 (Facility A)
        res_a1 = c.get(f"/api/v2/patients/{p1_a}", headers=bearer(token_a))
        assert res_a1.status_code == 200

        # Doctor A in Facility A CANNOT read Patient 4 (Facility B) -> 403 Forbidden
        res_a4 = c.get(f"/api/v2/patients/{p4_b}", headers=bearer(token_a))
        assert res_a4.status_code == 403

        # Doctor B in Facility B can read Patient 4 (Facility B)
        res_b4 = c.get(f"/api/v2/patients/{p4_b}", headers=bearer(token_b))
        assert res_b4.status_code == 200

        # Doctor B in Facility B CANNOT read Patient 1 (Facility A) -> 403 Forbidden
        res_b1 = c.get(f"/api/v2/patients/{p1_a}", headers=bearer(token_b))
        assert res_b1.status_code == 403
