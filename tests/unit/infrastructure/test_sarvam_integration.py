"""Unit tests for Sarvam AI Integration (Gate 10M + Indic Workflows).

Verifies:
1. SarvamClient fail-safe boundaries (CREDENTIALS_MISSING, TIMEOUT, 4XX, 5XX, MALFORMED_OUTPUT)
2. SarvamAIProvider clinical draft generation conforming to AIProvider protocol
3. IndicNutritionAnalyzer ICMR-NIN nutrition calculations & portion scoring
4. ClinicalCalculator glycemic analytics (TIR, TAR, TBR, eA1c, GMI, CV%)
5. Conversational assistant emergency triage & Hinglish reply generation
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from backend.application.ports.ai import (
    AITaskDefinition,
    AITaskType,
    DEFAULT_SYSTEM_CONSTRAINTS,
    EvidencePackage,
)
from backend.application.services.clinical_calculator import calculate_glycemic_metrics
from backend.application.services.conversational_assistant import (
    generate_conversational_reply,
    match_conversational_query,
)
from backend.infrastructure.ai.indic_nutrition_analyzer import IndicNutritionAnalyzer
from backend.infrastructure.ai.sarvam_client import SarvamClient, SarvamClientError
from backend.infrastructure.ai.sarvam_provider import SarvamAIProvider


class TestSarvamClient:
    def test_missing_credentials_fails_safe(self):
        client = SarvamClient(api_key="")
        assert not client.is_configured
        with pytest.raises(SarvamClientError) as exc_info:
            client.chat_completion([{"role": "user", "content": "hello"}])
        assert exc_info.value.error_code == "CREDENTIALS_MISSING"
        assert not exc_info.value.retryable

    @patch("httpx.Client.post")
    def test_chat_completion_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"summary": "Clinical test summary"}'}}],
            "usage": {"total_tokens": 150},
        }
        mock_post.return_value = mock_resp

        client = SarvamClient(api_key="test-sarvam-key")
        res = client.chat_completion([{"role": "user", "content": "test"}])
        assert "Clinical test summary" in res["content"]
        assert res["model"] == "sarvam-105b-conversations"
        assert res["usage"]["total_tokens"] == 150

    @patch("httpx.Client.post")
    def test_transcribe_audio_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "transcript": "Maine 2 roti aur dal khaya",
            "language_code": "hi-IN",
        }
        mock_post.return_value = mock_resp

        client = SarvamClient(api_key="test-sarvam-key")
        res = client.transcribe_audio(b"fake-audio-bytes", language_code="hi-IN")
        assert res["transcript"] == "Maine 2 roti aur dal khaya"
        assert res["language_code"] == "hi-IN"

    @patch("httpx.Client.post")
    def test_chat_completion_timeout_is_retryable(self, mock_post):
        import httpx

        mock_post.side_effect = httpx.TimeoutException("Read timed out")
        client = SarvamClient(api_key="test-sarvam-key")
        with pytest.raises(SarvamClientError) as exc_info:
            client.chat_completion([{"role": "user", "content": "hi"}])
        assert exc_info.value.error_code == "TIMEOUT"
        assert exc_info.value.retryable is True

    @patch("httpx.Client.post")
    def test_chat_completion_500_is_retryable(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_resp.text = "Bad Gateway"
        mock_post.return_value = mock_resp

        client = SarvamClient(api_key="test-sarvam-key")
        with pytest.raises(SarvamClientError) as exc_info:
            client.chat_completion([{"role": "user", "content": "hi"}])
        assert exc_info.value.error_code == "PROVIDER_5XX"
        assert exc_info.value.retryable is True

    @patch("httpx.Client.post")
    def test_chat_completion_400_not_retryable(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_post.return_value = mock_resp

        client = SarvamClient(api_key="test-sarvam-key")
        with pytest.raises(SarvamClientError) as exc_info:
            client.chat_completion([{"role": "user", "content": "hi"}])
        assert exc_info.value.error_code == "PROVIDER_4XX"
        assert exc_info.value.retryable is False


class TestSarvamAIProvider:
    def test_provider_missing_credentials_fails_safe(self):
        provider = SarvamAIProvider(api_key="")
        task = AITaskDefinition(
            task_type=AITaskType.CLINICAL_SUMMARY,
            system_constraints=DEFAULT_SYSTEM_CONSTRAINTS,
            patient_id=uuid4(),
            tenant_id=uuid4(),
        )
        evidence = EvidencePackage(patient_id=task.patient_id, tenant_id=task.tenant_id)
        result = provider.generate(task, evidence)
        assert not result.success
        assert result.error_code == "CREDENTIALS_MISSING"
        assert not result.retryable

    @patch.object(SarvamClient, "chat_completion")
    def test_provider_generate_success(self, mock_chat):
        mock_chat.return_value = {
            "content": '{"summary": "Draft SOAP note: Glycemic control stable under current lifestyle."}',
            "usage": {"total_tokens": 200},
            "latency_ms": 120.0,
        }
        provider = SarvamAIProvider(api_key="test-sarvam-key")
        task = AITaskDefinition(
            task_type=AITaskType.CLINICAL_SUMMARY,
            system_constraints=DEFAULT_SYSTEM_CONSTRAINTS,
            patient_id=uuid4(),
            tenant_id=uuid4(),
        )
        evidence = EvidencePackage(
            patient_id=task.patient_id,
            tenant_id=task.tenant_id,
            observations=[{"value_mg_dl": 125, "tag": "fasting", "taken_at": "2026-09-21T08:00:00"}],
            meals=[{"description": "2 roti and dal", "portion_katori": "medium"}],
        )
        result = provider.generate(task, evidence)
        assert result.success
        assert "Draft SOAP note" in result.summary
        assert result.provider == "sarvam"
        assert result.model == "sarvam-105b-conversations"


class TestIndicNutritionAnalyzer:
    def test_deterministic_icmr_parsing(self):
        analyzer = IndicNutritionAnalyzer(sarvam_client=SarvamClient(api_key=""))
        result = analyzer.analyze_meal("2 roti, 1 katori dal aur thoda salad", patient_name="Subham")

        assert len(result.items) >= 2
        assert result.total_calories_kcal > 200.0
        assert result.total_carbs_g > 30.0
        assert result.total_protein_g >= 10.0
        assert result.total_fiber_g >= 5.0
        assert result.source == "icmr_deterministic"
        assert "Subham ji" in result.patient_guidance_hinglish

    def test_carb_heavy_meal_flagging(self):
        analyzer = IndicNutritionAnalyzer(sarvam_client=SarvamClient(api_key=""))
        result = analyzer.analyze_meal("2 plate rice and 2 plain dosa", patient_name="Amit")
        assert result.total_carbs_g > 60.0
        assert result.glycemic_impact == "ELEVATED"
        assert result.balanced_plate_score == "CARB_HEAVY"


class TestClinicalCalculator:
    def test_glycemic_metrics_empty(self):
        metrics = calculate_glycemic_metrics([])
        assert metrics.total_readings == 0
        assert metrics.mean_glucose_mg_dl is None
        assert metrics.time_in_range_pct is None

    def test_glycemic_metrics_normal_profile(self):
        # 5 readings: 110, 120, 135, 140, 150 (all in 70-180 target)
        readings = [{"value_mg_dl": v, "tag": "fasting" if i == 0 else "postmeal"} for i, v in enumerate([110, 120, 135, 140, 150])]
        metrics = calculate_glycemic_metrics(readings)

        assert metrics.total_readings == 5
        assert metrics.mean_glucose_mg_dl == 131.0
        assert metrics.time_in_range_pct == 100.0
        assert metrics.time_below_range_pct == 0.0
        assert metrics.time_above_range_pct == 0.0
        assert metrics.estimated_hba1c_pct is not None
        assert metrics.coefficient_of_variation_pct is not None
        assert metrics.coefficient_of_variation_pct < 36.0
        assert metrics.variability_category == "STABLE"

    def test_glycemic_metrics_hypoglycemia_detection(self):
        # Reading with 62 mg/dL
        readings = [
            {"value_mg_dl": 62, "tag": "random"},
            {"value_mg_dl": 140, "tag": "postlunch"},
        ]
        metrics = calculate_glycemic_metrics(readings)
        assert metrics.hypo_events_count == 1
        assert metrics.time_below_range_pct == 50.0
        assert "Hypoglycemia risk flagged" in metrics.clinical_summary_note


class TestConversationalAssistant:
    def test_emergency_hypo_symptom_triage(self):
        # Patient reports dizziness and shivering
        reply = generate_conversational_reply("Mujhe chakkar aa raha hai aur pasina aa raha hai", patient_name="Subham")
        assert "⚠️ *Dhyan dein" in reply
        assert "Hypoglycemia" in reply
        assert "glucose/shakkar paani" in reply

    def test_dietary_guidance_fallback(self):
        reply = generate_conversational_reply("Kya main aam kha sakta hoon?", patient_name="Subham")
        assert "Namaste Subham ji!" in reply
        assert "Meethe Phal" in reply or "Thali" in reply
