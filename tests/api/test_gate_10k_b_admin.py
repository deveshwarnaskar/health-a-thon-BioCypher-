"""Gate 10K-B — Admin Backend Control Plane + RLS Repair tests.

Comprehensive test suite covering:
1. PostgreSQL Facilities Row Level Security (RLS):
   - Tenant A cannot read Tenant B facilities.
   - Tenant A cannot update Tenant B facilities.
   - Tenant A cannot deactivate Tenant B facilities.
   - Tenant A cannot create a facility using Tenant B tenant_id (WITH CHECK prevents tenant spoofing).
   - Care team member unique constraint (tenant_id, user_id).
2. Facility Administration:
   - Create, list, detail, update, deactivate lifecycle.
   - Tenant isolation & cross-tenant denial.
   - Input validation.
3. Care-Team Administration:
   - Provision, list, detail, update, deactivate lifecycle.
   - Unique constraint enforcement (duplicate user in tenant -> 409).
   - Invalid role literal validation (422).
   - Facility scoping & cross-tenant denial.
4. Patient Cohort Inspection & Lifecycle (Admin):
   - Admin list and detail.
   - Safe deactivation.
   - Strict PHI minimization (zero clinical fields: carbs, glucose, meal, medication, AI, risk).
   - Cross-tenant denial.
5. Identity Mapping Audit Fix:
   - Deactivation records audit event in audit_events.
6. Audit Filtering:
   - start_time, end_time, resource_type query parameters.
7. RBAC Enforcement:
   - Admin allowed administrative endpoints.
   - Clinicians, caregivers, patients denied administrative endpoints (403).
   - Admin denied clinical authority (observations, medication plans, AI review).
8. Idempotency:
   - Idempotency-Key replaying returns replayed responses on mutations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.domain.entities import CareTeamRole
from backend.infrastructure.config.database import create_db_engine
from backend.infrastructure.persistence.models import FacilityModel, OrganizationModel
from backend.infrastructure.persistence.models.clinician_models import CareTeamMemberModel
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from tests.api.conftest import (
    bearer,
    make_jwt,
    seed_facility,
    seed_glucose,
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


# =============================================================================
# 1. PostgreSQL Facilities Row Level Security (RLS)
# =============================================================================


@pytest.fixture(scope="module")
def postgres_db():
    import psycopg

    db_name = f"thali_gate10k_{uuid4().hex[:8]}"
    try:
        with psycopg.connect("dbname=postgres", autocommit=True, connect_timeout=1) as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE {db_name};")
    except Exception:
        pytest.skip("Local PostgreSQL not accessible for Gate 10K-B RLS testing")

    pg_url = f"postgresql+psycopg://@localhost:5432/{db_name}"
    engine = create_db_engine(pg_url)

    with engine.connect() as conn:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.attributes["connection"] = conn
        command.upgrade(alembic_cfg, "head")
        conn.execute(
            text(
                """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'thali_app_test_role') THEN
                    CREATE ROLE thali_app_test_role WITH NOSUPERUSER NOBYPASSRLS;
                END IF;
            END
            $$;
            GRANT USAGE ON SCHEMA public TO thali_app_test_role;
            GRANT ALL ON ALL TABLES IN SCHEMA public TO thali_app_test_role;
            """
            )
        )
        conn.commit()

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    yield session_factory, engine

    engine.dispose()
    with psycopg.connect("dbname=postgres", autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE);")


class TestFacilitiesRLSPostgres:
    def test_facilities_rls_tenant_isolation(self, postgres_db):
        session_factory, engine = postgres_db
        tenant_a = uuid4()
        tenant_b = uuid4()
        fac_a_id = uuid4()
        fac_b_id = uuid4()

        # Seed organizations using unprivileged test role
        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(
                text("INSERT INTO organizations (id, name, slug, created_at) VALUES (:id_a, 'Org A', :slug_a, NOW()), (:id_b, 'Org B', :slug_b, NOW());"),
                {"id_a": tenant_a, "slug_a": f"org-{tenant_a.hex[:8]}", "id_b": tenant_b, "slug_b": f"org-{tenant_b.hex[:8]}"},
            )
            # Insert Facility A under Tenant A context
            conn.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_a}';"))
            conn.execute(
                text("INSERT INTO facilities (id, tenant_id, name, active, created_at) VALUES (:id, :tid, 'Facility A', true, NOW());"),
                {"id": fac_a_id, "tid": tenant_a},
            )
            # Insert Facility B under Tenant B context
            conn.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_b}';"))
            conn.execute(
                text("INSERT INTO facilities (id, tenant_id, name, active, created_at) VALUES (:id, :tid, 'Facility B', true, NOW());"),
                {"id": fac_b_id, "tid": tenant_b},
            )
            conn.commit()

        # Verify Tenant A sees ONLY Facility A
        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_a}';"))
            rows = conn.execute(text("SELECT id, name FROM facilities;")).fetchall()
            ids = [r[0] for r in rows]
            assert fac_a_id in ids
            assert fac_b_id not in ids

        # Verify Tenant B sees ONLY Facility B
        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_b}';"))
            rows = conn.execute(text("SELECT id, name FROM facilities;")).fetchall()
            ids = [r[0] for r in rows]
            assert fac_b_id in ids
            assert fac_a_id not in ids

        # Verify missing tenant context returns 0 rows (fail-closed)
        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(text("RESET app.current_tenant_id;"))
            rows = conn.execute(text("SELECT id, name FROM facilities;")).fetchall()
            assert len(rows) == 0

    def test_facilities_rls_cross_tenant_update_and_delete_denied(self, postgres_db):
        session_factory, engine = postgres_db
        tenant_a = uuid4()
        tenant_b = uuid4()
        fac_a_id = uuid4()

        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(
                text("INSERT INTO organizations (id, name, slug, created_at) VALUES (:id_a, 'Org A2', :slug_a, NOW()), (:id_b, 'Org B2', :slug_b, NOW());"),
                {"id_a": tenant_a, "slug_a": f"org-{tenant_a.hex[:8]}", "id_b": tenant_b, "slug_b": f"org-{tenant_b.hex[:8]}"},
            )
            conn.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_a}';"))
            conn.execute(
                text("INSERT INTO facilities (id, tenant_id, name, active, created_at) VALUES (:id, :tid, 'Facility Orig', true, NOW());"),
                {"id": fac_a_id, "tid": tenant_a},
            )
            conn.commit()

        # Tenant B attempts UPDATE on Facility A -> affects 0 rows
        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_b}';"))
            res = conn.execute(
                text("UPDATE facilities SET name = 'Hacked' WHERE id = :id;"),
                {"id": fac_a_id},
            )
            assert res.rowcount == 0

        # Tenant B attempts DELETE on Facility A -> affects 0 rows
        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_b}';"))
            res = conn.execute(
                text("DELETE FROM facilities WHERE id = :id;"),
                {"id": fac_a_id},
            )
            assert res.rowcount == 0

        # Verify Facility A unchanged under Tenant A
        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_a}';"))
            row = conn.execute(
                text("SELECT name, active FROM facilities WHERE id = :id;"),
                {"id": fac_a_id},
            ).fetchone()
            assert row[0] == "Facility Orig"

    def test_facilities_rls_with_check_prevents_tenant_spoofing(self, postgres_db):
        session_factory, engine = postgres_db
        tenant_a = uuid4()
        tenant_b = uuid4()
        spoofed_fac_id = uuid4()

        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(
                text("INSERT INTO organizations (id, name, slug, created_at) VALUES (:id_a, 'Org A3', :slug_a, NOW()), (:id_b, 'Org B3', :slug_b, NOW());"),
                {"id_a": tenant_a, "slug_a": f"org-{tenant_a.hex[:8]}", "id_b": tenant_b, "slug_b": f"org-{tenant_b.hex[:8]}"},
            )
            conn.commit()

        # Tenant A tries to insert a facility with tenant_id = Tenant B
        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_a}';"))
            with pytest.raises(Exception) as exc_info:
                conn.execute(
                    text("INSERT INTO facilities (id, tenant_id, name, active, created_at) VALUES (:id, :tid, 'Spoofed', true, NOW());"),
                    {"id": spoofed_fac_id, "tid": tenant_b},
                )
                conn.commit()
            assert "violates row-level security policy" in str(exc_info.value).lower()

    def test_care_team_member_uniqueness_constraint_postgres(self, postgres_db):
        session_factory, engine = postgres_db
        tenant_a = uuid4()
        tenant_b = uuid4()
        user_id = uuid4()
        fac_a_id = uuid4()

        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(
                text("INSERT INTO organizations (id, name, slug, created_at) VALUES (:id_a, 'Org A4', :slug_a, NOW()), (:id_b, 'Org B4', :slug_b, NOW());"),
                {"id_a": tenant_a, "slug_a": f"org-{tenant_a.hex[:8]}", "id_b": tenant_b, "slug_b": f"org-{tenant_b.hex[:8]}"},
            )
            conn.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_a}';"))
            conn.execute(
                text("INSERT INTO facilities (id, tenant_id, name, active, created_at) VALUES (:id, :tid, 'Fac A4', true, NOW());"),
                {"id": fac_a_id, "tid": tenant_a},
            )
            # Insert first care team member for user_id under Tenant A
            conn.execute(
                text("INSERT INTO care_team_members (id, tenant_id, user_id, role, display_name, facility_id, active, created_at) "
                     "VALUES (:id, :tid, :uid, 'nurse', 'Nurse One', :fid, true, NOW());"),
                {"id": uuid4(), "tid": tenant_a, "uid": user_id, "fid": fac_a_id},
            )
            conn.commit()

        # Inserting second care team member for SAME user_id under Tenant A must violate unique constraint
        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_a}';"))
            with pytest.raises(Exception) as exc_info:
                conn.execute(
                    text("INSERT INTO care_team_members (id, tenant_id, user_id, role, display_name, facility_id, active, created_at) "
                         "VALUES (:id, :tid, :uid, 'doctor', 'Doctor Duplicate', :fid, true, NOW());"),
                    {"id": uuid4(), "tid": tenant_a, "uid": user_id, "fid": fac_a_id},
                )
                conn.commit()
            err_str = str(exc_info.value).lower()
            assert "unique constraint" in err_str or "duplicate key" in err_str or "uq_care_team_members_tenant_user" in err_str

        # Same user_id under DIFFERENT tenant (Tenant B) must succeed
        with engine.connect() as conn:
            conn.execute(text("SET ROLE thali_app_test_role;"))
            conn.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_b}';"))
            conn.execute(
                text("INSERT INTO care_team_members (id, tenant_id, user_id, role, display_name, active, created_at) "
                     "VALUES (:id, :tid, :uid, 'doctor', 'Dr B', true, NOW());"),
                {"id": uuid4(), "tid": tenant_b, "uid": user_id},
            )
            conn.commit()


# =============================================================================
# 2. Facility Administration (HTTP API)
# =============================================================================


class TestFacilityAdministration:
    def test_facility_crud_lifecycle(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        seed_org(sf, tenant_id, "admin-fac-org")

        headers = bearer(_token(admin_id, tenant_id, ["admin"]))

        # 1. Create facility
        create_res = client.post(
            "/api/v2/admin/facilities",
            headers=headers,
            json={"name": "Koramangala Community Clinic"},
        )
        assert create_res.status_code == 201
        data = create_res.json()
        fac_id = data["facility_id"]
        assert data["name"] == "Koramangala Community Clinic"
        assert data["active"] is True
        assert "created_at" in data

        # 2. List facilities
        list_res = client.get("/api/v2/admin/facilities", headers=headers)
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total"] >= 1
        fac_names = [f["name"] for f in list_data["items"]]
        assert "Koramangala Community Clinic" in fac_names

        # 3. Get single facility
        get_res = client.get(f"/api/v2/admin/facilities/{fac_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Koramangala Community Clinic"

        # 4. Update facility
        patch_res = client.patch(
            f"/api/v2/admin/facilities/{fac_id}",
            headers=headers,
            json={"name": "Koramangala Main Center"},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["name"] == "Koramangala Main Center"

        # 5. Deactivate facility
        deact_res = client.post(
            f"/api/v2/admin/facilities/{fac_id}/deactivate",
            headers=headers,
        )
        assert deact_res.status_code == 200
        assert deact_res.json()["active"] is False

        # Confirm inactive in detail
        get_after = client.get(f"/api/v2/admin/facilities/{fac_id}", headers=headers)
        assert get_after.status_code == 200
        assert get_after.json()["active"] is False

    def test_facility_cross_tenant_isolation(self, db_client):
        client, sf = db_client
        tenant_a = uuid4()
        tenant_b = uuid4()
        admin_a = uuid4()
        admin_b = uuid4()
        fac_a = uuid4()

        seed_org(sf, tenant_a, "fac-tenant-a")
        seed_org(sf, tenant_b, "fac-tenant-b")
        seed_facility(sf, tenant_a, fac_a, "Facility In Tenant A")

        headers_b = bearer(_token(admin_b, tenant_b, ["admin"]))

        # Tenant B cannot read Facility A
        res_get = client.get(f"/api/v2/admin/facilities/{fac_a}", headers=headers_b)
        assert res_get.status_code == 404

        # Tenant B cannot update Facility A
        res_patch = client.patch(
            f"/api/v2/admin/facilities/{fac_a}",
            headers=headers_b,
            json={"name": "Hacked Name"},
        )
        assert res_patch.status_code == 404

        # Tenant B cannot deactivate Facility A
        res_deact = client.post(
            f"/api/v2/admin/facilities/{fac_a}/deactivate",
            headers=headers_b,
        )
        assert res_deact.status_code == 404

        # Tenant B list does not contain Facility A
        list_res = client.get("/api/v2/admin/facilities", headers=headers_b)
        assert list_res.status_code == 200
        fac_ids = [f["facility_id"] for f in list_res.json()["items"]]
        assert str(fac_a) not in fac_ids

    def test_facility_input_validation(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        seed_org(sf, tenant_id, "fac-val-org")
        headers = bearer(_token(admin_id, tenant_id, ["admin"]))

        # Empty name -> 422
        res_empty = client.post(
            "/api/v2/admin/facilities",
            headers=headers,
            json={"name": ""},
        )
        assert res_empty.status_code == 422

        # Invalid UUID -> 400
        res_bad_id = client.get("/api/v2/admin/facilities/not-a-uuid", headers=headers)
        assert res_bad_id.status_code == 400


# =============================================================================
# 3. Care-Team Administration (HTTP API)
# =============================================================================


class TestCareTeamAdministration:
    def test_care_team_crud_lifecycle(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        fac_id = uuid4()
        user_id = uuid4()

        seed_org(sf, tenant_id, "ct-admin-org")
        seed_facility(sf, tenant_id, fac_id, "Clinic Center")

        headers = bearer(_token(admin_id, tenant_id, ["admin"]))

        # 1. Provision care-team member
        prov_res = client.post(
            "/api/v2/admin/care-team-members",
            headers=headers,
            json={
                "user_id": str(user_id),
                "role": "nurse",
                "display_name": "Nurse Joy",
                "facility_id": str(fac_id),
            },
        )
        assert prov_res.status_code == 201
        data = prov_res.json()
        member_id = data["member_id"]
        assert data["user_id"] == str(user_id)
        assert data["role"] == "nurse"
        assert data["display_name"] == "Nurse Joy"
        assert data["facility_id"] == str(fac_id)
        assert data["active"] is True

        # 2. List care-team members
        list_res = client.get("/api/v2/admin/care-team-members", headers=headers)
        assert list_res.status_code == 200
        members = list_res.json()["items"]
        assert any(m["member_id"] == member_id for m in members)

        # 3. Filter care-team members by role
        filter_role = client.get(
            "/api/v2/admin/care-team-members?role=nurse",
            headers=headers,
        )
        assert filter_role.status_code == 200
        assert len(filter_role.json()["items"]) >= 1

        filter_wrong_role = client.get(
            "/api/v2/admin/care-team-members?role=doctor",
            headers=headers,
        )
        assert filter_wrong_role.status_code == 200
        assert not any(m["member_id"] == member_id for m in filter_wrong_role.json()["items"])

        # 4. Detail
        detail_res = client.get(f"/api/v2/admin/care-team-members/{member_id}", headers=headers)
        assert detail_res.status_code == 200
        assert detail_res.json()["display_name"] == "Nurse Joy"

        # 5. Update (role & display_name)
        patch_res = client.patch(
            f"/api/v2/admin/care-team-members/{member_id}",
            headers=headers,
            json={
                "role": "care_coordinator",
                "display_name": "Coordinator Joy",
            },
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["role"] == "care_coordinator"
        assert patch_res.json()["display_name"] == "Coordinator Joy"

        # 6. Deactivate
        deact_res = client.post(
            f"/api/v2/admin/care-team-members/{member_id}/deactivate",
            headers=headers,
        )
        assert deact_res.status_code == 200
        assert deact_res.json()["active"] is False

    def test_care_team_unique_constraint_enforcement(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        fac_id = uuid4()
        user_id = uuid4()

        seed_org(sf, tenant_id, "ct-uniq-org")
        seed_facility(sf, tenant_id, fac_id, "Facility U")
        headers = bearer(_token(admin_id, tenant_id, ["admin"]))

        # First provision succeeds
        res1 = client.post(
            "/api/v2/admin/care-team-members",
            headers=headers,
            json={
                "user_id": str(user_id),
                "role": "doctor",
                "display_name": "Dr. Primary",
                "facility_id": str(fac_id),
            },
        )
        assert res1.status_code == 201

        # Second provision with same user_id in same tenant -> 409 Conflict
        res2 = client.post(
            "/api/v2/admin/care-team-members",
            headers=headers,
            json={
                "user_id": str(user_id),
                "role": "nurse",
                "display_name": "Nurse Duplicate",
                "facility_id": str(fac_id),
            },
        )
        assert res2.status_code == 409
        err = res2.json()
        assert err["error"]["code"] == "CARE_TEAM_MEMBER_CONFLICT"

    def test_care_team_invalid_role_rejected(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        fac_id = uuid4()

        seed_org(sf, tenant_id, "ct-inv-role-org")
        seed_facility(sf, tenant_id, fac_id, "Facility R")
        headers = bearer(_token(admin_id, tenant_id, ["admin"]))

        res = client.post(
            "/api/v2/admin/care-team-members",
            headers=headers,
            json={
                "user_id": str(uuid4()),
                "role": "neurosurgeon",  # Not in Phase 1 vocabulary
                "display_name": "Invalid Role Person",
                "facility_id": str(fac_id),
            },
        )
        assert res.status_code == 422

    def test_care_team_cross_tenant_isolation(self, db_client):
        client, sf = db_client
        tenant_a = uuid4()
        tenant_b = uuid4()
        admin_b = uuid4()
        fac_a = uuid4()
        user_a = uuid4()
        member_a_id = uuid4()

        seed_org(sf, tenant_a, "ct-tenant-a")
        seed_org(sf, tenant_b, "ct-tenant-b")
        seed_facility(sf, tenant_a, fac_a, "Fac A")

        # Seed member directly under Tenant A
        with sf() as s:
            s.add(
                CareTeamMemberModel(
                    id=member_a_id,
                    tenant_id=tenant_a,
                    user_id=user_a,
                    role="nurse",
                    display_name="Nurse A",
                    facility_id=fac_a,
                    active=True,
                )
            )
            s.commit()

        headers_b = bearer(_token(admin_b, tenant_b, ["admin"]))

        # Tenant B admin cannot read member A
        assert client.get(f"/api/v2/admin/care-team-members/{member_a_id}", headers=headers_b).status_code == 404

        # Tenant B admin cannot update member A
        assert client.patch(
            f"/api/v2/admin/care-team-members/{member_a_id}",
            headers=headers_b,
            json={"display_name": "Hacked"},
        ).status_code == 404

        # Tenant B admin cannot deactivate member A
        assert client.post(
            f"/api/v2/admin/care-team-members/{member_a_id}/deactivate",
            headers=headers_b,
        ).status_code == 404


# =============================================================================
# 4. Patient Cohort Inspection & Lifecycle (Admin, PHI-minimized)
# =============================================================================


class TestAdminPatientInspection:
    def test_admin_patient_list_and_detail_phi_minimized(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        fac_id = uuid4()
        patient_id = uuid4()
        clinician_id = uuid4()

        seed_org(sf, tenant_id, "patient-admin-org")
        seed_facility(sf, tenant_id, fac_id, "Central Hospital")
        seed_member(sf, tenant_id, clinician_id, role="doctor", facility_id=fac_id)
        seed_patient(sf, tenant_id, patient_id, facility_id=fac_id, name="Aarav Sharma")

        # Seed clinical observations for this patient (carbs, glucose, meal, medication)
        seed_glucose(sf, tenant_id, patient_id, value=142)
        seed_meal(sf, tenant_id, patient_id, carbs=45.0, gi="medium")
        seed_medication_plan(sf, tenant_id, patient_id)

        headers = bearer(_token(admin_id, tenant_id, ["admin"]))

        # 1. Admin patient list
        list_res = client.get("/api/v2/admin/patients", headers=headers)
        assert list_res.status_code == 200
        list_json = list_res.json()
        assert list_json["total"] >= 1
        item = next(p for p in list_json["items"] if p["patient_id"] == str(patient_id))

        # Assert operational fields present
        assert item["patient_id"] == str(patient_id)
        assert item["name"] == "Aarav Sharma"
        assert item["facility_id"] == str(fac_id)
        assert item["active"] is True
        assert "has_active_mapping" in item
        assert "created_at" in item

        # Explicitly verify PHI minimization on list item: ZERO clinical fields
        item_keys = set(item.keys())
        forbidden_phi_fields = {
            "carbs_grams",
            "glycemic_index",
            "glucose",
            "meal",
            "meals",
            "medication",
            "medications",
            "medication_plan",
            "ai",
            "ai_review",
            "risk",
            "risk_score",
            "diagnostic",
            "observations",
            "glucose_readings",
        }
        intersection = item_keys & forbidden_phi_fields
        assert not intersection, f"Admin patient list exposed forbidden clinical fields: {intersection}"

        # 2. Admin single patient detail
        get_res = client.get(f"/api/v2/admin/patients/{patient_id}", headers=headers)
        assert get_res.status_code == 200
        detail = get_res.json()
        assert detail["patient_id"] == str(patient_id)
        assert detail["name"] == "Aarav Sharma"

        detail_keys = set(detail.keys())
        intersection_detail = detail_keys & forbidden_phi_fields
        assert not intersection_detail, f"Admin patient detail exposed forbidden clinical fields: {intersection_detail}"

    def test_admin_patient_filters(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        fac_1 = uuid4()
        fac_2 = uuid4()
        p1 = uuid4()
        p2 = uuid4()

        seed_org(sf, tenant_id, "patient-filter-org")
        seed_facility(sf, tenant_id, fac_1, "Fac 1")
        seed_facility(sf, tenant_id, fac_2, "Fac 2")
        seed_patient(sf, tenant_id, p1, facility_id=fac_1, name="Patient Fac 1")
        seed_patient(sf, tenant_id, p2, facility_id=fac_2, name="Patient Fac 2")

        headers = bearer(_token(admin_id, tenant_id, ["admin"]))

        # Filter by facility_id
        res_fac1 = client.get(f"/api/v2/admin/patients?facility_id={fac_1}", headers=headers)
        assert res_fac1.status_code == 200
        p_ids = [p["patient_id"] for p in res_fac1.json()["items"]]
        assert str(p1) in p_ids
        assert str(p2) not in p_ids

    def test_admin_patient_deactivate(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        fac_id = uuid4()
        p_id = uuid4()

        seed_org(sf, tenant_id, "patient-deact-org")
        seed_facility(sf, tenant_id, fac_id, "Fac Deact")
        seed_patient(sf, tenant_id, p_id, facility_id=fac_id, name="Active Patient")

        headers = bearer(_token(admin_id, tenant_id, ["admin"]))

        # Deactivate
        deact_res = client.post(f"/api/v2/admin/patients/{p_id}/deactivate", headers=headers)
        assert deact_res.status_code == 200
        assert deact_res.json()["active"] is False

        # Verify inactive on detail read
        get_res = client.get(f"/api/v2/admin/patients/{p_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["active"] is False

    def test_admin_provision_patient(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        fac_id = uuid4()

        seed_org(sf, tenant_id, "patient-prov-org")
        seed_facility(sf, tenant_id, fac_id, "Fac Prov")
        headers = bearer(_token(admin_id, tenant_id, ["admin"]))

        res = client.post(
            "/api/v2/admin/patients",
            headers=headers,
            json={
                "name": "New Enrolled Patient",
                "facility_id": str(fac_id),
                "uh_id": "UHID-7788",
                "phone": "+919876543210",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "New Enrolled Patient"
        assert data["uh_id"] == "UHID-7788"
        assert data["active"] is True
        assert data["has_active_mapping"] is False

    def test_admin_patient_cross_tenant_isolation(self, db_client):
        client, sf = db_client
        tenant_a = uuid4()
        tenant_b = uuid4()
        admin_b = uuid4()
        fac_a = uuid4()
        p_a = uuid4()

        seed_org(sf, tenant_a, "p-tenant-a")
        seed_org(sf, tenant_b, "p-tenant-b")
        seed_facility(sf, tenant_a, fac_a, "Fac A")
        seed_patient(sf, tenant_a, p_a, facility_id=fac_a, name="Patient In Tenant A")

        headers_b = bearer(_token(admin_b, tenant_b, ["admin"]))

        assert client.get(f"/api/v2/admin/patients/{p_a}", headers=headers_b).status_code == 404
        assert client.post(f"/api/v2/admin/patients/{p_a}/deactivate", headers=headers_b).status_code == 404


# =============================================================================
# 5. Identity Mapping Audit Fix
# =============================================================================


class TestIdentityMappingAudit:
    def test_identity_mapping_deactivation_creates_audit_log(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        user_id = uuid4()
        patient_id = uuid4()
        fac_id = uuid4()

        seed_org(sf, tenant_id, "id-audit-org")
        seed_facility(sf, tenant_id, fac_id, "Fac ID")
        seed_patient(sf, tenant_id, patient_id, facility_id=fac_id)

        headers = bearer(_token(admin_id, tenant_id, ["admin"]))

        # 1. Create mapping
        create_res = client.post(
            "/api/v2/admin/identity-mappings",
            headers=headers,
            json={"user_id": str(user_id), "patient_id": str(patient_id)},
        )
        assert create_res.status_code == 201
        mapping_id = create_res.json()["mapping_id"]

        # 2. Deactivate mapping
        deact_res = client.post(
            f"/api/v2/admin/identity-mappings/{mapping_id}/deactivate",
            headers=headers,
        )
        assert deact_res.status_code == 200

        # 3. Query audit events
        audit_res = client.get("/api/v2/admin/audit-events", headers=headers)
        assert audit_res.status_code == 200
        events = audit_res.json()
        mapping_revoke_events = [
            e
            for e in events
            if e["resource_type"] == "identity_mapping"
            and e["action"] == "REVOKE"
            and e["resource_id"] == mapping_id
        ]
        assert len(mapping_revoke_events) >= 1, "Expected audit event for identity mapping deactivation"


# =============================================================================
# 6. Audit Filtering
# =============================================================================


class TestAuditFiltering:
    def test_audit_filtering_by_resource_type_and_time(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()

        seed_org(sf, tenant_id, "audit-filter-org")
        headers = bearer(_token(admin_id, tenant_id, ["admin"]))

        t_start = datetime.now(timezone.utc) - timedelta(seconds=2)

        # Generate facility audit event
        f_res = client.post(
            "/api/v2/admin/facilities",
            headers=headers,
            json={"name": "Audit Facility 1"},
        )
        assert f_res.status_code == 201

        # Query filter by resource_type=facility
        fac_audit = client.get(
            "/api/v2/admin/audit-events?resource_type=facility",
            headers=headers,
        )
        assert fac_audit.status_code == 200
        fac_events = fac_audit.json()
        assert all(e["resource_type"] == "facility" for e in fac_events)
        assert len(fac_events) >= 1

        # Query filter by non-matching resource_type
        other_audit = client.get(
            "/api/v2/admin/audit-events?resource_type=non_existent_type",
            headers=headers,
        )
        assert other_audit.status_code == 200
        assert len(other_audit.json()) == 0

        # Query filter with valid time window
        t_end = datetime.now(timezone.utc) + timedelta(minutes=5)
        time_audit = client.get(
            "/api/v2/admin/audit-events",
            headers=headers,
            params={"start_time": t_start.isoformat(), "end_time": t_end.isoformat()},
        )
        assert time_audit.status_code == 200
        assert len(time_audit.json()) >= 1


# =============================================================================
# 7. RBAC Security Invariants
# =============================================================================


class TestRBACSecurityInvariants:
    def test_non_admin_cannot_access_administrative_endpoints(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        clinician_id = uuid4()
        caregiver_id = uuid4()
        patient_id = uuid4()
        fac_id = uuid4()

        seed_org(sf, tenant_id, "rbac-test-org")
        seed_facility(sf, tenant_id, fac_id, "Fac RBAC")
        seed_member(sf, tenant_id, clinician_id, role="doctor", facility_id=fac_id)
        seed_patient(sf, tenant_id, patient_id, facility_id=fac_id)

        roles_to_test = [
            ("doctor", ["doctor"]),
            ("nurse", ["nurse"]),
            ("caregiver", ["caregiver"]),
            ("patient", ["patient"]),
        ]

        admin_get_endpoints = [
            "/api/v2/admin/facilities",
            "/api/v2/admin/care-team-members",
            "/api/v2/admin/patients",
            "/api/v2/admin/audit-events",
            "/api/v2/admin/identity-mappings",
        ]
        admin_post_endpoints = [
            ("/api/v2/admin/facilities", {"name": "Test Facility"}),
            (
                "/api/v2/admin/care-team-members",
                {
                    "user_id": str(uuid4()),
                    "role": "nurse",
                    "display_name": "Test Nurse",
                    "facility_id": str(fac_id),
                },
            ),
        ]

        for role_name, roles in roles_to_test:
            user_token = _token(uuid4(), tenant_id, roles, facility_id=fac_id)
            headers = bearer(user_token)

            for endpoint in admin_get_endpoints:
                res = client.get(endpoint, headers=headers)
                assert res.status_code == 403, (
                    f"Role {role_name} should be denied 403 on GET {endpoint}, got {res.status_code}"
                )

            for endpoint, payload in admin_post_endpoints:
                res = client.post(endpoint, headers=headers, json=payload)
                assert res.status_code == 403, (
                    f"Role {role_name} should be denied 403 on POST {endpoint}, got {res.status_code}"
                )

    def test_admin_cannot_access_clinical_endpoints(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        fac_id = uuid4()
        patient_id = uuid4()

        seed_org(sf, tenant_id, "admin-clin-deny-org")
        seed_facility(sf, tenant_id, fac_id, "Fac Clin Deny")
        seed_patient(sf, tenant_id, patient_id, facility_id=fac_id)

        admin_headers = bearer(_token(admin_id, tenant_id, ["admin"]))

        # 1. Admin cannot read clinical observations solely because they are admin
        res_obs = client.get(
            f"/api/v2/clinical/observations?patient_id={patient_id}",
            headers=admin_headers,
        )
        assert res_obs.status_code == 403

        # 2. Admin cannot author medication plans
        res_med = client.post(
            "/api/v2/clinical/medication-plans",
            headers=admin_headers,
            json={"patient_id": str(patient_id), "medication": "Metformin", "instruction": "500 mg daily"},
        )
        assert res_med.status_code == 403

        # 3. Admin cannot perform AI review
        res_ai = client.post(
            f"/api/v2/clinical/ai-artifacts/{uuid4()}/review",
            headers=admin_headers,
            json={"decision": "approve"},
        )
        assert res_ai.status_code == 403


# =============================================================================
# 8. Idempotency Verification
# =============================================================================


class TestIdempotencyOnAdminMutations:
    def test_facility_creation_idempotency(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        seed_org(sf, tenant_id, "idem-fac-org")

        headers = bearer(_token(admin_id, tenant_id, ["admin"]))
        headers["Idempotency-Key"] = f"key-fac-{uuid4()}"

        body = {"name": "Idempotent Facility"}

        # First request
        res1 = client.post("/api/v2/admin/facilities", headers=headers, json=body)
        assert res1.status_code == 201
        data1 = res1.json()

        # Replay same request
        res2 = client.post("/api/v2/admin/facilities", headers=headers, json=body)
        assert res2.status_code == 201
        assert res2.headers.get("Idempotent-Replayed") == "true"
        assert res2.json()["facility_id"] == data1["facility_id"]

    def test_care_team_provision_idempotency(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        fac_id = uuid4()
        user_id = uuid4()

        seed_org(sf, tenant_id, "idem-ct-org")
        seed_facility(sf, tenant_id, fac_id, "Fac Idem CT")

        headers = bearer(_token(admin_id, tenant_id, ["admin"]))
        headers["Idempotency-Key"] = f"key-ct-{uuid4()}"

        body = {
            "user_id": str(user_id),
            "role": "dietitian",
            "display_name": "Dietitian Dan",
            "facility_id": str(fac_id),
        }

        # First request
        res1 = client.post("/api/v2/admin/care-team-members", headers=headers, json=body)
        assert res1.status_code == 201
        data1 = res1.json()

        # Replay same request
        res2 = client.post("/api/v2/admin/care-team-members", headers=headers, json=body)
        assert res2.status_code == 201
        assert res2.headers.get("Idempotent-Replayed") == "true"
        assert res2.json()["member_id"] == data1["member_id"]

    def test_patient_deactivation_idempotency(self, db_client):
        client, sf = db_client
        tenant_id = uuid4()
        admin_id = uuid4()
        fac_id = uuid4()
        p_id = uuid4()

        seed_org(sf, tenant_id, "idem-pat-org")
        seed_facility(sf, tenant_id, fac_id, "Fac Idem Pat")
        seed_patient(sf, tenant_id, p_id, facility_id=fac_id, name="Patient Idem")

        headers = bearer(_token(admin_id, tenant_id, ["admin"]))
        headers["Idempotency-Key"] = f"key-deact-{uuid4()}"

        res1 = client.post(f"/api/v2/admin/patients/{p_id}/deactivate", headers=headers)
        assert res1.status_code == 200

        res2 = client.post(f"/api/v2/admin/patients/{p_id}/deactivate", headers=headers)
        assert res2.status_code == 200
        assert res2.headers.get("Idempotent-Replayed") == "true"
