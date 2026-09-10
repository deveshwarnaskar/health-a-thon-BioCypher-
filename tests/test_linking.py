"""Clinic-side number linking: the operator keys a patient's real WhatsApp
number (and optional caregiver) at runtime. These tests pin the invariants:

  * linking is guarded by an operator key (403 otherwise)
  * after linking, only the new numbers are accepted by the role guard
  * a re-seed never overwrites numbers the operator already linked
  * real-WhatsApp inbound (no patient_id, only the sender number) resolves
    the patient by phone — that is how the live channel reaches the pipeline
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.core.seed import seed_demo
from app.core.process import IngestService
from app.server.main import create_app


def _cli(tmp_path):
    return TestClient(create_app(cfg=Settings(db_path=str(tmp_path / "link.db"),
                                              operator_key="test-key",
                                              whatsapp="simulator")))


# ---- HTTP guard + update -----------------------------------------------
def test_endpoint_requires_operator_key(tmp_path):
    c = _cli(tmp_path)
    pid = c.get("/api/v1/patients").json()[0]["id"]
    r = c.post(f"/api/v1/patients/{pid}/linked",
               json={"patient_phone": "+919800000001"},
               headers={"X-Aahaar-Key": "wrong"})
    assert r.status_code == 403


def test_endpoint_links_and_lists_numbers(tmp_path):
    c = _cli(tmp_path)
    pid = c.get("/api/v1/patients").json()[0]["id"]
    r = c.post(f"/api/v1/patients/{pid}/linked",
               json={"patient_phone": "+919800000001",
                     "caregiver_phone": "+919800000002"},
               headers={"X-Aahaar-Key": "test-key"})
    assert r.status_code == 200
    assert r.json()["patient_phone"] == "+919800000001"
    p = c.get("/api/v1/patients").json()[0]
    assert p["patient_phone"] == "+919800000001"
    assert p["caregiver_phone"] == "+919800000002"


def test_endpoint_rejects_garbage_phone(tmp_path):
    c = _cli(tmp_path)
    pid = c.get("/api/v1/patients").json()[0]["id"]
    r = c.post(f"/api/v1/patients/{pid}/linked",
               json={"patient_phone": "not-a-phone"},
               headers={"X-Aahaar-Key": "test-key"})
    assert r.status_code == 400


# ---- real-WhatsApp path: resolve patient by sender number ---------------
def test_cloud_inbound_resolves_patient_by_sender_phone(seeded, store, cfg):
    pid, _ = seeded
    replies = IngestService(store, cfg).handle(  # no patient_id in the payload
        {"sender_phone": "+919000000001", "kind": "text", "text": "fasting 120"})
    assert replies and "Logged fasting" in replies[0].body


def test_cloud_inbound_fails_for_unlinked_number(seeded, store, cfg):
    pid, _ = seeded
    replies = IngestService(store, cfg).handle(
        {"sender_phone": "+919111111111", "kind": "text", "text": "fasting 120"})
    assert replies and "clinic to link" in replies[0].body.lower()


# ---- re-linking replaces the old bindings --------------------------------
def test_relink_phones_changes_allowed_senders(seeded, store, cfg):
    pid, _ = seeded
    ingest = IngestService(store, cfg)
    store.set_patient_phone(pid, "+919800000001")
    store.set_caregiver_phone(pid, "+919800000002")
    for old in ("+919000000001", "+919000000002"):
        r = ingest.handle({"patient_id": pid, "sender_phone": old,
                           "kind": "text", "text": "fasting 120"})
        assert r and "clinic to link" in r[0].body.lower(), old
    for new in ("+919800000001", "+919800000002"):
        r = ingest.handle({"patient_id": pid, "sender_phone": new,
                           "kind": "text", "text": "fasting 120"})
        assert r and "Logged fasting" in r[0].body, new


# ---- re-seed preserves operator-linked numbers ---------------------------
def test_reseed_keeps_operator_linked_numbers(store, cfg):
    pid, _ = seed_demo(store, cfg, days=14,
                       phone="+911111111111", caregiver_phone="+911111111112")
    store.set_patient_phone(pid, "+919800000001")
    pid2, _ = seed_demo(store, cfg, days=14)   # same uh_id -> same patient
    assert pid2 == pid
    assert store.get_patient(pid)["phone"] == "+919800000001"
    assert store.get_caregiver(pid)["phone"] == "+911111111112"


def test_meta_webhook_digits_only_matches_plus_phone(seeded, store, cfg):
    """Meta Cloud API delivers `from` as digits only (e.g. '919000000001').
    The DB stores '+919000000001'. The resolver must match seamlessly."""
    ingest = IngestService(store, cfg)
    replies = ingest.handle({"sender_phone": "919000000001", "kind": "text", "text": "fasting 128"})
    assert replies and "Logged fasting: 128" in replies[0].body


def test_patient_sends_fasting_keyword_only_gets_helpful_ai_prompt(seeded, store, cfg):
    """When a patient types just 'fasting' without a number, the AI prompts for the value."""
    ingest = IngestService(store, cfg)
    replies = ingest.handle({"sender_phone": "919000000001", "kind": "text", "text": "fasting"})
    assert replies
    reply_body = replies[0].body.lower()
    assert "fasting" in reply_body or "reading" in reply_body or "sugar" in reply_body


def test_patient_log_returns_inbound_and_outbound(tmp_path):
    """Verify GET /api/v1/patients/{pid}/log contains both inbound raw speech and outbound replies."""
    c = _cli(tmp_path)
    pid = c.get("/api/v1/patients").json()[0]["id"]
    # Send inbound message
    c.post("/api/v1/inbound", json={"patient_id": pid, "sender_phone": "+919000000001",
                                    "kind": "text", "text": "fasting 115"})
    log = c.get(f"/api/v1/patients/{pid}/log").json()
    assert "inbound" in log
    assert "outbound" in log
    assert any("fasting 115" in m.get("raw_text", "") for m in log["inbound"])

def test_meta_webhook_endpoint_background_processing(tmp_path):
    """Verify POST /api/v1/webhooks/whatsapp returns fast 200 OK and executes ingest in background."""
    c = _cli(tmp_path)
    pid = c.get("/api/v1/patients").json()[0]["id"]
    
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "contacts": [{"wa_id": "917439030190"}],
                            "messages": [
                                {
                                    "from": "917439030190",
                                    "type": "text",
                                    "text": {"body": "fasting 124"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    
    r = c.post("/api/v1/webhooks/whatsapp", json=payload)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "processed": 1}
    
    # TestClient automatically flushes background tasks before returning
    log = c.get(f"/api/v1/patients/{pid}/log").json()
    assert any("fasting 124" in m.get("raw_text", "") for m in log["inbound"])


def test_debug_status_and_test_whatsapp(tmp_path):
    """Verify GET /api/v1/debug/status and POST /api/v1/debug/test-whatsapp."""
    c = _cli(tmp_path)
    r = c.get("/api/v1/debug/status")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "channel" in data
    assert "cloud_ready" in data
    assert "last_dispatch" in data

    # Test ping endpoint
    r2 = c.post("/api/v1/debug/test-whatsapp", json={"phone": "+917439030190", "message": "Test ping"})
    assert r2.status_code == 200
    assert r2.json()["success"] is True


def test_clear_patient_chat(tmp_path):
    """Verify POST /api/v1/patients/{pid}/clear-chat wipes chat thread."""
    c = _cli(tmp_path)
    pid = c.get("/api/v1/patients").json()[0]["id"]
    
    # Send a message to populate inbound and outbound
    c.post("/api/v1/inbound", json={
        "patient_id": pid,
        "sender_phone": "+917439030190",
        "kind": "text",
        "text": "fasting 115"
    })
    log = c.get(f"/api/v1/patients/{pid}/log").json()
    assert len(log["inbound"]) > 0
    assert len(log["outbound"]) > 0

    # Clear chat
    clr = c.post(f"/api/v1/patients/{pid}/clear-chat")
    assert clr.status_code == 200
    assert clr.json()["ok"] is True

    # Check that chat thread is now empty
    empty_log = c.get(f"/api/v1/patients/{pid}/log").json()
    assert len(empty_log["inbound"]) == 0
    assert len(empty_log["outbound"]) == 0

