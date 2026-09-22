"""Integration tests for AI API endpoints (/api/v2/ai).

Tests:
1. /api/v2/ai/analyze-meal: Indian meal macronutrients, portion scoring, Hinglish guidance
2. /api/v2/ai/chat: Indic conversational health assistant with safety boundaries
3. /api/v2/ai/calculate-glycemic: Statistical calculations (TIR, TAR, TBR, eA1c, GMI, CV%)
4. /api/v2/ai/transcribe-base64: Audio transcription base64 endpoint
"""

from __future__ import annotations

import base64
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from backend.interfaces.http.app import create_app
from tests.api.conftest import bearer, make_jwt


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def patient_auth():
    user_id = uuid4()
    tenant_id = uuid4()
    token = make_jwt(
        sub=str(user_id),
        tenant_id=str(tenant_id),
        roles=["Patient"],
    )
    return bearer(token)


@pytest.fixture
def clinician_auth():
    user_id = uuid4()
    tenant_id = uuid4()
    facility_id = uuid4()
    token = make_jwt(
        sub=str(user_id),
        tenant_id=str(tenant_id),
        roles=["Doctor"],
        facility_id=str(facility_id),
    )
    return bearer(token)


def test_analyze_meal_endpoint(client, patient_auth):
    resp = client.post(
        "/api/v2/ai/analyze-meal",
        headers=patient_auth,
        json={
            "description": "2 roti, 1 katori dal aur thoda salad",
            "patient_name": "Subham",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 2
    assert data["total_calories_kcal"] > 0
    assert data["total_carbs_g"] > 0
    assert data["total_protein_g"] > 0
    assert data["glycemic_impact"] in ("LOW", "MODERATE", "ELEVATED")
    assert "patient_guidance_hinglish" in data


def test_conversational_chat_endpoint(client, patient_auth):
    resp = client.post(
        "/api/v2/ai/chat",
        headers=patient_auth,
        json={
            "message": "Kya main aam kha sakta hoon?",
            "patient_name": "Subham",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert len(data["reply"]) > 10
    assert data["safety_checked"] is True


def test_calculate_glycemic_endpoint(client, patient_auth):
    resp = client.post(
        "/api/v2/ai/calculate-glycemic",
        headers=patient_auth,
        json={
            "readings": [
                {"value_mg_dl": 110, "tag": "fasting", "taken_at": "2026-09-21T08:00:00"},
                {"value_mg_dl": 140, "tag": "postlunch", "taken_at": "2026-09-21T14:00:00"},
                {"value_mg_dl": 125, "tag": "postdinner", "taken_at": "2026-09-21T21:00:00"},
            ]
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_readings"] == 3
    assert data["mean_glucose_mg_dl"] == 125.0
    assert data["time_in_range_pct"] == 100.0
    assert data["time_below_range_pct"] == 0.0
    assert data["estimated_hba1c_pct"] is not None
    assert data["variability_category"] == "STABLE"


from unittest.mock import patch


@patch("backend.infrastructure.ai.sarvam_client.SarvamClient.transcribe_audio")
def test_transcribe_base64_endpoint(mock_transcribe, client, patient_auth):
    mock_transcribe.return_value = {
        "transcript": "Maine 2 roti aur dal khaya",
        "language_code": "hi-IN",
        "latency_ms": 120.0,
    }
    fake_audio_bytes = b"ID3\x03\x00\x00\x00\x00\x00#TSSE\x00\x00\x00\x0f\x00\x00\x03Lavf58.29.100"
    b64_audio = base64.b64encode(fake_audio_bytes).decode("utf-8")

    resp = client.post(
        "/api/v2/ai/transcribe-base64",
        headers=patient_auth,
        json={
            "audio_base64": b64_audio,
            "mime_type": "audio/mp3",
            "language_code": "hi-IN",
            "filename": "voice.mp3",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] == "Maine 2 roti aur dal khaya"
    assert "provider" in data
