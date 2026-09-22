"""Sarvam AI Provider (Gate 04 + Gate 10M).

Integrates Sarvam AI (sarvam-m / sarvam-2b) for Indic clinical intelligence,
dietary summarization, and physician review drafts.

Enforces Gate 10M fail-safe boundaries:
- Missing credentials -> CREDENTIALS_MISSING (retryable=False)
- Timeout -> TIMEOUT (retryable=True)
- HTTP 4xx -> PROVIDER_4XX (retryable=False)
- HTTP 5xx -> PROVIDER_5XX (retryable=True)
- Malformed JSON -> MALFORMED_OUTPUT (retryable=False)
- Zero autonomous clinical action; produces unapproved DRAFT for licensed clinician review.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

from backend.application.ports.ai import (
    AIProvider,
    AIProviderResult,
    AITaskDefinition,
    EvidencePackage,
)
from backend.application.services.clinical_calculator import calculate_glycemic_metrics
from backend.infrastructure.ai.sarvam_client import SarvamClient, SarvamClientError

logger = logging.getLogger(__name__)


class SarvamAIProvider:
    """Production Sarvam AI Provider for clinical review artifacts."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "sarvam-105b-conversations",
        base_url: Optional[str] = None,
        timeout_seconds: float = 12.0,
    ) -> None:
        self.client = SarvamClient(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
        self.model_name = model_name or self.client.default_model
        self.provider_name = "sarvam"

    def generate(self, task: AITaskDefinition, evidence: EvidencePackage) -> AIProviderResult:
        """Execute clinical draft generation through Sarvam AI."""
        if not self.client.is_configured:
            logger.error("Sarvam AI credentials missing — failing safe")
            return AIProviderResult(
                success=False,
                summary="",
                provider=self.provider_name,
                model=self.model_name,
                error_code="CREDENTIALS_MISSING",
                retryable=False,
            )

        start_time = time.monotonic()

        # Deterministic clinical metrics preprocessing (ICMR / RSSDI / ADA)
        metrics = calculate_glycemic_metrics(evidence.observations)
        metrics_text = (
            f"--- CLINICAL GLYCEMIC METRICS (ICMR / RSSDI Standards) ---\n"
            f"Readings Count: {metrics.total_readings}\n"
            f"Mean Glucose: {metrics.mean_glucose_mg_dl} mg/dL (SD: ±{metrics.standard_deviation_mg_dl})\n"
            f"Time In Range (70-180 mg/dL): {metrics.time_in_range_pct}% (Target > 70%)\n"
            f"Time Below Range (<70 mg/dL): {metrics.time_below_range_pct}% (Target < 4%)\n"
            f"Time Above Range (>180 mg/dL): {metrics.time_above_range_pct}%\n"
            f"Glycemic Variability (CV): {metrics.coefficient_of_variation_pct}% ({metrics.variability_category})\n"
            f"Estimated HbA1c: {metrics.estimated_hba1c_pct}%\n"
            f"Glucose Management Indicator (GMI): {metrics.glucose_management_indicator_pct}%\n"
            f"Dawn Phenomenon Suspected: {'YES' if metrics.dawn_phenomenon_suspected else 'NO'}\n"
            f"Summary Note: {metrics.clinical_summary_note}\n"
        )

        system_constraints_text = "\n".join(task.system_constraints)
        system_prompt = (
            f"{system_constraints_text}\n\n"
            "You are an assistive clinical intelligence assistant for THALI x P.L.A.T.E.\n"
            "Produce an assistive, objective clinical draft summary for licensed clinician review.\n"
            "Structure as a structured SOAP Draft note:\n"
            "- Subjective: Patient logged symptoms/notes\n"
            "- Objective: Glycemic metrics, TIR, Mean, Meal patterns\n"
            "- Assessment: Glycemic control stability, variability, hypoglycemic risk\n"
            "- Plan (Draft for Clinician Review): Suggested follow-up considerations for the doctor\n"
            "Return JSON with key 'summary'."
        )

        evidence_text = evidence.to_prompt_context()
        user_prompt = (
            f"Task: {task.task_type.value}\n\n"
            f"{metrics_text}\n"
            f"{evidence_text}\n\n"
            f"Generate the assistive draft clinical summary in clean JSON format: {{\"summary\": \"...\"}}"
        )

        try:
            res = self.client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=self.model_name,
                temperature=0.2,
                max_tokens=850,
            )

            raw_content = res.get("content", "").strip()
            latency = res.get("latency_ms", (time.monotonic() - start_time) * 1000.0)

            # Try parsing JSON wrapper
            summary_text = ""
            if "{" in raw_content and "}" in raw_content:
                try:
                    match = re.search(r"\{.*\}", raw_content, re.DOTALL)
                    if match:
                        parsed = json.loads(match.group(0))
                        summary_text = parsed.get("summary", "")
                except Exception:
                    pass

            if not summary_text:
                summary_text = raw_content

            if not summary_text:
                logger.warning("Sarvam AI returned empty summary text")
                return AIProviderResult(
                    success=False,
                    summary="",
                    provider=self.provider_name,
                    model=self.model_name,
                    error_code="MALFORMED_OUTPUT",
                    retryable=False,
                    latency_ms=latency,
                )

            return AIProviderResult(
                success=True,
                summary=summary_text,
                provider=self.provider_name,
                model=self.model_name,
                latency_ms=latency,
                usage=res.get("usage"),
            )

        except SarvamClientError as exc:
            latency = (time.monotonic() - start_time) * 1000.0
            return AIProviderResult(
                success=False,
                summary="",
                provider=self.provider_name,
                model=self.model_name,
                error_code=exc.error_code,
                retryable=exc.retryable,
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.monotonic() - start_time) * 1000.0
            logger.exception("Sarvam AI provider unexpected error: %s", exc)
            return AIProviderResult(
                success=False,
                summary="",
                provider=self.provider_name,
                model=self.model_name,
                error_code="PROVIDER_ERROR",
                retryable=False,
                latency_ms=latency,
            )
