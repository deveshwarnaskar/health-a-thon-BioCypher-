"""Sarvam AI Client for Indic Speech, LLM, Translation & Audio Workflows.

Integrates with Sarvam AI REST endpoints:
- Speech-to-Text (Saaras ASR v2): Hinglish & 10+ Indic languages transcription
- Chat Completions (Sarvam-M / Sarvam-2B): Empathetic Indic clinical & dietary reasoning
- Translation (Mayura v1): Indic-English bilingual translation
- Text-to-Speech (Bulbul v1): Indic voice synthesis

Follows Gate 10M fail-safe boundaries:
- Missing credentials -> CREDENTIALS_MISSING (retryable=False)
- Network/timeout -> TIMEOUT (retryable=True)
- HTTP 4xx -> PROVIDER_4XX (retryable=False)
- HTTP 5xx -> PROVIDER_5XX (retryable=True)
- Malformed output -> MALFORMED_OUTPUT (retryable=False)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional
import httpx

from config.settings import Settings

logger = logging.getLogger(__name__)


class SarvamClientError(Exception):
    """Base exception for Sarvam AI errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "PROVIDER_ERROR",
        status_code: Optional[int] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.retryable = retryable


class SarvamClient:
    """Client for Sarvam AI Indic API suite."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        settings = Settings()
        if api_key is not None:
            self.api_key = api_key.strip()
        else:
            self.api_key = (
                settings.ai.sarvam_api_key
                or (settings.ai.api_key if settings.ai.provider == "sarvam" else "")
            ).strip()
        self.base_url = (base_url or settings.ai.sarvam_base_url or "https://api.sarvam.ai").rstrip("/")
        self.timeout = timeout_seconds
        self.default_model = settings.ai.sarvam_model or "sarvam-105b-conversations"
        self.default_asr_model = settings.ai.sarvam_asr_model or "saaras:v3"
        self.default_tts_model = settings.ai.sarvam_tts_model or "bulbul:v3"

    @property
    def is_configured(self) -> bool:
        """Returns True if a valid Sarvam API key is available."""
        return bool(self.api_key)

    def _get_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise SarvamClientError("Sarvam API key is not configured", error_code="CREDENTIALS_MISSING", retryable=False)
        return {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> dict[str, Any]:
        """Execute chat completion request using Sarvam-M or specified Indic model."""
        if not self.api_key:
            raise SarvamClientError("Sarvam API key is not configured", error_code="CREDENTIALS_MISSING", retryable=False)

        model_to_use = model or self.default_model
        endpoint = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model_to_use,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        start_time = time.monotonic()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    endpoint,
                    json=payload,
                    headers=self._get_headers(),
                )
                latency_ms = (time.monotonic() - start_time) * 1000.0

                if response.status_code not in (200, 201):
                    logger.warning("Sarvam chat completion returned HTTP %s: %s", response.status_code, response.text[:200])
                    code = "PROVIDER_5XX" if response.status_code >= 500 else "PROVIDER_4XX"
                    raise SarvamClientError(
                        f"Sarvam HTTP {response.status_code}: {response.text[:100]}",
                        error_code=code,
                        status_code=response.status_code,
                        retryable=response.status_code >= 500 or response.status_code == 429,
                    )

                data = response.json()
                choices = data.get("choices") or []
                content = ""
                if choices and isinstance(choices, list):
                    msg = choices[0].get("message") or {}
                    content = msg.get("content", "")

                return {
                    "content": content,
                    "model": model_to_use,
                    "usage": data.get("usage"),
                    "latency_ms": latency_ms,
                    "raw": data,
                }

        except httpx.TimeoutException as exc:
            logger.warning("Sarvam chat completion timed out after %ss", self.timeout)
            raise SarvamClientError("Sarvam API timed out", error_code="TIMEOUT", retryable=True) from exc
        except httpx.RequestError as exc:
            logger.warning("Sarvam chat request failed: %s", exc)
            raise SarvamClientError(f"Network error connecting to Sarvam: {exc}", error_code="PROVIDER_ERROR", retryable=True) from exc
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Sarvam returned malformed JSON")
            raise SarvamClientError("Sarvam returned malformed JSON", error_code="MALFORMED_OUTPUT", retryable=False) from exc

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "voice_note.ogg",
        mime_type: str = "audio/ogg",
        language_code: str = "unknown",
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """Transcribe Indic/Hinglish speech to text using Sarvam Saaras ASR."""
        if not self.api_key:
            raise SarvamClientError("Sarvam API key is not configured", error_code="CREDENTIALS_MISSING", retryable=False)

        endpoint = f"{self.base_url}/speech-to-text"
        asr_model = model or self.default_asr_model
        headers = {"api-subscription-key": self.api_key}

        # Normalize MIME types: strip parameters like ';codecs=opus' and map mobile audio containers
        raw_mime = (mime_type or "audio/ogg").lower().strip()
        base_mime = raw_mime.split(";")[0].strip()

        if base_mime in ("audio/m4a", "audio/x-m4a"):
            normalized_mime = "audio/x-m4a"
        elif base_mime in ("audio/webm", "video/webm"):
            normalized_mime = "audio/webm"
        elif base_mime in ("audio/mp4", "video/mp4", "audio/3gp", "audio/3gpp", "audio/amr"):
            normalized_mime = "audio/mp4"
        elif base_mime in ("audio/aac", "audio/x-aac"):
            normalized_mime = "audio/aac"
        elif base_mime in ("audio/wav", "audio/x-wav", "audio/wave"):
            normalized_mime = "audio/wav"
        elif base_mime in ("audio/ogg", "audio/opus"):
            normalized_mime = "audio/ogg"
        elif base_mime in ("audio/mpeg", "audio/mp3", "audio/mpeg3", "audio/x-mp3"):
            normalized_mime = "audio/mpeg"
        elif base_mime in ("unknown", "application/octet-stream", "", "audio/caf", "audio/x-caf"):
            lower_fn = filename.lower()
            if lower_fn.endswith(".m4a"):
                normalized_mime = "audio/x-m4a"
            elif lower_fn.endswith(".webm"):
                normalized_mime = "audio/webm"
            elif lower_fn.endswith(".mp4"):
                normalized_mime = "audio/mp4"
            elif lower_fn.endswith(".wav"):
                normalized_mime = "audio/wav"
            elif lower_fn.endswith(".ogg"):
                normalized_mime = "audio/ogg"
            elif lower_fn.endswith(".aac"):
                normalized_mime = "audio/aac"
            else:
                normalized_mime = "application/octet-stream"
        else:
            normalized_mime = "application/octet-stream"

        files = {
            "file": (filename, audio_bytes, normalized_mime),
        }
        data = {
            "model": asr_model,
            "language_code": language_code,
        }

        start_time = time.monotonic()
        try:
            with httpx.Client(timeout=max(self.timeout, 30.0)) as client:
                response = client.post(
                    endpoint,
                    files=files,
                    data=data,
                    headers=headers,
                )
                latency_ms = (time.monotonic() - start_time) * 1000.0

                if response.status_code not in (200, 201):
                    logger.warning("Sarvam ASR returned HTTP %s: %s", response.status_code, response.text[:200])
                    code = "PROVIDER_5XX" if response.status_code >= 500 else "PROVIDER_4XX"
                    raise SarvamClientError(
                        f"Sarvam ASR HTTP {response.status_code}: {response.text[:100]}",
                        error_code=code,
                        status_code=response.status_code,
                        retryable=response.status_code >= 500 or response.status_code == 429,
                    )

                res_json = response.json()
                transcript = res_json.get("transcript", "")
                detected_lang = res_json.get("language_code", language_code)

                return {
                    "transcript": transcript.strip(),
                    "language_code": detected_lang,
                    "latency_ms": latency_ms,
                    "raw": res_json,
                }

        except httpx.TimeoutException as exc:
            logger.warning("Sarvam ASR timed out")
            raise SarvamClientError("Sarvam ASR timed out", error_code="TIMEOUT", retryable=True) from exc
        except httpx.RequestError as exc:
            logger.warning("Sarvam ASR connection error: %s", exc)
            raise SarvamClientError(f"Network error in Sarvam ASR: {exc}", error_code="PROVIDER_ERROR", retryable=True) from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise SarvamClientError("Sarvam ASR returned malformed JSON", error_code="MALFORMED_OUTPUT", retryable=False) from exc

    def translate(
        self,
        text: str,
        source_language_code: str = "en-IN",
        target_language_code: str = "hi-IN",
        model: str = "mayura:v1",
        mode: str = "formal",
    ) -> dict[str, Any]:
        """Translate text between English and Indian languages."""
        if not self.api_key:
            raise SarvamClientError("Sarvam API key is not configured", error_code="CREDENTIALS_MISSING", retryable=False)

        endpoint = f"{self.base_url}/translate"
        payload = {
            "input": text,
            "source_language_code": source_language_code,
            "target_language_code": target_language_code,
            "speaker_gender": "Female",
            "mode": mode,
            "model": model,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(endpoint, json=payload, headers=self._get_headers())
                if response.status_code not in (200, 201):
                    code = "PROVIDER_5XX" if response.status_code >= 500 else "PROVIDER_4XX"
                    raise SarvamClientError(
                        f"Sarvam translate HTTP {response.status_code}",
                        error_code=code,
                        status_code=response.status_code,
                        retryable=response.status_code >= 500,
                    )
                data = response.json()
                return {
                    "translated_text": data.get("translated_text", ""),
                    "source_language": source_language_code,
                    "target_language": target_language_code,
                }
        except httpx.TimeoutException as exc:
            raise SarvamClientError("Sarvam translation timed out", error_code="TIMEOUT", retryable=True) from exc
        except httpx.RequestError as exc:
            raise SarvamClientError(f"Sarvam translation network error: {exc}", error_code="PROVIDER_ERROR", retryable=True) from exc

    def text_to_speech(
        self,
        text: str,
        target_language_code: str = "hi-IN",
        speaker: str = "priya",
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate audio from Indic text using Sarvam Bulbul TTS."""
        if not self.api_key:
            raise SarvamClientError("Sarvam API key is not configured", error_code="CREDENTIALS_MISSING", retryable=False)

        endpoint = f"{self.base_url}/text-to-speech"
        payload = {
            "inputs": [text[:500]],
            "target_language_code": target_language_code,
            "speaker": speaker,
            "model": model or self.default_tts_model,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(endpoint, json=payload, headers=self._get_headers())
                if response.status_code not in (200, 201):
                    code = "PROVIDER_5XX" if response.status_code >= 500 else "PROVIDER_4XX"
                    raise SarvamClientError(
                        f"Sarvam TTS HTTP {response.status_code}",
                        error_code=code,
                        status_code=response.status_code,
                        retryable=response.status_code >= 500,
                    )
                data = response.json()
                audios = data.get("audios") or []
                return {
                    "audio_base64": audios[0] if audios else "",
                    "target_language": target_language_code,
                }
        except httpx.TimeoutException as exc:
            raise SarvamClientError("Sarvam TTS timed out", error_code="TIMEOUT", retryable=True) from exc
        except httpx.RequestError as exc:
            raise SarvamClientError(f"Sarvam TTS network error: {exc}", error_code="PROVIDER_ERROR", retryable=True) from exc
