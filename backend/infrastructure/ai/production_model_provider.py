"""Production AI Model Provider (Gate 10M).

Standard-library-only (urllib) integration for production LLM APIs (e.g. Gemini / Vertex REST).
Enforces fail-safe boundaries:
- Missing credentials -> CREDENTIALS_MISSING (retryable=False)
- Timeout -> TIMEOUT (retryable=True)
- HTTP 4xx -> PROVIDER_4XX (retryable=False)
- HTTP 5xx -> PROVIDER_5XX (retryable=True)
- Malformed JSON / missing structure -> MALFORMED_OUTPUT (retryable=False)
- No hardcoded secrets, no client exposure, no external SDK.
"""

from __future__ import annotations

import json
import logging
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from backend.application.ports.ai import (
    AIProvider,
    AIProviderResult,
    AITaskDefinition,
    EvidencePackage,
)

logger = logging.getLogger(__name__)


class ProductionModelProvider:
    """Production REST model provider implemented via stdlib urllib."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-1.5-flash",
        base_url: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = api_key or ""
        self.model_name = model_name
        self.base_url = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        self.timeout = timeout_seconds
        self.provider_name = "production_gemini"

    def generate(self, task: AITaskDefinition, evidence: EvidencePackage) -> AIProviderResult:
        """Execute model request through authorized REST gateway."""
        if not self.api_key:
            logger.error("AI production credentials missing — failing safe")
            return AIProviderResult(
                success=False,
                summary="",
                provider=self.provider_name,
                model=self.model_name,
                error_code="CREDENTIALS_MISSING",
                retryable=False,
            )

        start_time = time.monotonic()
        endpoint = f"{self.base_url}/models/{self.model_name}:generateContent?key={self.api_key}"

        # Construct payload strictly separating system instructions and authorized evidence
        system_instruction_text = "\n".join(task.system_constraints)
        evidence_text = evidence.to_prompt_context()

        request_body = {
            "system_instruction": {
                "parts": [{"text": system_instruction_text}]
            },
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                f"Task: {task.task_type.value}\n\n"
                                f"{evidence_text}\n\n"
                                f"Produce an assistive clinical summary draft for human review. "
                                f"Return JSON with key 'summary'."
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 800,
            },
        }

        data = json.dumps(request_body).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        if not endpoint.startswith(("https://", "http://")):
            raise ValueError("Endpoint must use http or https scheme")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # nosec B310
                status_code = resp.status
                resp_bytes = resp.read()
                latency = (time.monotonic() - start_time) * 1000.0

                if status_code not in (200, 201):
                    logger.warning("AI provider returned unexpected HTTP %s", status_code)
                    return AIProviderResult(
                        success=False,
                        summary="",
                        provider=self.provider_name,
                        model=self.model_name,
                        error_code="PROVIDER_5XX" if status_code >= 500 else "PROVIDER_4XX",
                        retryable=status_code >= 500,
                        latency_ms=latency,
                    )

                try:
                    payload = json.loads(resp_bytes.decode("utf-8"))
                except Exception:
                    logger.warning("AI provider returned unparseable JSON")
                    return AIProviderResult(
                        success=False,
                        summary="",
                        provider=self.provider_name,
                        model=self.model_name,
                        error_code="MALFORMED_OUTPUT",
                        retryable=False,
                        latency_ms=latency,
                    )

                # Validate expected response structure
                # Either standard Gemini candidates structure or mock server {"summary": "..."}
                summary_text = ""
                if "summary" in payload and isinstance(payload["summary"], str):
                    summary_text = payload["summary"]
                elif "candidates" in payload and isinstance(payload["candidates"], list) and len(payload["candidates"]) > 0:
                    cand = payload["candidates"][0]
                    content = cand.get("content", {})
                    parts = content.get("parts", [])
                    if parts and isinstance(parts[0], dict) and "text" in parts[0]:
                        raw_text = parts[0]["text"].strip()
                        # Try parsing inner json if requested
                        if raw_text.startswith("{") and raw_text.endswith("}"):
                            try:
                                inner = json.loads(raw_text)
                                summary_text = inner.get("summary", raw_text)
                            except Exception:
                                summary_text = raw_text
                        else:
                            summary_text = raw_text

                if not summary_text:
                    logger.warning("AI provider response missing required text/summary field")
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
                    usage=payload.get("usageMetadata"),
                )

        except urllib.error.HTTPError as e:
            latency = (time.monotonic() - start_time) * 1000.0
            logger.warning("AI provider HTTPError: %s %s", e.code, e.reason)
            if 400 <= e.code < 500:
                return AIProviderResult(
                    success=False,
                    summary="",
                    provider=self.provider_name,
                    model=self.model_name,
                    error_code="PROVIDER_4XX",
                    retryable=False,
                    latency_ms=latency,
                )
            else:
                return AIProviderResult(
                    success=False,
                    summary="",
                    provider=self.provider_name,
                    model=self.model_name,
                    error_code="PROVIDER_5XX",
                    retryable=True,
                    latency_ms=latency,
                )

        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            latency = (time.monotonic() - start_time) * 1000.0
            logger.warning("AI provider network error/timeout: %s", str(e))
            return AIProviderResult(
                success=False,
                summary="",
                provider=self.provider_name,
                model=self.model_name,
                error_code="TIMEOUT",
                retryable=True,
                latency_ms=latency,
            )

        except Exception as e:
            latency = (time.monotonic() - start_time) * 1000.0
            logger.exception("AI provider unexpected error")
            return AIProviderResult(
                success=False,
                summary="",
                provider=self.provider_name,
                model=self.model_name,
                error_code="PROVIDER_ERROR",
                retryable=False,
                latency_ms=latency,
            )
