"""Gate 10N — Comprehensive Test Suite for Reports, Documents & S3 Storage.

Verification Matrix (Requirements 1 through 30):
 1. test_generate_clinical_report_pdf
 2. test_generate_clinical_report_png
 3. test_generate_patient_summary_pdf
 4. test_report_storage_private_key_structure
 5. test_report_storage_path_traversal_rejected
 6. test_report_storage_no_public_reads
 7. test_presigned_download_url
 8. test_direct_stream_download
 9. test_patient_self_read_own_document
10. test_patient_cannot_read_other_patient_document
11. test_caregiver_read_verified_patient_document
12. test_caregiver_cannot_read_unverified_patient_document
13. test_caregiver_expired_relationship_denied
14. test_clinician_facility_scoped_access
15. test_clinician_cross_facility_denied
16. test_deactivated_patient_denied
17. test_admin_tenant_scoped_read
18. test_admin_cross_tenant_denied
19. test_patient_summary_dto_asymmetry_no_carbs_no_gi
20. test_patient_summary_omits_ai_internal_hashes
21. test_medication_plan_read_only_in_report
22. test_ai_artifact_review_state_preserved
23. test_idempotency_generate_report
24. test_document_upload_valid_pdf
25. test_document_upload_invalid_mime_rejected
26. test_document_upload_size_limit_enforced
27. test_audit_event_logged_on_report_generation
28. test_audit_event_logged_on_document_download
29. test_unauthenticated_request_denied
30. test_unauthorized_role_denied
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4

import pytest
from starlette.testclient import TestClient

from backend.domain.entities import (
    CareTeamRole,
    DocumentKind,
    DocumentReference,
    MealObservation,
    MedicationPlan,
    ReviewAuthority,
    ReviewState,
)
from backend.domain.value_objects import GlucoseValue, KatoriVolume, MealPortion, ReadingTag
from backend.infrastructure.persistence.models.ops_models import AuditEventModel
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from backend.infrastructure.storage.s3_storage import S3ObjectStorage, build_storage_key
from tests.api.conftest import (
    bearer,
    make_jwt,
    seed_ai_artifact,
    seed_caregiver_relationship,
    seed_document_reference,
    seed_facility,
    seed_glucose,
    seed_identity_mapping,
    seed_meal,
    seed_medication_plan,
    seed_member,
    seed_org,
    seed_patient,
)


@pytest.fixture
def test_setup(db_client):
    """Setup standard test fixture with tenant, facility, clinician, and patient."""
    client, session_factory = db_client
    tenant_id = uuid4()
    seed_org(session_factory, tenant_id, "tenant-10n")
    facility_id = uuid4()
    facility_b_id = uuid4()
    seed_facility(session_factory, tenant_id, facility_id, name="General Hospital 10N")
    seed_facility(session_factory, tenant_id, facility_b_id, name="Other Hospital 10N")

    clinician_user_id = uuid4()
    seed_member(
        session_factory,
        tenant_id,
        clinician_user_id,
        role=CareTeamRole.DOCTOR,
        facility_id=facility_id,
    )

    other_clinician_id = uuid4()
    seed_member(
        session_factory,
        tenant_id,
        other_clinician_id,
        role=CareTeamRole.DOCTOR,
        facility_id=facility_b_id,
    )

    patient_id = uuid4()
    seed_patient(session_factory, tenant_id, patient_id, facility_id=facility_id, name="Patient 10N")
    patient_b_id = uuid4()
    seed_patient(session_factory, tenant_id, patient_b_id, facility_id=facility_b_id, name="Patient B 10N")

    patient_user_id = uuid4()
    seed_identity_mapping(session_factory, tenant_id, patient_user_id, patient_id)

    caregiver_user_id = uuid4()
    seed_caregiver_relationship(
        session_factory,
        tenant_id,
        patient_id,
        caregiver_user_id,
        status="verified",
        capabilities=["read_glucose", "read_meal"],
    )

    admin_user_id = uuid4()

    # Seed observations & plan for patient
    seed_glucose(session_factory, tenant_id, patient_id, 126)
    seed_glucose(session_factory, tenant_id, patient_id, 165)
    seed_medication_plan(session_factory, tenant_id, patient_id, medication="Metformin", instruction="500mg BID")

    # Seed a meal observation with carbs and glycemic index
    seed_meal(session_factory, tenant_id, patient_id, carbs=48.0, gi="medium")

    return {
        "client": client,
        "session_factory": session_factory,
        "tenant_id": tenant_id,
        "facility_id": facility_id,
        "facility_b_id": facility_b_id,
        "clinician_user_id": clinician_user_id,
        "other_clinician_id": other_clinician_id,
        "patient_id": patient_id,
        "patient_b_id": patient_b_id,
        "patient_user_id": patient_user_id,
        "caregiver_user_id": caregiver_user_id,
        "admin_user_id": admin_user_id,
    }


@pytest.fixture
def client(test_setup):
    return test_setup["client"]


@pytest.fixture
def session_factory(test_setup):
    return test_setup["session_factory"]


# 1. test_generate_clinical_report_pdf
def test_generate_clinical_report_pdf(client: TestClient, test_setup):
    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    res = client.post(
        "/api/v2/clinical/reports/generate",
        headers=bearer(token),
        json={
            "patient_id": str(test_setup["patient_id"]),
            "report_type": "clinical_summary",
            "format": "pdf",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["patient_id"] == str(test_setup["patient_id"])
    assert data["kind"] == "clinical_report"
    assert data["mime_type"] == "application/pdf"
    assert data["filename"].endswith(".pdf")
    assert data["file_size_bytes"] > 0
    assert data["download_url"] is not None


# 2. test_generate_clinical_report_png
def test_generate_clinical_report_png(client: TestClient, test_setup):
    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    res = client.post(
        "/api/v2/clinical/reports/generate",
        headers=bearer(token),
        json={
            "patient_id": str(test_setup["patient_id"]),
            "report_type": "clinical_summary",
            "format": "png",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["kind"] == "chart_image"
    assert data["mime_type"] == "image/png"
    assert data["filename"].endswith(".png")
    assert data["file_size_bytes"] > 0


# 3. test_generate_patient_summary_pdf
def test_generate_patient_summary_pdf(client: TestClient, test_setup):
    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    res = client.post(
        "/api/v2/clinical/reports/generate",
        headers=bearer(token),
        json={
            "patient_id": str(test_setup["patient_id"]),
            "report_type": "patient_summary",
            "format": "pdf",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["kind"] == "patient_summary"
    assert data["mime_type"] == "application/pdf"


# 4. test_report_storage_private_key_structure
def test_report_storage_private_key_structure(test_setup):
    tenant_id = test_setup["tenant_id"]
    patient_id = test_setup["patient_id"]
    doc_id = uuid4()
    key = build_storage_key(tenant_id, patient_id, "clinical_report", doc_id, "pdf")
    expected_prefix = f"tenants/{tenant_id}/patients/{patient_id}/clinical_report/{doc_id}.pdf"
    assert key == expected_prefix
    assert ".." not in key
    assert not key.startswith("/")


# 5. test_report_storage_path_traversal_rejected
def test_report_storage_path_traversal_rejected():
    storage = S3ObjectStorage()
    with pytest.raises(ValueError, match="Illegal object key path"):
        storage.put("../secret/passwords.txt", b"malicious")

    with pytest.raises(ValueError, match="Illegal object key path"):
        storage.get("tenants/../../etc/passwd")


# 6. test_report_storage_no_public_reads
def test_report_storage_no_public_reads(client: TestClient, session_factory, test_setup):
    doc = seed_document_reference(session_factory, test_setup["tenant_id"], test_setup["patient_id"])
    res = client.get(f"/api/v2/clinical/documents/{doc.id}/download")
    assert res.status_code == 401


# 7. test_presigned_download_url
def test_presigned_download_url(client: TestClient, session_factory, test_setup):
    from backend.interfaces.http.dependencies import get_object_storage

    storage = get_object_storage()
    key = f"tenants/{test_setup['tenant_id']}/patients/{test_setup['patient_id']}/clinical_report/{uuid4()}.pdf"
    storage.put(key, b"%PDF-1.4 test document content")

    doc = seed_document_reference(
        session_factory,
        test_setup["tenant_id"],
        test_setup["patient_id"],
        facility_id=test_setup["facility_id"],
        storage_key=key,
    )

    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    res = client.get(
        f"/api/v2/clinical/documents/{doc.id}/download?signed_url=true",
        headers=bearer(token),
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "download_url" in data
    assert data["expires_in"] == 300
    assert "expires=" in data["download_url"].lower()


# 8. test_direct_stream_download
def test_direct_stream_download(client: TestClient, session_factory, test_setup):
    from backend.interfaces.http.dependencies import get_object_storage

    storage = get_object_storage()
    key = f"tenants/{test_setup['tenant_id']}/patients/{test_setup['patient_id']}/clinical_report/{uuid4()}.pdf"
    storage.put(key, b"%PDF-1.4 test stream bytes")

    doc = seed_document_reference(
        session_factory,
        test_setup["tenant_id"],
        test_setup["patient_id"],
        facility_id=test_setup["facility_id"],
        storage_key=key,
        filename="custom_report.pdf",
    )

    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    res = client.get(
        f"/api/v2/clinical/documents/{doc.id}/download",
        headers=bearer(token),
    )
    assert res.status_code == 200
    assert res.content == b"%PDF-1.4 test stream bytes"
    assert "custom_report.pdf" in res.headers.get("Content-Disposition", "")


# 9. test_patient_self_read_own_document
def test_patient_self_read_own_document(client: TestClient, session_factory, test_setup):
    seed_document_reference(
        session_factory,
        test_setup["tenant_id"],
        test_setup["patient_id"],
        facility_id=test_setup["facility_id"],
    )

    token = make_jwt(
        sub=str(test_setup["patient_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["patient"],
    )
    res = client.get(
        f"/api/v2/clinical/patients/{test_setup['patient_id']}/documents",
        headers=bearer(token),
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total"] >= 1
    assert data["items"][0]["patient_id"] == str(test_setup["patient_id"])


# 10. test_patient_cannot_read_other_patient_document
def test_patient_cannot_read_other_patient_document(client: TestClient, session_factory, test_setup):
    seed_document_reference(
        session_factory,
        test_setup["tenant_id"],
        test_setup["patient_b_id"],
        facility_id=test_setup["facility_b_id"],
    )

    token = make_jwt(
        sub=str(test_setup["patient_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["patient"],
    )
    res = client.get(
        f"/api/v2/clinical/patients/{test_setup['patient_b_id']}/documents",
        headers=bearer(token),
    )
    assert res.status_code == 403


# 11. test_caregiver_read_verified_patient_document
def test_caregiver_read_verified_patient_document(client: TestClient, session_factory, test_setup):
    seed_document_reference(
        session_factory,
        test_setup["tenant_id"],
        test_setup["patient_id"],
        facility_id=test_setup["facility_id"],
    )

    token = make_jwt(
        sub=str(test_setup["caregiver_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["caregiver"],
    )
    res = client.get(
        f"/api/v2/clinical/patients/{test_setup['patient_id']}/documents",
        headers=bearer(token),
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total"] >= 1


# 12. test_caregiver_cannot_read_unverified_patient_document
def test_caregiver_cannot_read_unverified_patient_document(client: TestClient, session_factory, test_setup):
    unverified_cg_id = uuid4()
    seed_caregiver_relationship(
        session_factory,
        test_setup["tenant_id"],
        test_setup["patient_id"],
        unverified_cg_id,
        status="pending",
    )

    token = make_jwt(
        sub=str(unverified_cg_id),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["caregiver"],
    )
    res = client.get(
        f"/api/v2/clinical/patients/{test_setup['patient_id']}/documents",
        headers=bearer(token),
    )
    assert res.status_code == 403


# 13. test_caregiver_expired_relationship_denied
def test_caregiver_expired_relationship_denied(client: TestClient, session_factory, test_setup):
    expired_cg_id = uuid4()
    seed_caregiver_relationship(
        session_factory,
        test_setup["tenant_id"],
        test_setup["patient_id"],
        expired_cg_id,
        status="verified",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )

    token = make_jwt(
        sub=str(expired_cg_id),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["caregiver"],
    )
    res = client.get(
        f"/api/v2/clinical/patients/{test_setup['patient_id']}/documents",
        headers=bearer(token),
    )
    assert res.status_code == 403


# 14. test_clinician_facility_scoped_access
def test_clinician_facility_scoped_access(client: TestClient, session_factory, test_setup):
    seed_document_reference(
        session_factory,
        test_setup["tenant_id"],
        test_setup["patient_id"],
        facility_id=test_setup["facility_id"],
    )

    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    res = client.get(
        f"/api/v2/clinical/patients/{test_setup['patient_id']}/documents",
        headers=bearer(token),
    )
    assert res.status_code == 200


# 15. test_clinician_cross_facility_denied
def test_clinician_cross_facility_denied(client: TestClient, session_factory, test_setup):
    # Clinician belongs to Facility B, Patient belongs to Facility A
    token = make_jwt(
        sub=str(test_setup["other_clinician_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_b_id"]),
    )
    res = client.post(
        "/api/v2/clinical/reports/generate",
        headers=bearer(token),
        json={
            "patient_id": str(test_setup["patient_id"]),
            "report_type": "clinical_summary",
            "format": "pdf",
        },
    )
    assert res.status_code == 403


# 16. test_deactivated_patient_denied
def test_deactivated_patient_denied(client: TestClient, session_factory, test_setup):
    inactive_patient_id = uuid4()
    seed_patient(
        session_factory,
        test_setup["tenant_id"],
        inactive_patient_id,
        facility_id=test_setup["facility_id"],
        name="Deactivated Patient",
        active=False,
    )

    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    res = client.post(
        "/api/v2/clinical/reports/generate",
        headers=bearer(token),
        json={
            "patient_id": str(inactive_patient_id),
            "report_type": "clinical_summary",
            "format": "pdf",
        },
    )
    assert res.status_code == 403


# 17. test_admin_tenant_scoped_read
def test_admin_tenant_scoped_read(client: TestClient, session_factory, test_setup):
    seed_document_reference(
        session_factory,
        test_setup["tenant_id"],
        test_setup["patient_id"],
    )

    token = make_jwt(
        sub=str(test_setup["admin_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["admin"],
    )
    res = client.get(
        "/api/v2/admin/documents",
        headers=bearer(token),
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total"] >= 1


# 18. test_admin_cross_tenant_denied
def test_admin_cross_tenant_denied(client: TestClient, session_factory, test_setup):
    other_tenant_id = uuid4()
    seed_org(session_factory, other_tenant_id, "other-tenant")
    doc_other = seed_document_reference(
        session_factory,
        other_tenant_id,
        uuid4(),
    )

    # Admin of Tenant A trying to get document of Tenant B
    token = make_jwt(
        sub=str(test_setup["admin_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["admin"],
    )
    res = client.get(
        f"/api/v2/clinical/documents/{doc_other.id}",
        headers=bearer(token),
    )
    assert res.status_code == 404


# 19. test_patient_summary_dto_asymmetry_no_carbs_no_gi
def test_patient_summary_dto_asymmetry_no_carbs_no_gi(session_factory, test_setup):
    from backend.application.queries.build_clinical_report_context import BuildClinicalReportContext
    from backend.application.services.build_clinical_report_context import BuildClinicalReportContextHandler

    with SqlAlchemyUnitOfWork(session_factory, test_setup["tenant_id"]) as uow:
        handler = BuildClinicalReportContextHandler(uow)
        patient_ctx = handler.handle(
            BuildClinicalReportContext(
                patient_id=test_setup["patient_id"],
                report_type="patient_summary",
            )
        )
        clinical_ctx = handler.handle(
            BuildClinicalReportContext(
                patient_id=test_setup["patient_id"],
                report_type="clinical_summary",
            )
        )

    # Patient summary must NOT contain carbs_grams or glycemic_index
    assert len(patient_ctx["meals"]) > 0
    for m in patient_ctx["meals"]:
        assert "carbs_grams" not in m
        assert "glycemic_index" not in m

    # Clinical summary DOES contain carbs_grams and glycemic_index
    assert len(clinical_ctx["meals"]) > 0
    assert clinical_ctx["meals"][0]["carbs_grams"] == 48
    assert clinical_ctx["meals"][0]["glycemic_index"] == "medium"


# 20. test_patient_summary_omits_ai_internal_hashes
def test_patient_summary_omits_ai_internal_hashes(session_factory, test_setup):
    from backend.application.queries.build_clinical_report_context import BuildClinicalReportContext
    from backend.application.services.build_clinical_report_context import BuildClinicalReportContextHandler
    from backend.domain.entities import AIReviewArtifact

    artifact = AIReviewArtifact(
        id=uuid4(),
        patient_id=test_setup["patient_id"],
        tenant_id=test_setup["tenant_id"],
        artifact_kind="extracted_observation",
        authority=ReviewAuthority.CLINICIAN_REVIEW,
        state=ReviewState.APPROVED,
        generated_by="ai",
        summary="Patient showing steady fasting readings.",
        model_name="gemini-1.5-flash",
        evidence_hash="secret_evidence_hash_12345",
    )
    with SqlAlchemyUnitOfWork(session_factory, test_setup["tenant_id"]) as uow:
        uow.ai_artifacts.add(artifact)
        uow.commit()

    with SqlAlchemyUnitOfWork(session_factory, test_setup["tenant_id"]) as uow:
        handler = BuildClinicalReportContextHandler(uow)
        patient_ctx = handler.handle(
            BuildClinicalReportContext(
                patient_id=test_setup["patient_id"],
                report_type="patient_summary",
            )
        )

    for a in patient_ctx["ai_artifacts"]:
        assert "evidence_hash" not in a
        assert "model_name" not in a


# 21. test_medication_plan_read_only_in_report
def test_medication_plan_read_only_in_report(session_factory, test_setup):
    from backend.application.queries.build_clinical_report_context import BuildClinicalReportContext
    from backend.application.services.build_clinical_report_context import BuildClinicalReportContextHandler

    with SqlAlchemyUnitOfWork(session_factory, test_setup["tenant_id"]) as uow:
        plans_before = uow.medication_plans.list_for_patient(test_setup["patient_id"])
        handler = BuildClinicalReportContextHandler(uow)
        ctx = handler.handle(
            BuildClinicalReportContext(
                patient_id=test_setup["patient_id"],
                report_type="clinical_summary",
            )
        )
        plans_after = uow.medication_plans.list_for_patient(test_setup["patient_id"])

    assert len(ctx["medication_plans"]) == 1
    assert ctx["medication_plans"][0]["medication"] == "Metformin"
    assert len(plans_before) == len(plans_after)
    assert plans_before[0].instruction == plans_after[0].instruction


# 22. test_ai_artifact_review_state_preserved
def test_ai_artifact_review_state_preserved(session_factory, test_setup):
    from backend.application.queries.build_clinical_report_context import BuildClinicalReportContext
    from backend.application.services.build_clinical_report_context import BuildClinicalReportContextHandler

    artifact = seed_ai_artifact(
        session_factory,
        test_setup["tenant_id"],
        test_setup["patient_id"],
        state=ReviewState.PENDING_REVIEW,
    )

    with SqlAlchemyUnitOfWork(session_factory, test_setup["tenant_id"]) as uow:
        handler = BuildClinicalReportContextHandler(uow)
        ctx = handler.handle(
            BuildClinicalReportContext(
                patient_id=test_setup["patient_id"],
                report_type="clinical_summary",
            )
        )
        reloaded = uow.ai_artifacts.get(artifact.id)

    # State in report is faithfully pending_review, and not self-approved
    assert ctx["ai_artifacts"][0]["state"] == "pending_review"
    assert reloaded.state == ReviewState.PENDING_REVIEW


# 23. test_idempotency_generate_report
def test_idempotency_generate_report(client: TestClient, test_setup):
    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    idempotency_key = f"gate10n-idem-{uuid4()}"
    headers = {
        **bearer(token),
        "Idempotency-Key": idempotency_key,
    }
    payload = {
        "patient_id": str(test_setup["patient_id"]),
        "report_type": "clinical_summary",
        "format": "pdf",
    }

    res1 = client.post("/api/v2/clinical/reports/generate", headers=headers, json=payload)
    assert res1.status_code == 200, res1.text
    doc_id1 = res1.json()["id"]

    res2 = client.post("/api/v2/clinical/reports/generate", headers=headers, json=payload)
    assert res2.status_code == 200
    assert res2.headers.get("Idempotent-Replayed") == "true"
    assert res2.json()["id"] == doc_id1


# 24. test_document_upload_valid_pdf
def test_document_upload_valid_pdf(client: TestClient, test_setup):
    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    raw_content = b"%PDF-1.4 external clinical chart"
    b64_content = base64.b64encode(raw_content).decode()

    res = client.post(
        f"/api/v2/clinical/patients/{test_setup['patient_id']}/documents/upload",
        headers=bearer(token),
        json={
            "filename": "external_chart.pdf",
            "mime_type": "application/pdf",
            "content_base64": b64_content,
            "kind": "chart_image",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["filename"] == "external_chart.pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["file_size_bytes"] == len(raw_content)


# 25. test_document_upload_invalid_mime_rejected
def test_document_upload_invalid_mime_rejected(client: TestClient, test_setup):
    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    res = client.post(
        f"/api/v2/clinical/patients/{test_setup['patient_id']}/documents/upload",
        headers=bearer(token),
        json={
            "filename": "script.sh",
            "mime_type": "application/x-sh",
            "content_base64": base64.b64encode(b"echo hello").decode(),
            "kind": "chart_image",
        },
    )
    assert res.status_code == 400


# 26. test_document_upload_size_limit_enforced
def test_document_upload_size_limit_enforced(client: TestClient, test_setup):
    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    oversized = b"A" * (11 * 1024 * 1024)  # 11MB
    res = client.post(
        f"/api/v2/clinical/patients/{test_setup['patient_id']}/documents/upload",
        headers=bearer(token),
        json={
            "filename": "huge.pdf",
            "mime_type": "application/pdf",
            "content_base64": base64.b64encode(oversized).decode(),
            "kind": "chart_image",
        },
    )
    assert res.status_code == 413


# 27. test_audit_event_logged_on_report_generation
def test_audit_event_logged_on_report_generation(client: TestClient, session_factory, test_setup):
    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    res = client.post(
        "/api/v2/clinical/reports/generate",
        headers=bearer(token),
        json={
            "patient_id": str(test_setup["patient_id"]),
            "report_type": "clinical_summary",
            "format": "pdf",
        },
    )
    assert res.status_code == 200

    with session_factory() as s:
        audit = (
            s.query(AuditEventModel)
            .filter_by(resource_type="clinical.report")
            .order_by(AuditEventModel.occurred_at.desc())
            .first()
        )
        assert audit is not None
        assert audit.action == "CREATE"


# 28. test_audit_event_logged_on_document_download
def test_audit_event_logged_on_document_download(client: TestClient, session_factory, test_setup):
    from backend.interfaces.http.dependencies import get_object_storage

    storage = get_object_storage()
    key = f"tenants/{test_setup['tenant_id']}/patients/{test_setup['patient_id']}/clinical_report/{uuid4()}.pdf"
    storage.put(key, b"%PDF-1.4 audit download test")

    doc = seed_document_reference(
        session_factory,
        test_setup["tenant_id"],
        test_setup["patient_id"],
        facility_id=test_setup["facility_id"],
        storage_key=key,
    )

    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    res = client.get(
        f"/api/v2/clinical/documents/{doc.id}/download",
        headers=bearer(token),
    )
    assert res.status_code == 200

    with session_factory() as s:
        audit = (
            s.query(AuditEventModel)
            .filter_by(resource_type="clinical.document", resource_id=str(doc.id))
            .order_by(AuditEventModel.occurred_at.desc())
            .first()
        )
        assert audit is not None
        assert audit.action == "READ"


# 29. test_unauthenticated_request_denied
def test_unauthenticated_request_denied(client: TestClient, test_setup):
    res = client.post(
        "/api/v2/clinical/reports/generate",
        json={
            "patient_id": str(test_setup["patient_id"]),
            "report_type": "clinical_summary",
            "format": "pdf",
        },
    )
    assert res.status_code == 401


# 30. test_unauthorized_role_denied
def test_unauthorized_role_denied(client: TestClient, test_setup):
    token = make_jwt(
        sub=str(test_setup["caregiver_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["caregiver"],
    )
    res = client.post(
        "/api/v2/clinical/reports/generate",
        headers=bearer(token),
        json={
            "patient_id": str(test_setup["patient_id"]),
            "report_type": "clinical_summary",
            "format": "pdf",
        },
    )
    assert res.status_code == 403


# 31. test_document_download_base64
def test_document_download_base64(client: TestClient, test_setup, session_factory):
    import base64
    from backend.interfaces.http.dependencies import get_object_storage

    storage = get_object_storage()
    content = b"%PDF-1.4 Authoritative Clinical Report Payload"
    key = f"tenants/{test_setup['tenant_id']}/patients/{test_setup['patient_id']}/clinical_report/{uuid4()}.pdf"
    storage.put(key, content)

    doc = seed_document_reference(
        session_factory,
        test_setup["tenant_id"],
        test_setup["patient_id"],
        facility_id=test_setup["facility_id"],
        storage_key=key,
    )

    token = make_jwt(
        sub=str(test_setup["clinician_user_id"]),
        tenant_id=str(test_setup["tenant_id"]),
        roles=["doctor"],
        facility_id=str(test_setup["facility_id"]),
    )
    res = client.get(
        f"/api/v2/clinical/documents/{doc.id}/download?base64=true",
        headers=bearer(token),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["filename"] == "test_report.pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["content_base64"] == base64.b64encode(content).decode("ascii")
    assert data["file_size_bytes"] == len(content)

