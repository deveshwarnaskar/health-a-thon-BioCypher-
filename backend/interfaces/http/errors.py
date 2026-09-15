"""Safe HTTP exception mapping (Gate 07).

Global exception handlers that map domain/application exceptions to safe HTTP
responses. NEVER leaks stack traces, SQL, filesystem paths, secrets, or PHI.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.application.exceptions import (
    ApplicationError,
    DuplicateCaregiverRelationship,
    DuplicateIdentityMapping,
    ReviewerNotAuthorized,
)
from backend.domain.exceptions import (
    DomainError,
    EntityNotFound,
    InvalidStateTransition,
    UnauthorizedMedicationPlanMutation,
)
from backend.interfaces.http.v2.security.jwt import JwtSignatureError
from backend.interfaces.http.v2.security.roles import role_tokens
from backend.interfaces.http.v2.webhooks.whatsapp.signature import WebhookSignatureError
from backend.interfaces.http.v2.webhooks.whatsapp.verify_token import VerifyTokenError

logger = logging.getLogger(__name__)


def _error_response(
    status: int, code: str, message: str, request: Request
) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "correlation_id": correlation_id,
            }
        },
    )


async def _auth_missing_handler(request: Request, exc: Any) -> JSONResponse:
    return _error_response(401, "AUTHENTICATION_REQUIRED", "Bearer token is required", request)


async def _auth_invalid_handler(request: Request, exc: Any) -> JSONResponse:
    return _error_response(401, "AUTHENTICATION_INVALID", "Authentication credentials are invalid", request)


async def _auth_expired_handler(request: Request, exc: Any) -> JSONResponse:
    return _error_response(401, "AUTHENTICATION_EXPIRED", "Authentication token has expired", request)


async def _authorization_denied_handler(request: Request, exc: Any) -> JSONResponse:
    return _error_response(403, "AUTHORIZATION_DENIED", "Access denied", request)


async def _entity_not_found_handler(request: Request, exc: EntityNotFound) -> JSONResponse:
    return _error_response(404, "RESOURCE_NOT_FOUND", "The requested resource was not found", request)


async def _invalid_state_handler(request: Request, exc: InvalidStateTransition) -> JSONResponse:
    return _error_response(409, "INVALID_STATE", "The operation conflicts with the current state", request)


async def _unauthorized_medication_handler(
    request: Request, exc: UnauthorizedMedicationPlanMutation
) -> JSONResponse:
    return _error_response(403, "MEDICATION_PLAN_UNAUTHORIZED", "Insufficient authority for medication plan", request)


async def _reviewer_not_authorized_handler(
    request: Request, exc: ReviewerNotAuthorized
) -> JSONResponse:
    return _error_response(403, "REVIEW_UNAUTHORIZED", "Insufficient authority to review AI artifacts", request)


async def _duplicate_identity_mapping_handler(
    request: Request, exc: DuplicateIdentityMapping
) -> JSONResponse:
    return _error_response(409, "IDENTITY_MAPPING_CONFLICT", "An active identity mapping already exists", request)


async def _duplicate_caregiver_relationship_handler(
    request: Request, exc: DuplicateCaregiverRelationship
) -> JSONResponse:
    return _error_response(409, "CAREGIVER_RELATIONSHIP_CONFLICT", "An active caregiver relationship already exists", request)


async def _jwt_signature_handler(request: Request, exc: JwtSignatureError) -> JSONResponse:
    return _error_response(401, "JWT_SIGNATURE_INVALID", "JWT signature verification failed", request)


async def _webhook_signature_handler(request: Request, exc: WebhookSignatureError) -> JSONResponse:
    return _error_response(401, "WEBHOOK_SIGNATURE_INVALID", "Webhook signature verification failed", request)


async def _verify_token_handler(request: Request, exc: VerifyTokenError) -> JSONResponse:
    return _error_response(403, "VERIFY_TOKEN_MISMATCH", "Webhook verification token is invalid", request)


async def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return _error_response(400, "DOMAIN_ERROR", "The request violates a business rule", request)


async def _application_error_handler(request: Request, exc: ApplicationError) -> JSONResponse:
    return _error_response(400, "APPLICATION_ERROR", "The request could not be processed", request)


async def _validation_error_handler(request: Request, exc: Any) -> JSONResponse:
    return _error_response(422, "VALIDATION_ERROR", "Request validation failed", request)


async def _http_exception_handler(request: Request, exc: Any) -> JSONResponse:
    """Safe mapping for HTTPExceptions raised by routes/dependencies.

    Never echoes ``exc.detail`` verbatim (it could contain internals).
    """
    status = getattr(exc, "status_code", 500)
    mapping = {
        400: ("INVALID_REQUEST", "The request is invalid"),
        401: ("AUTHENTICATION_REQUIRED", "Authentication is required or invalid"),
        403: ("AUTHORIZATION_DENIED", "Access denied"),
        404: ("RESOURCE_NOT_FOUND", "The requested resource was not found"),
        405: ("METHOD_NOT_ALLOWED", "Method not allowed"),
        409: ("CONFLICT", "The operation conflicts with the current state"),
        413: ("PAYLOAD_TOO_LARGE", "Request body too large"),
        422: ("VALIDATION_ERROR", "Request validation failed"),
        429: ("TOO_MANY_REQUESTS", "Too many requests"),
    }
    code, message = mapping.get(status, ("HTTP_ERROR", "Request could not be completed"))
    return _error_response(status, code, message, request)


async def _generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled exception (no details exposed)")
    return _error_response(500, "INTERNAL_ERROR", "An unexpected error occurred", request)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all safe exception handlers on the FastAPI app."""
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(EntityNotFound, _entity_not_found_handler)
    app.add_exception_handler(InvalidStateTransition, _invalid_state_handler)
    app.add_exception_handler(UnauthorizedMedicationPlanMutation, _unauthorized_medication_handler)
    app.add_exception_handler(ReviewerNotAuthorized, _reviewer_not_authorized_handler)
    app.add_exception_handler(DuplicateIdentityMapping, _duplicate_identity_mapping_handler)
    app.add_exception_handler(DuplicateCaregiverRelationship, _duplicate_caregiver_relationship_handler)
    app.add_exception_handler(JwtSignatureError, _jwt_signature_handler)
    app.add_exception_handler(WebhookSignatureError, _webhook_signature_handler)
    app.add_exception_handler(VerifyTokenError, _verify_token_handler)
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(ApplicationError, _application_error_handler)
    app.add_exception_handler(Exception, _generic_error_handler)
