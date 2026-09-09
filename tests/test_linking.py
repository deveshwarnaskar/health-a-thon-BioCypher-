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
                                              operator_key="test-key")))


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