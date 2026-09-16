"""Gate 09 — idempotency-key middleware (HTTP).

Client-visible behavior (contract §7):

- ``Idempotency-Key`` header (1..128 chars of ``[A-Za-z0-9_-]``) reserves the
  request for ``tenant ‖ actor ‖ key`` for 24h.
- A completed replay returns the cached status, body and headers verbatim plus
  ``Idempotent-Replayed: true``.
- A concurrent in-progress request returns 409 ``CONCURRENT_REQUEST_IN_PROGRESS``.
- The same key with a different payload returns 409 ``IDEMPOTENCY_KEY_MISMATCH``.
- On any downstream failure the reservation is released so the client can retry.

Only unsafe methods (POST/PUT/PATCH/DELETE) participate. If the caller token is
invalid the middleware passes the request through and the route's own
authentication dependency produces the 401. A failed reservation (DB hiccup)
fails OPEN: the request proceeds without a guarantee rather than being dropped.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from backend.interfaces.http.dependencies import _get_engine, get_db_url
from backend.infrastructure.config.database import create_session_factory
from backend.infrastructure.persistence.ops.idempotency_store import SqlAlchemyIdempotencyStore
from backend.interfaces.http.v2.security.jwt import verify_hs256

logger = logging.getLogger(__name__)

_IDEMPOTENCY_TTL_SECONDS = 86_400  # contract §7.5
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_KEY_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")


def build_fingerprint(*, method: str, path: str, raw_body: bytes, secret: str) -> str:
    """HMAC-SHA256 over METHOD|PATH|RAW_BODY using the JWT secret.

    The fingerprint is deterministic for byte-identical retries and
    unpredictable to clients, so a doomed key can never be replayed elsewhere.
    """
    material = b"|".join(
        [
            method.upper().encode("ascii"),
            path.encode("utf-8"),
            raw_body,
        ]
    )
    return hmac.new(secret.encode("utf-8"), material, hashlib.sha256).hexdigest()


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Reserve/complete/replay idempotency-key requests in-process.

    Registered beneath the correlation/security middleware so outer layers still
    stamp headers on responses this middleware short-circuits.
    """

    def __init__(self, app: Any, secret: str) -> None:
        super().__init__(app)
        self._secret = secret
        self._engine = _get_engine(get_db_url())
        self._session_factory = create_session_factory(self._engine)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)
        if not _KEY_RE.match(key):
            return self._error(request, 400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key header is malformed")

        claims = self._safe_claims(request)
        if claims is None:
            return await call_next(request)

        tenant_id = claims["tenant_id"]
        actor_id = claims["actor_id"]
        raw_body = await request.body()
        fingerprint = build_fingerprint(
            method=request.method,
            path=request.url.path,
            raw_body=raw_body,
            secret=self._secret,
        )

        session = self._session_factory()
        store = SqlAlchemyIdempotencyStore(session)
        try:
            result = store.reserve(tenant_id, actor_id, key, fingerprint, _IDEMPOTENCY_TTL_SECONDS)
            session.commit()
        except Exception:
            logger.exception("idempotency reservation failed; request proceeds without guarantee")
            session.rollback()
            session.close()
            return await call_next(request)

        if result.accepted:
            try:
                response = await call_next(request)
            except Exception:
                try:
                    store.release_failed(tenant_id, actor_id, key)
                    session.commit()
                except Exception:
                    logger.exception("failed to release idempotency reservation")
                    session.rollback()
                session.close()
                raise
            body = await self._collect_body(response)
            if body is not None and 200 <= response.status_code < 400:
                try:
                    store.complete(
                        tenant_id,
                        actor_id,
                        key,
                        response.status_code,
                        dict(response.headers),
                        body.decode("utf-8", "replace"),
                    )
                    session.commit()
                except Exception:
                    logger.exception("failed to finalize idempotency record")
                    session.rollback()
            session.close()
            if body is not None:
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
            return response

        session.close()
        if result.replay:
            headers = dict(result.headers or {})
            headers["Idempotent-Replayed"] = "true"
            return Response(
                content=(result.body or "").encode("utf-8"),
                status_code=result.status_code or 200,
                headers=headers,
            )
        if result.conflict == "in_progress":
            return self._error(
                request,
                409,
                "CONCURRENT_REQUEST_IN_PROGRESS",
                "A request with this idempotency key is currently being processed",
            )
        return self._error(
            request,
            409,
            "IDEMPOTENCY_KEY_MISMATCH",
            "Idempotency-Key was reused with a different request payload",
        )

    def _safe_claims(self, request: Request) -> dict | None:
        authorization = request.headers.get("authorization")
        if not authorization or not authorization.startswith("Bearer "):
            return None
        token = authorization[len("Bearer "):]
        try:
            payload = verify_hs256(token, self._secret).payload
            actor_id = uuid.UUID(str(payload.get("sub")))
            tenant_id = uuid.UUID(str(payload.get("tenant_id")))
        except Exception:
            return None
        return {"actor_id": actor_id, "tenant_id": tenant_id}

    async def _collect_body(self, response: Response) -> bytes | None:
        try:
            if getattr(response, "body", None):
                return response.body
            chunks = [chunk async for chunk in response.body_iterator]
            return b"".join(chunks)
        except Exception:
            logger.exception("failed to capture response body for idempotency cache")
            return None

    def _error(self, request: Request, status: int, code: str, message: str) -> Response:
        correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
        return Response(
            content=json.dumps(
                {"error": {"code": code, "message": message, "correlation_id": correlation_id}}
            ).encode("utf-8"),
            status_code=status,
            media_type="application/json",
            headers={"Cache-Control": "no-store"},
        )


__all__ = ["IdempotencyMiddleware", "build_fingerprint"]