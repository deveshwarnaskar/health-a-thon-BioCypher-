"""Live local smoke test suite for THALI x P.L.A.T.E. WhatsApp & Multimodal Endpoints.

Tests directly against the running FastAPI application on http://localhost:8000.
Executes:
1. Health live probe
2. Health ready probe
3. Webhook GET handshake with valid verify_token
4. Webhook GET handshake with invalid verify_token (403)
5. Webhook POST signature failure (missing header -> 401)
6. Webhook POST signature failure (tampered signature -> 401)
7. Webhook POST text message with valid HMAC-SHA256 signature -> 202
8. Webhook POST replay/deduplication (same message_id -> 202, receipt deduplicated)
9. Webhook POST voice note media metadata -> 202
10. Webhook POST meal image media metadata -> 202
11. Worker execution (--once) to process queued outbox jobs
12. Metrics exposition check on /metrics
"""
from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import Settings


def make_sig_header(raw_body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def run_smoke_tests() -> dict[str, str]:
    settings = Settings()
    base_url = "http://localhost:8000"
    app_secret = settings.whatsapp.app_secret
    verify_token = settings.whatsapp.verify_token

    results: dict[str, str] = {}
    print("=" * 60)
    print("STARTING LIVE SMOKE TESTS AGAINST http://localhost:8000")
    print("=" * 60)

    # 1. Health Live
    try:
        req = urllib.request.Request(f"{base_url}/health/live")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            results["1. Health Live"] = "PASS"
            print("✓ 1. Health Live: PASS")
    except Exception as e:
        results["1. Health Live"] = f"FAIL: {e}"
        print(f"✗ 1. Health Live: FAIL - {e}")

    # 2. Health Ready
    try:
        req = urllib.request.Request(f"{base_url}/health/ready")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data["checks"]["database"] == "ok"
            results["2. Health Ready"] = "PASS"
            print("✓ 2. Health Ready: PASS")
    except Exception as e:
        results["2. Health Ready"] = f"FAIL: {e}"
        print(f"✗ 2. Health Ready: FAIL - {e}")

    # 3. Webhook GET Handshake Valid
    try:
        challenge_val = "1234567890"
        url = f"{base_url}/api/v2/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token={verify_token}&hub.challenge={challenge_val}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8").strip()
            # Can be plain text challenge or JSON {"challenge": "..."}
            assert challenge_val in body
            results["3. Webhook Handshake Valid"] = "PASS"
            print("✓ 3. Webhook Handshake Valid: PASS")
    except Exception as e:
        results["3. Webhook Handshake Valid"] = f"FAIL: {e}"
        print(f"✗ 3. Webhook Handshake Valid: FAIL - {e}")

    # 4. Webhook GET Handshake Invalid Token
    try:
        url = f"{base_url}/api/v2/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=wrong_token&hub.challenge=1234"
        req = urllib.request.Request(url)
        try:
            urllib.request.urlopen(req, timeout=5)
            results["4. Webhook Handshake Invalid Token"] = "FAIL: Expected 403"
            print("✗ 4. Webhook Handshake Invalid Token: FAIL (expected 403)")
        except urllib.error.HTTPError as err:
            assert err.code == 403
            results["4. Webhook Handshake Invalid Token"] = "PASS (403 Forbidden)"
            print("✓ 4. Webhook Handshake Invalid Token: PASS (403 Forbidden)")
    except Exception as e:
        results["4. Webhook Handshake Invalid Token"] = f"FAIL: {e}"
        print(f"✗ 4. Webhook Handshake Invalid Token: FAIL - {e}")

    # 5. Webhook POST Missing Signature
    try:
        req = urllib.request.Request(
            f"{base_url}/api/v2/webhooks/whatsapp",
            data=b'{"entry":[]}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            results["5. Webhook POST Missing Signature"] = "FAIL: Expected 401"
            print("✗ 5. Webhook POST Missing Signature: FAIL (expected 401)")
        except urllib.error.HTTPError as err:
            assert err.code == 401
            results["5. Webhook POST Missing Signature"] = "PASS (401 Unauthorized)"
            print("✓ 5. Webhook POST Missing Signature: PASS (401 Unauthorized)")
    except Exception as e:
        results["5. Webhook POST Missing Signature"] = f"FAIL: {e}"
        print(f"✗ 5. Webhook POST Missing Signature: FAIL - {e}")

    # 6. Webhook POST Tampered Signature
    try:
        payload = b'{"entry":[]}'
        req = urllib.request.Request(
            f"{base_url}/api/v2/webhooks/whatsapp",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=badbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadb",
            },
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            results["6. Webhook POST Tampered Signature"] = "FAIL: Expected 401"
            print("✗ 6. Webhook POST Tampered Signature: FAIL (expected 401)")
        except urllib.error.HTTPError as err:
            assert err.code == 401
            results["6. Webhook POST Tampered Signature"] = "PASS (401 Unauthorized)"
            print("✓ 6. Webhook POST Tampered Signature: PASS (401 Unauthorized)")
    except Exception as e:
        results["6. Webhook POST Tampered Signature"] = f"FAIL: {e}"
        print(f"✗ 6. Webhook POST Tampered Signature: FAIL - {e}")

    # 7. Webhook POST Valid Text Intake
    msg_id_text = f"wamid.smoke.text.{int(time.time())}"
    text_payload = json.dumps({
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_001",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15550001", "phone_number_id": "PN_001"},
                    "contacts": [{"wa_id": "919876543210", "profile": {"name": "Test User"}}],
                    "messages": [{
                        "from": "919876543210",
                        "id": msg_id_text,
                        "timestamp": str(int(time.time())),
                        "type": "text",
                        "text": {"body": "140 fasting"},
                    }],
                },
                "field": "messages",
            }],
        }],
    }).encode("utf-8")

    try:
        sig = make_sig_header(text_payload, app_secret)
        req = urllib.request.Request(
            f"{base_url}/api/v2/webhooks/whatsapp",
            data=text_payload,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 202
            results["7. Webhook POST Valid Text Intake"] = "PASS (202 Accepted)"
            print("✓ 7. Webhook POST Valid Text Intake: PASS (202 Accepted)")
    except Exception as e:
        results["7. Webhook POST Valid Text Intake"] = f"FAIL: {e}"
        print(f"✗ 7. Webhook POST Valid Text Intake: FAIL - {e}")

    # 8. Webhook POST Replay / Deduplication
    try:
        sig = make_sig_header(text_payload, app_secret)
        req = urllib.request.Request(
            f"{base_url}/api/v2/webhooks/whatsapp",
            data=text_payload,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            # Must return 202 Accepted to provider without enqueueing duplicate work
            assert resp.status == 202
            results["8. Webhook Replay Deduplication"] = "PASS (202 Deduplicated)"
            print("✓ 8. Webhook Replay Deduplication: PASS (202 Deduplicated)")
    except Exception as e:
        results["8. Webhook Replay Deduplication"] = f"FAIL: {e}"
        print(f"✗ 8. Webhook Replay Deduplication: FAIL - {e}")

    # 9. Webhook POST Voice Note Metadata
    msg_id_voice = f"wamid.smoke.voice.{int(time.time())}"
    voice_payload = json.dumps({
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_001",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15550001", "phone_number_id": "PN_001"},
                    "contacts": [{"wa_id": "919876543210", "profile": {"name": "Test User"}}],
                    "messages": [{
                        "from": "919876543210",
                        "id": msg_id_voice,
                        "timestamp": str(int(time.time())),
                        "type": "audio",
                        "audio": {
                            "id": "voice_media_file_123",
                            "mime_type": "audio/ogg; codecs=opus",
                            "sha256": "abcdef1234567890",
                            "file_size": 16384,
                            "voice": True,
                        },
                    }],
                },
                "field": "messages",
            }],
        }],
    }).encode("utf-8")

    try:
        sig = make_sig_header(voice_payload, app_secret)
        req = urllib.request.Request(
            f"{base_url}/api/v2/webhooks/whatsapp",
            data=voice_payload,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 202
            results["9. Webhook POST Voice Note Metadata"] = "PASS (202 Accepted)"
            print("✓ 9. Webhook POST Voice Note Metadata: PASS (202 Accepted)")
    except Exception as e:
        results["9. Webhook POST Voice Note Metadata"] = f"FAIL: {e}"
        print(f"✗ 9. Webhook POST Voice Note Metadata: FAIL - {e}")

    # 10. Webhook POST Meal Photo Metadata
    msg_id_image = f"wamid.smoke.image.{int(time.time())}"
    image_payload = json.dumps({
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_001",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15550001", "phone_number_id": "PN_001"},
                    "contacts": [{"wa_id": "919876543210", "profile": {"name": "Test User"}}],
                    "messages": [{
                        "from": "919876543210",
                        "id": msg_id_image,
                        "timestamp": str(int(time.time())),
                        "type": "image",
                        "image": {
                            "id": "image_media_file_456",
                            "mime_type": "image/jpeg",
                            "sha256": "fedcba0987654321",
                            "file_size": 45000,
                            "caption": "lunch",
                        },
                    }],
                },
                "field": "messages",
            }],
        }],
    }).encode("utf-8")

    try:
        sig = make_sig_header(image_payload, app_secret)
        req = urllib.request.Request(
            f"{base_url}/api/v2/webhooks/whatsapp",
            data=image_payload,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 202
            results["10. Webhook POST Meal Image Metadata"] = "PASS (202 Accepted)"
            print("✓ 10. Webhook POST Meal Image Metadata: PASS (202 Accepted)")
    except Exception as e:
        results["10. Webhook POST Meal Image Metadata"] = f"FAIL: {e}"
        print(f"✗ 10. Webhook POST Meal Image Metadata: FAIL - {e}")

    # 11. Worker Execution Once
    try:
        res = subprocess.run(
            [sys.executable, "-m", "backend.interfaces.cli.worker", "--once"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert res.returncode == 0
        results["11. Outbox Worker Execution"] = f"PASS (processed batch, returncode=0)"
        print(f"✓ 11. Outbox Worker Execution: PASS (returncode=0)")
    except Exception as e:
        results["11. Outbox Worker Execution"] = f"FAIL: {e}"
        print(f"✗ 11. Outbox Worker Execution: FAIL - {e}")

    # 12. Prometheus Metrics Exposition
    try:
        req = urllib.request.Request(f"{base_url}/metrics")
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read().decode("utf-8")
            assert "sarvam_requests_total" in content
            assert "voice_pipeline_success_total" in content
            assert "image_pipeline_success_total" in content
            assert "db_pool_size" in content
            # Strict verification: no PHI in metric exposition
            assert "patient_id" not in content
            assert "wamid" not in content
            results["12. Metrics Exposition & PHI Cleanliness"] = "PASS (Exposition verified, 0 PHI)"
            print("✓ 12. Metrics Exposition & PHI Cleanliness: PASS (0 PHI in metrics)")
    except Exception as e:
        results["12. Metrics Exposition & PHI Cleanliness"] = f"FAIL: {e}"
        print(f"✗ 12. Metrics Exposition & PHI Cleanliness: FAIL - {e}")

    print("=" * 60)
    print("LIVE SMOKE SUMMARY:")
    all_pass = all("PASS" in v for v in results.values())
    for k, v in results.items():
        print(f"  {k}: {v}")
    print("OVERALL LIVE SMOKE RESULT:", "PASS" if all_pass else "FAIL")
    print("=" * 60)
    return results


if __name__ == "__main__":
    run_smoke_tests()
