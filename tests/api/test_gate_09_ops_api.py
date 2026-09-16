"""Gate 09 API — idempotency middleware, rate limiting, admin audit trail.

Proves the client-visible contract §7 end-to-end:

- A completed unsafe request is replayed verbatim (status, body, headers) plus
  ``Idempotent-Replayed: true``.
- Same key + different payload → 409 ``IDEMPOTENCY_KEY_MISMATCH``.
- Concurrent in-progress reservation → 409 ``CONCURRENT_REQUEST_IN_PROGRESS``.
- Malformed key → 400 ``INVALID_IDEMPOTENCY_KEY`` (before auth).
- Safe methods (GET) never participate.
- Rate-limit tiers are asserted through a dependency override (contract §9).
- The admin audit-trail endpoint is admin-only and tenant-scoped (§10).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.application.ops.contracts import RateLimitFailurePolicy
from backend.infrastructure.cache.rate_limiter import InMemorySlidingWindowRateLimiter
from backend.infrastructure.persistence.ops.idempotency_store import SqlAlchemyIdempotencyStore
from backend.interfaces.http.dependencies import get_engine
from backend.interfaces.http.ops.idempotency import build_fingerprint
from tests.api.conftest import (
    _ensure_app_schema,
    bearer,
    make_jwt,
    seed_facility,
    seed_member,
    seed_org,
    seed_patient,
)

_WEBHOOK_SECRET = "dev-webhook-secret-change-in-production"


def _compact(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _post_mapping(client, token, body_bytes, key=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if key:
        headers["Idempotency-Key"] = key
    return client.post(
        "/api/v2/admin/identity-mappings",
        content=body_bytes,
        headers=headers,
    )


def _sign(body: bytes) -> str:
    sig = hmac.new(_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


class TestIdempotencyMiddleware:

    def _seed(self, sf, slug):
        tid, fid, actor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
        seed_org(sf, tid, slug)
        seed_facility(sf, tid, fid, "Facility A")
        seed_patient(sf, tid, patient_id, facility_id=fid, name="Mapped")
        seed_member(sf, tid, user_id=actor_id, role="care_coordinator", facility_id=fid)
        token = make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["admin"])
        return tid, actor_id, patient_id, token

    def test_replay_returns_cached_response_verbatim(self, db_client):
        c, sf = db_client
        _, _, patient_id, token = self._seed(sf, "idm-replay")
        body = _compact({"user_id": str(uuid4()), "patient_id": str(patient_id)})

        first = _post_mapping(c, token, body, key="req-001")
        assert first.status_code == 201

        replay = _post_mapping(c, token, body, key="req-001")
        assert replay.status_code == 201
        assert replay.headers.get("idempotent-replayed") == "true"
        assert replay.json() == first.json()

    def test_different_requests_same_key_conflict(self, db_client):
        c, sf = db_client
        _, _, patient_id, token = self._seed(sf, "idm-mismatch")
        body_a = _compact({"user_id": str(uuid4()), "patient_id": str(patient_id)})
        body_b = _compact({"user_id": str(uuid4()), "patient_id": str(patient_id)})

        assert _post_mapping(c, token, body_a, key="req-002").status_code == 201
        resp = _post_mapping(c, token, body_b, key="req-002")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "IDEMPOTENCY_KEY_MISMATCH"

    def test_in_progress_reservation_conflicts(self, db_client):
        c, sf = db_client
        tid, actor_id, patient_id, token = self._seed(sf, "idm-inflight")
        body = _compact({"user_id": str(uuid4()), "patient_id": str(patient_id)})
        fp = build_fingerprint(
            method="POST",
            path="/api/v2/admin/identity-mappings",
            raw_body=body,
            secret="test-secret",
        )

        session = Session(get_engine())
        try:
            SqlAlchemyIdempotencyStore(session).reserve(tid, actor_id, "req-inflight", fp)
            session.commit()
        finally:
            session.close()

        resp = _post_mapping(c, token, body, key="req-inflight")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "CONCURRENT_REQUEST_IN_PROGRESS"

    def test_malformed_key_rejected_before_auth(self, db_client):
        c, _ = db_client
        body = _compact({"user_id": str(uuid4()), "patient_id": str(uuid4())})
        resp = _post_mapping(c, "not-a-token", body, key="bad key!!")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_IDEMPOTENCY_KEY"

    def test_safe_method_bypasses_idempotency(self, client):
        resp = client.get(
            "/api/v2/webhooks/whatsapp",
            params={"hub.mode": "subscribe", "hub.verify_token": "thali-dev-verify-token", "hub.challenge": "C"},
            headers={"Idempotency-Key": "bad key!!"},
        )
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "C"

    def test_no_key_means_no_dedup(self, db_client):
        c, sf = db_client
        tid, _, patient_id, token = self._seed(sf, "idm-nokey")
        other_patient = seed_patient(sf, tid, uuid4(), facility_id=uuid4(), name="Second")
        first = _post_mapping(c, token, _compact({"user_id": str(uuid4()), "patient_id": str(patient_id)}))
        second = _post_mapping(c, token, _compact({"user_id": str(uuid4()), "patient_id": str(other_patient.id)}))
        assert first.status_code == 201
        assert second.status_code == 201


class TestRateLimitOverride:
    """Rate limiting driven through a shared in-memory limiter (§9)."""

    def test_webhook_tier_exhaustion_returns_429(self, client, monkeypatch):
        from backend.interfaces.http.ops.rate_limit import RateTier, TIERS, get_rate_limiter

        monkeypatch.setitem(
            TIERS,
            "webhook",
            RateTier("webhook", limit=2, window_seconds=1, burst=1, policy=RateLimitFailurePolicy.FAIL_OPEN),
        )

        _ensure_app_schema()
        from backend.interfaces.http.app import create_app

        limiter = InMemorySlidingWindowRateLimiter()

        def _override_limiter():
            return limiter

        app = create_app()
        app.dependency_overrides[get_rate_limiter] = _override_limiter
        c = TestClient(app, raise_server_exceptions=False)
        body = b'{"object": "whatsapp_business_account"}'
        codes = [
            c.post(
                "/api/v2/webhooks/whatsapp",
                content=body,
                headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
            ).status_code
            for _ in range(4)
        ]
        assert codes[:3] == [202, 202, 202]
        assert codes[3] == 429
        resp = c.post(
            "/api/v2/webhooks/whatsapp",
            content=body,
            headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
        )
        assert resp.status_code == 429
        assert resp.headers.get("Retry-After") is not None
        assert resp.headers.get("X-RateLimit-Limit") is not None


class TestAuditEventsEndpoint:

    def test_admin_only_and_tenant_scoped(self, db_client):
        c, sf = db_client

        def _seed_audit(slug):
            tid, fid, actor_id, patient_id = uuid4(), uuid4(), uuid4(), uuid4()
            seed_org(sf, tid, slug)
            seed_facility(sf, tid, fid, "Facility A")
            seed_patient(sf, tid, patient_id, facility_id=fid, name="Audit")
            seed_member(sf, tid, user_id=actor_id, role="care_coordinator", facility_id=fid)
            return tid, actor_id, patient_id, make_jwt(sub=str(actor_id), tenant_id=str(tid), roles=["admin"])

        tid_a, _, patient_a, admin_a = _seed_audit("audit-a")
        tid_b, _, _, admin_b = _seed_audit("audit-b")

        body = _compact({"user_id": str(uuid4()), "patient_id": str(patient_a)})
        assert _post_mapping(c, admin_a, body).status_code == 201

        non_admin = make_jwt(sub=str(uuid4()), tenant_id=str(tid_a), roles=["doctor"])
        denied = c.get("/api/v2/admin/audit-events", headers=bearer(non_admin))
        assert denied.status_code == 403

        other = c.get("/api/v2/admin/audit-events", headers=bearer(admin_b))
        assert other.status_code == 200
        assert other.json() == []

        mine = c.get("/api/v2/admin/audit-events", headers=bearer(admin_a))
        assert mine.status_code == 200
        events = mine.json()
        assert any(
            e["resource_type"] == "identity_mapping"
            and e["action"] == "CREATE"
            and e["outcome"] == "SUCCESS"
            for e in events
        )
        assert all(e["tenant_id"] == str(tid_a) for e in events)
        assert all(e["audit_event_id"] for e in events)


__all__ = ["TestIdempotencyMiddleware", "TestRateLimitOverride", "TestAuditEventsEndpoint"]