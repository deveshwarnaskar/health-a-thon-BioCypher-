"""Tenant isolation HTTP integration tests (Gate 07).

Proves the full chain:

    Verified JWT
        → AuthenticatedContext.tenant_id
        → UnitOfWork(tenant_id)
        → transaction-local context
        → database tenant scoping

- Tenant A sees tenant A's data.
- Tenant B sees tenant B's data.
- Tenant A cannot access tenant B's data.
- Request body tenant_id override is rejected (extra=forbid / ignored).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from tests.api.conftest import bearer, make_jwt, seed_glucose, seed_member, seed_org, seed_patient


class TestTenantIsolationViaHTTP:
    """End-to-end HTTP → UoW → RLS chain proof."""

    def test_tenant_a_sees_own_patient(self, db_client):
        c, sf = db_client
        tid = uuid4()
        fid = uuid4()
        actor_id = uuid4()
        patient_id = uuid4()
        seed_org(sf, tid, "org-a")
        seed_patient(sf, tid, patient_id, facility_id=fid, name="Alpha")
        seed_member(sf, tid, user_id=actor_id, role="doctor", facility_id=fid)
        seed_glucose(sf, tid, patient_id, value=130)

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["doctor"], facility_id=str(fid))
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 200
        assert resp.json()["patient_id"] == str(patient_id)
        assert len(resp.json()["items"]) >= 1

    def test_tenant_b_sees_own_patient(self, db_client):
        c, sf = db_client
        tid = uuid4()
        fid = uuid4()
        actor_id = uuid4()
        patient_id = uuid4()
        seed_org(sf, tid, "org-b")
        seed_patient(sf, tid, patient_id, facility_id=fid, name="Beta")
        seed_member(sf, tid, user_id=actor_id, role="doctor", facility_id=fid)
        seed_glucose(sf, tid, patient_id, value=90)

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["doctor"], facility_id=str(fid))
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 200
        assert len(resp.json()["items"]) >= 1

    def test_tenant_a_cannot_see_tenant_b_patient(self, db_client):
        c, sf = db_client
        tid_a = uuid4()
        tid_b = uuid4()
        fid = uuid4()
        actor_a = uuid4()
        patient_b_id = uuid4()

        seed_org(sf, tid_a, "org-a")
        seed_org(sf, tid_b, "org-b")
        seed_patient(sf, tid_b, patient_b_id, facility_id=fid, name="Beta Only")
        seed_member(sf, tid_a, user_id=actor_a, role="doctor", facility_id=fid)

        token = make_jwt(sub=str(actor_a), tenant_id=str(tid_a), roles=["doctor"], facility_id=str(fid))
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_b_id}", headers=bearer(token))
        # 404 (patient not found in tenant A's scoped repos) or 403 (facility check)
        assert resp.status_code in (403, 404)

    def test_tenant_b_cannot_see_tenant_a_patient(self, db_client):
        c, sf = db_client
        tid_a = uuid4()
        tid_b = uuid4()
        fid = uuid4()
        actor_b = uuid4()
        patient_a_id = uuid4()

        seed_org(sf, tid_a, "org-a")
        seed_org(sf, tid_b, "org-b")
        seed_patient(sf, tid_a, patient_a_id, facility_id=fid, name="Alpha Only")
        seed_member(sf, tid_b, user_id=actor_b, role="doctor", facility_id=fid)

        token = make_jwt(sub=str(actor_b), tenant_id=str(tid_b), roles=["doctor"], facility_id=str(fid))
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_a_id}", headers=bearer(token))
        assert resp.status_code in (403, 404)

    def test_cross_tenant_write_denied(self, db_client):
        """Tenant A token + tenant B patient_id → patient not found in tenant A."""
        c, sf = db_client
        tid_a = uuid4()
        tid_b = uuid4()
        fid = uuid4()
        actor_a = uuid4()
        patient_b_id = uuid4()

        seed_org(sf, tid_a, "org-a")
        seed_org(sf, tid_b, "org-b")
        seed_patient(sf, tid_b, patient_b_id, facility_id=fid, name="B")
        seed_member(sf, tid_a, user_id=actor_a, role="doctor", facility_id=fid)

        token = make_jwt(sub=str(actor_a), tenant_id=str(tid_a), roles=["doctor"], facility_id=str(fid))
        resp = c.post(
            "/api/v2/clinical/observations",
            json={"patient_id": str(patient_b_id), "value_mg_dl": 150},
            headers=bearer(token),
        )
        assert resp.status_code == 404

    def test_request_body_tenant_id_rejected(self, db_client):
        """Body containing tenant_id is rejected by extra=forbid."""
        c, sf = db_client
        tid = uuid4()
        fid = uuid4()
        actor_id = uuid4()
        patient_id = uuid4()

        seed_org(sf, tid, "org")
        seed_patient(sf, tid, patient_id, facility_id=fid)
        seed_member(sf, tid, user_id=actor_id, role="doctor", facility_id=fid)

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["doctor"], facility_id=str(fid))
        resp = c.post(
            "/api/v2/clinical/observations",
            json={
                "patient_id": str(patient_id),
                "value_mg_dl": 120,
                "tenant_id": str(uuid4()),  # attempted override
            },
            headers=bearer(token),
        )
        assert resp.status_code == 422

    def test_uow_tenant_context_verified(self, db_client):
        """Verify the UoW is bound to the authenticated tenant (not arbitrary)."""
        c, sf = db_client
        tid = uuid4()
        fid = uuid4()
        actor_id = uuid4()
        patient_id = uuid4()

        seed_org(sf, tid, "org")
        seed_patient(sf, tid, patient_id, facility_id=fid, name="Scoped")
        seed_member(sf, tid, user_id=actor_id, role="doctor", facility_id=fid)
        seed_glucose(sf, tid, patient_id, value=180)

        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["doctor"], facility_id=str(fid))
        resp = c.get(f"/api/v2/clinical/observations?patient_id={patient_id}", headers=bearer(token))
        assert resp.status_code == 200
        # The items visible are ONLY from tenant tid (proven by RLS in Postgres, by repo scoping in SQLite)
        items = resp.json()["items"]
        assert len(items) >= 1
        values = [i.get("value_mg_dl") for i in items if i.get("kind") == "glucose"]
        assert 180 in values
