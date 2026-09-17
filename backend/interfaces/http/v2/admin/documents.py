"""Admin documents routes (Gate 10N).

Tenant-scoped document administration for platform administrators.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from backend.application.ports.unit_of_work import UnitOfWork
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_authorization_policy,
    get_object_storage,
    get_unit_of_work,
)
from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit, get_rate_limiter
from backend.interfaces.http.v2.schemas import (
    DocumentReferenceListResponse,
    DocumentReferenceResponse,
)
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
)
from backend.interfaces.http.v2.security.scoping import authorize_or_403

admin_documents_router = APIRouter()


@admin_documents_router.get(
    "/documents",
    response_model=DocumentReferenceListResponse,
)
async def admin_list_documents(
    request: Request,
    response: Response,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    storage=Depends(get_object_storage),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> DocumentReferenceListResponse:
    """List documents across the tenant (admin-only)."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.ADMIN)

    docs = uow.document_references.list_for_tenant(limit=limit, offset=offset)

    items = []
    for d in docs:
        try:
            url = storage.generate_presigned_url(d.storage_key, expires_in=300)
        except Exception:
            url = None
        items.append(
            DocumentReferenceResponse(
                id=str(d.id),
                patient_id=str(d.patient_id),
                kind=d.kind.value if hasattr(d.kind, "value") else str(d.kind),
                filename=d.filename,
                mime_type=d.mime_type,
                file_size_bytes=d.file_size_bytes,
                created_at=d.created_at,
                download_url=url,
            )
        )

    return DocumentReferenceListResponse(total=len(items), items=items)
