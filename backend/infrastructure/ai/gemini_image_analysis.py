"""Gemini image analysis adapter (additive multimodal layer).

Retained Gemini as the multimodal-capable provider behind the provider-neutral
``ImageAnalysisProvider`` port because the existing ``ProductionModelProvider``
already talks to the Gemini ``generativelanguage`` REST gateway (text-only). This
adapter extends that integration to ``inline_data`` images while keeping the
exact same fail-safe boundaries: no external SDK, no hardcoded secrets,
stdlib-only transport, and structured JSON-only output.

Boundary guarantees (mirror ``ProductionModelProvider``):

- Output is a *candidate* only. The description text must still round-trip
  through the deterministic ``nutrition_taxonomy.classify_text`` /
  ``estimate_nutrition`` before any canonical observation can exist.
- Never returns computed nutrition, never mutates state, never creates events.
- Low-confidence or empty output yields ``unidentifiable=True`` and the
  ingestion use case responds with the canonical safe-copy guidance — never a
  hallucinated replacement.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from backend.application.ports.ai_multimodal import (
    AIMultimodalError,
    FoodItemCandidate,
    ImageAnalysisProvider,
    ImageAnalysisResult,
    MediaProvenance,
    UnsupportedMediaError,
)

logger = logging.getLogger(__name__)

_PROMPT = (
    "This is a meal photo taken on a phone in India. List the food items you can "
    "clearly see and a rough serving size for each. Verbatim JSON ONLY in this "
    'shape: {"items":[{"name":"<Hinglish food name like \"2 roti\" or \"dal\" or '
    '\"kofta curry\">","portion":"<serving label like \"1 katori\" or \"2 roti\">"}], '
    '"description":"<one short Hinglish plate description for the whole meal>",'
    '"confidence":"high|medium|low"}. If the photo is not food or nothing can be '
    "identified, return {\"items\":[],\"description\":\"\",\"confidence\":\"low\"}. "
    "Do NOT return or estimate any nutrition values."
)


class GeminiImageAnalysisProvider:
    """Provider-neutral ``ImageAnalysisProvider`` implemented with Gemini (vision)."""

    provider_name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-flash-lite-latest",
        base_url: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        resolved_key = (
            api_key
            if api_key is not None
            else (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("THALI_AI__API_KEY") or "")
        )
        self.api_key = resolved_key or ""
        if model_name in ("gemini-1.5-flash", "gemini-1.5-flash-latest"):
            model_name = "gemini-flash-lite-latest"
        self.model_name = model_name
        self.base_url = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        self.timeout = timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def analyze_meal(self, image_bytes: bytes, mime_type: str) -> ImageAnalysisResult:
        if not self.api_key:
            raise AIMultimodalError("gemini API key is not configured", retryable=False, provider=self.provider_name)
        if not image_bytes:
            raise UnsupportedMediaError("empty image payload", provider=self.provider_name)
        if not (mime_type or "").startswith("image/"):
            raise UnsupportedMediaError(f"unsupported image mime: {mime_type}", provider=self.provider_name)

        start_time = time.monotonic()
        endpoint = f"{self.base_url}/models/{self.model_name}:generateContent?key={self.api_key}"
        encoded = base64.b64encode(image_bytes).decode("ascii")

        request_body = {
            "contents": [
                {
                    "parts": [
                        {"inline_data": {"mime_type": mime_type or "image/jpeg", "data": encoded}},
                        {"text": _PROMPT},
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 800},
        }

        data = json.dumps(request_body).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if not endpoint.startswith(("https://", "http://")):
            raise AIMultimodalError("endpoint must use http or https scheme", retryable=False, provider=self.provider_name)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # nosec B310 - guarded scheme above
                status_code = resp.status
                resp_bytes = resp.read()
                latency = (time.monotonic() - start_time) * 1000.0
                if status_code not in (200, 201):
                    raise AIMultimodalError(
                        f"gemini HTTP {status_code}",
                        retryable=status_code >= 500,
                        provider=self.provider_name,
                    )
                payload = json.loads(resp_bytes.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            latency = (time.monotonic() - start_time) * 1000.0
            logger.warning("gemini image analysis HTTPError: %s %s", exc.code, exc.reason)
            raise AIMultimodalError(
                f"gemini HTTP {exc.code}",
                retryable=exc.code >= 500,
                provider=self.provider_name,
            ) from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
            latency = (time.monotonic() - start_time) * 1000.0
            logger.warning("gemini image analysis network error: %s", exc)
            raise AIMultimodalError(
                "gemini image analysis timed out",
                retryable=True,
                provider=self.provider_name,
            ) from exc
        except (ValueError, json.JSONDecodeError) as exc:
            latency = (time.monotonic() - start_time) * 1000.0
            logger.warning("gemini image analysis unparseable response")
            raise AIMultimodalError(
                "gemini returned malformed JSON",
                retryable=False,
                provider=self.provider_name,
            ) from exc

        text = _extract_text(payload)
        parsed = _parse_candidates_json(text)

        provenance = MediaProvenance(
            provider=self.provider_name,
            model=self.model_name,
            quality=parsed.get("confidence", "low"),
            latency_ms=(time.monotonic() - start_time) * 1000.0 if not latency else latency,
        )

        items: list[FoodItemCandidate] = []
        for item in parsed.get("items") or []:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            # Reject any candidate that looks like a nutrition number rather than a food name
            if re.fullmatch(r"[\d.]+", name):
                continue
            items.append(FoodItemCandidate(name=name, portion=str(item.get("portion") or "").strip()))

        confidence = str(parsed.get("confidence") or "low").lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"
        description = str(parsed.get("description") or "").strip()

        unidentifiable = bool(not items)
        return ImageAnalysisResult(
            items=tuple(items),
            description=description,
            confidence=confidence,
            unidentifiable=unidentifiable,
            provenance=provenance,
        )


def _extract_text(payload: dict) -> str:
    """Pull the model text from a Gemini ``generateContent`` response."""
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    if not parts or not isinstance(parts[0], dict):
        return ""
    return str(parts[0].get("text") or "").strip()


def _parse_candidates_json(raw: str) -> dict:
    """Best-effort JSON extraction. Any failure yields an empty safe result."""
    if not raw:
        return {}
    candidate = raw
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z]*\n?", "", candidate)
        candidate = re.sub(r"\n?```$", "", candidate)
    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data
    except (ValueError, json.JSONDecodeError):
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    return data
            except (ValueError, json.JSONDecodeError):
                pass
    return {}


__all__ = ["GeminiImageAnalysisProvider", "ImageAnalysisResult"]