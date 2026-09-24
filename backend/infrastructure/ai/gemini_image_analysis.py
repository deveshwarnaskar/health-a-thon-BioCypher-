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
        model_name: str = "gemini-3-flash-preview",
        base_url: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if api_key is not None:
            resolved_key = api_key
        else:
            resolved_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("THALI_AI__API_KEY")
            if not resolved_key:
                try:
                    from config.settings import Settings
                    settings = Settings()
                    resolved_key = getattr(settings.ai, "api_key", "")
                except Exception:
                    resolved_key = ""
        self.api_key = (resolved_key or "").strip()
        if model_name in (
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-flash-lite-latest",
            "gemini-2.5-flash",
        ):
            model_name = "gemini-3-flash-preview"
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

        clean_mime = (mime_type or "image/jpeg").lower().strip()
        if clean_mime in ("image/jpg", "image/pjpeg"):
            clean_mime = "image/jpeg"

        # Image size optimization: thumbnail large mobile camera uploads to prevent network timeouts
        try:
            import io
            from PIL import Image

            if len(image_bytes) > 400_000:
                pil_img = Image.open(io.BytesIO(image_bytes))
                if pil_img.mode in ("RGBA", "P"):
                    pil_img = pil_img.convert("RGB")
                pil_img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                out_buf = io.BytesIO()
                pil_img.save(out_buf, format="JPEG", quality=85)
                image_bytes = out_buf.getvalue()
                clean_mime = "image/jpeg"
        except Exception as img_err:
            logger.debug("Image resize pass skipped: %s", img_err)

        start_time = time.monotonic()
        encoded = base64.b64encode(image_bytes).decode("ascii")

        request_body = {
            "contents": [
                {
                    "parts": [
                        {"text": _PROMPT},
                        {"inline_data": {"mime_type": clean_mime, "data": encoded}},
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 800},
        }

        data = json.dumps(request_body).encode("utf-8")

        candidate_models = [self.model_name]
        for fallback in ("gemini-3-flash-preview", "gemini-flash-latest", "gemini-3.5-flash"):
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        payload = None
        used_model = self.model_name
        latency = 0.0

        for model in candidate_models:
            for attempt in range(2):
                endpoint = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
                if not endpoint.startswith(("https://", "http://")):
                    raise AIMultimodalError("endpoint must use http or https scheme", retryable=False, provider=self.provider_name)

                req = urllib.request.Request(
                    endpoint,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # nosec B310 - guarded scheme above
                        status_code = resp.status
                        resp_bytes = resp.read()
                        latency = (time.monotonic() - start_time) * 1000.0
                        if status_code in (200, 201):
                            payload = json.loads(resp_bytes.decode("utf-8"))
                            used_model = model
                            break
                        elif status_code in (429, 503) and attempt == 0:
                            time.sleep(1.5)
                            continue
                        else:
                            raise AIMultimodalError(
                                f"gemini HTTP {status_code}",
                                retryable=status_code >= 500,
                                provider=self.provider_name,
                            )
                except urllib.error.HTTPError as exc:
                    latency = (time.monotonic() - start_time) * 1000.0
                    if exc.code in (429, 503) and attempt == 0:
                        time.sleep(1.5)
                        continue
                    logger.warning("gemini image analysis HTTPError on model %s: %s %s", model, exc.code, exc.reason)
                    break
                except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
                    latency = (time.monotonic() - start_time) * 1000.0
                    logger.warning("gemini image analysis network error on model %s: %s", model, exc)
                    if attempt == 0:
                        time.sleep(1.0)
                        continue
                    break
                except (ValueError, json.JSONDecodeError) as exc:
                    latency = (time.monotonic() - start_time) * 1000.0
                    logger.warning("gemini image analysis unparseable response")
                    raise AIMultimodalError(
                        "gemini returned malformed JSON",
                        retryable=False,
                        provider=self.provider_name,
                    ) from exc
            if payload is not None:
                break

        if payload is None:
            raise AIMultimodalError(
                "gemini image analysis service temporarily unavailable",
                retryable=True,
                provider=self.provider_name,
            )

        text = _extract_text(payload)
        parsed = _parse_candidates_json(text)

        provenance = MediaProvenance(
            provider=self.provider_name,
            model=used_model,
            quality=parsed.get("confidence", "low"),
            latency_ms=latency or (time.monotonic() - start_time) * 1000.0,
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
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z]*\s*", "", candidate)
        candidate = re.sub(r"\s*```[\s\S]*$", "", candidate)
        candidate = candidate.strip()
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