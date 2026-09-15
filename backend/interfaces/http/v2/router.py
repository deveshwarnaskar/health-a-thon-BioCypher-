"""API v2 router aggregation (Gate 07).

All v2 routes are mounted under /api/v2 via the application factory.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.interfaces.http.v2.auth.router import auth_router
from backend.interfaces.http.v2.clinical.router import clinical_router
from backend.interfaces.http.v2.webhooks.router import webhook_router

api_v2_router = APIRouter()
api_v2_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_v2_router.include_router(clinical_router, prefix="/clinical", tags=["Clinical"])
api_v2_router.include_router(webhook_router, prefix="/webhooks", tags=["Webhooks"])
