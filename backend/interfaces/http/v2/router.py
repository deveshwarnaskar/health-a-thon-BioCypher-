"""API v2 router aggregation (Gate 07).

All v2 routes are mounted under /api/v2 via the application factory.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.interfaces.http.v2.admin.audit import admin_audit_router
from backend.interfaces.http.v2.admin.documents import admin_documents_router
from backend.interfaces.http.v2.admin.facilities import admin_facilities_router
from backend.interfaces.http.v2.admin.identity import admin_router
from backend.interfaces.http.v2.admin.patients import admin_patients_router
from backend.interfaces.http.v2.admin.provisioning import admin_provisioning_router
from backend.interfaces.http.v2.auth.router import auth_router
from backend.interfaces.http.v2.caregivers import caregivers_router
from backend.interfaces.http.v2.clinical.router import clinical_router
from backend.interfaces.http.v2.notifications import notifications_router
from backend.interfaces.http.v2.patients.router import patients_router
from backend.interfaces.http.v2.tasks.router import tasks_router
from backend.interfaces.http.v2.webhooks.router import webhook_router

api_v2_router = APIRouter()
api_v2_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_v2_router.include_router(caregivers_router, prefix="/caregivers", tags=["Caregivers"])
api_v2_router.include_router(clinical_router, prefix="/clinical", tags=["Clinical"])
api_v2_router.include_router(patients_router, prefix="/patients", tags=["Patients"])
api_v2_router.include_router(tasks_router, prefix="/care-tasks", tags=["Care Tasks"])
api_v2_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
api_v2_router.include_router(admin_router, prefix="/admin", tags=["Admin"])
api_v2_router.include_router(admin_audit_router, prefix="/admin", tags=["Admin"])
api_v2_router.include_router(admin_provisioning_router, prefix="/admin", tags=["Admin"])
api_v2_router.include_router(admin_facilities_router, prefix="/admin", tags=["Admin"])
api_v2_router.include_router(admin_patients_router, prefix="/admin", tags=["Admin"])
api_v2_router.include_router(admin_documents_router, prefix="/admin", tags=["Admin"])
api_v2_router.include_router(webhook_router, prefix="/webhooks", tags=["Webhooks"])


