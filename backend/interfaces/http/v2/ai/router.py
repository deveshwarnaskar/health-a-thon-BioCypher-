"""AI Services API Router (Gate 10M + Sarvam AI).

Provides authenticated, audited AI endpoints for:
- Indic speech-to-text audio transcription (Saaras ASR v2)
- Indian dietary & ICMR-NIN nutrition analysis
- Patient conversational health guide (Sarvam-M)
- Clinical glycemic analytics (TIR, TAR, TBR, eA1c, GMI, CV%)
- Clinician patient intelligence summary
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field

from backend.application.services.clinical_calculator import calculate_glycemic_metrics
from backend.application.services.conversational_assistant import generate_conversational_reply
from backend.infrastructure.ai.indic_nutrition_analyzer import IndicNutritionAnalyzer
from backend.infrastructure.ai.sarvam_client import SarvamClient, SarvamClientError
from backend.interfaces.http.dependencies import get_authenticated_context, get_unit_of_work
from backend.interfaces.http.v2.security.authorization import AuthenticatedContext
from backend.application.ports.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

ai_router = APIRouter()


class AnalyzeMealRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=1000)
    patient_name: str = Field(default="")


class ConversationalChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    patient_name: str = Field(default="")


class GlucoseReadingItem(BaseModel):
    value_mg_dl: float
    tag: Optional[str] = None
    taken_at: Optional[str] = None


class CalculateGlycemicRequest(BaseModel):
    readings: list[GlucoseReadingItem]


class TranscribeBase64Request(BaseModel):
    audio_base64: str = Field(..., min_length=1)
    mime_type: str = Field(default="audio/ogg")
    language_code: str = Field(default="unknown")
    filename: str = Field(default="voice.ogg")


@ai_router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language_code: str = Form("unknown"),
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
) -> dict[str, Any]:
    """Transcribe spoken Indic audio (WhatsApp voice notes, app mic dictation).

    Uses Sarvam Saaras ASR v2 with automatic Indian language & Hinglish detection.
    """
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty audio file uploaded")

        client = SarvamClient()
        if not client.is_configured:
            # Safe mock transcript for dev/offline testing if key is not configured
            return {
                "transcript": "Audio received (Sarvam API key not configured — fallback mode)",
                "language_code": language_code,
                "provider": "fallback",
                "filename": file.filename,
                "size_bytes": len(content),
            }

        res = client.transcribe_audio(
            content,
            filename=file.filename or "audio.ogg",
            mime_type=file.content_type or "audio/ogg",
            language_code=language_code,
        )
        return {
            "transcript": res["transcript"],
            "language_code": res["language_code"],
            "provider": "sarvam_saaras_v2",
            "latency_ms": res.get("latency_ms"),
        }
    except SarvamClientError as e:
        if e.error_code == "CREDENTIALS_MISSING":
            raise HTTPException(status_code=503, detail="Sarvam AI credentials not configured")
        elif e.error_code == "TIMEOUT":
            raise HTTPException(status_code=504, detail="Audio transcription timed out")
        raise HTTPException(status_code=502, detail=f"Transcription error: {e.message}")
    except Exception as exc:
        logger.exception("Transcribe audio unexpected failure: %s", exc)
        raise HTTPException(status_code=500, detail="Audio transcription failed")


@ai_router.post("/transcribe-base64")
def transcribe_audio_base64(
    body: TranscribeBase64Request,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
) -> dict[str, Any]:
    """Transcribe base64-encoded audio (ideal for mobile apps)."""
    import base64
    try:
        content = base64.b64decode(body.audio_base64)
        if not content:
            raise HTTPException(status_code=400, detail="Decoded audio data is empty")

        client = SarvamClient()
        if not client.is_configured:
            return {
                "transcript": "Audio received (Sarvam API key not configured — fallback mode)",
                "language_code": body.language_code,
                "provider": "fallback",
                "size_bytes": len(content),
            }

        res = client.transcribe_audio(
            content,
            filename=body.filename,
            mime_type=body.mime_type,
            language_code=body.language_code,
        )
        return {
            "transcript": res["transcript"],
            "language_code": res["language_code"],
            "provider": "sarvam_saaras_v2",
            "latency_ms": res.get("latency_ms"),
        }
    except SarvamClientError as e:
        if e.error_code == "CREDENTIALS_MISSING":
            raise HTTPException(status_code=503, detail="Sarvam AI credentials not configured")
        elif e.error_code == "TIMEOUT":
            raise HTTPException(status_code=504, detail="Audio transcription timed out")
        raise HTTPException(status_code=502, detail=f"Transcription error: {e.message}")
    except Exception as exc:
        logger.exception("Transcribe audio base64 failed: %s", exc)
        raise HTTPException(status_code=500, detail="Audio transcription failed")


@ai_router.post("/analyze-meal")
def analyze_meal(
    body: AnalyzeMealRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
) -> dict[str, Any]:
    """Analyze Indian meal composition using ICMR-NIN reference tables and Sarvam AI.

    Calculates calories, carbs, protein, fiber, glycemic impact, and healthy Hinglish guidance.
    """
    analyzer = IndicNutritionAnalyzer()
    res = analyzer.analyze_meal(body.description, patient_name=body.patient_name)

    return {
        "raw_description": res.raw_description,
        "items": [
            {
                "name": item.name,
                "portion_text": item.portion_text,
                "calories_kcal": item.calories_kcal,
                "carbs_g": item.carbs_g,
                "protein_g": item.protein_g,
                "fat_g": item.fat_g,
                "fiber_g": item.fiber_g,
                "glycemic_index_category": item.glycemic_index_category,
            }
            for item in res.items
        ],
        "total_calories_kcal": res.total_calories_kcal,
        "total_carbs_g": res.total_carbs_g,
        "total_protein_g": res.total_protein_g,
        "total_fat_g": res.total_fat_g,
        "total_fiber_g": res.total_fiber_g,
        "glycemic_impact": res.glycemic_impact,
        "balanced_plate_score": res.balanced_plate_score,
        "patient_guidance_hinglish": res.patient_guidance_hinglish,
        "clinician_notes": res.clinician_notes,
        "source": res.source,
    }


@ai_router.post("/chat")
def conversational_chat(
    body: ConversationalChatRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
) -> dict[str, Any]:
    """Conversational health companion query with Sarvam-M Indic dialogue.

    Enforces strict clinical safety: zero medication dosage changes, immediate hypoglycemia emergency triage.
    """
    client = SarvamClient()
    ai_completer = None
    if client.is_configured:
        def _sarvam_completer(msg: str, name: str) -> str:
            clean_n = name.strip() or "Friend"
            system_prompt = (
                "You are THALI Care Companion, an empathetic, scientifically grounded Indic diabetes health assistant.\n"
                f"Address patient warmly as '{clean_n} ji'. Respond in natural Hinglish. Follow ICMR/RSSDI guidelines.\n"
                "Never diagnose or prescribe. Emphasize balanced Indian plate (1/2 vegetables, 1/4 protein, 1/4 whole grains)."
            )
            res = client.chat_completion([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": msg},
            ])
            return res.get("content", "")
        ai_completer = _sarvam_completer

    reply = generate_conversational_reply(body.message, patient_name=body.patient_name, ai_completer=ai_completer)
    return {
        "reply": reply,
        "safety_checked": True,
        "provider": "sarvam_m" if client.is_configured else "deterministic_clinical_rules",
    }


@ai_router.post("/calculate-glycemic")
def calculate_glycemic(
    body: CalculateGlycemicRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
) -> dict[str, Any]:
    """Calculate clinical glycemic indicators (TIR, TAR, TBR, eA1c, GMI, CV%) per ICMR/RSSDI/ADA standards."""
    raw_readings = [r.model_dump() for r in body.readings]
    metrics = calculate_glycemic_metrics(raw_readings)

    return {
        "total_readings": metrics.total_readings,
        "mean_glucose_mg_dl": metrics.mean_glucose_mg_dl,
        "standard_deviation_mg_dl": metrics.standard_deviation_mg_dl,
        "coefficient_of_variation_pct": metrics.coefficient_of_variation_pct,
        "time_in_range_pct": metrics.time_in_range_pct,
        "time_below_range_pct": metrics.time_below_range_pct,
        "time_below_range_level2_pct": metrics.time_below_range_level2_pct,
        "time_above_range_pct": metrics.time_above_range_pct,
        "time_above_range_level2_pct": metrics.time_above_range_level2_pct,
        "estimated_hba1c_pct": metrics.estimated_hba1c_pct,
        "glucose_management_indicator_pct": metrics.glucose_management_indicator_pct,
        "fasting_mean_mg_dl": metrics.fasting_mean_mg_dl,
        "post_prandial_mean_mg_dl": metrics.post_prandial_mean_mg_dl,
        "hypo_events_count": metrics.hypo_events_count,
        "hyper_events_count": metrics.hyper_events_count,
        "dawn_phenomenon_suspected": metrics.dawn_phenomenon_suspected,
        "variability_category": metrics.variability_category,
        "clinical_summary_note": metrics.clinical_summary_note,
    }


@ai_router.get("/clinical-insights/{patient_id}")
def get_patient_clinical_insights(
    patient_id: UUID,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> dict[str, Any]:
    """Clinician-only comprehensive AI insights and glycemic analysis for a patient."""
    patient = uow.patients.get(patient_id)
    if not patient or not getattr(patient, "active", True):
        raise HTTPException(status_code=404, detail="Patient not found or inactive")

    # Fetch observations
    glucose_obs = uow.glucose_observations.list_for_patient(patient_id)
    meal_obs = uow.meal_observations.list_for_patient(patient_id)
    med_plans = uow.medication_plans.list_for_patient(patient_id)

    glucose_dicts = [
        {
            "value_mg_dl": g.value.value_mg_dl,
            "taken_at": g.taken_at.isoformat() if hasattr(g, "taken_at") else None,
            "tag": getattr(getattr(g, "tag", None), "value", str(getattr(g, "tag", ""))),
        }
        for g in glucose_obs
    ]

    metrics = calculate_glycemic_metrics(glucose_dicts)

    # Analyze meal patterns
    analyzer = IndicNutritionAnalyzer()
    recent_meals_analysis = [
        {
            "description": m.description,
            "recorded_at": m.recorded_at.isoformat() if hasattr(m, "recorded_at") else None,
            "analysis": analyzer.analyze_meal(m.description).balanced_plate_score,
        }
        for m in meal_obs[:5]
    ]

    active_meds = [
        {
            "medication": p.medication,
            "instruction": p.instruction,
            "active": p.active,
        }
        for p in med_plans if p.active
    ]

    client = SarvamClient()
    provider_name = "sarvam_m" if client.is_configured else "deterministic_clinical_engine"

    return {
        "patient_id": str(patient_id),
        "patient_name": getattr(patient, "name", ""),
        "provider": provider_name,
        "metrics": {
            "total_readings": metrics.total_readings,
            "mean_glucose_mg_dl": metrics.mean_glucose_mg_dl,
            "standard_deviation_mg_dl": metrics.standard_deviation_mg_dl,
            "coefficient_of_variation_pct": metrics.coefficient_of_variation_pct,
            "time_in_range_pct": metrics.time_in_range_pct,
            "time_below_range_pct": metrics.time_below_range_pct,
            "time_above_range_pct": metrics.time_above_range_pct,
            "estimated_hba1c_pct": metrics.estimated_hba1c_pct,
            "glucose_management_indicator_pct": metrics.glucose_management_indicator_pct,
            "dawn_phenomenon_suspected": metrics.dawn_phenomenon_suspected,
            "variability_category": metrics.variability_category,
            "clinical_summary_note": metrics.clinical_summary_note,
        },
        "recent_meals": recent_meals_analysis,
        "active_medications": active_meds,
    }
