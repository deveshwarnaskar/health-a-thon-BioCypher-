"""Sarvam AI provider adapters (additive multimodal layer).

Thin, provider-neutral adapters over ``SarvamClient`` that implement the
protocols in ``backend.application.ports.ai_multimodal``. These classes are pure
signal converters:

- They make no domain decisions, create no events, mutate no observations, and
  never compute canonical nutrition.
- Their outputs (transcripts, translations, candidates) are just *candidates*
  that still round-trip through the deterministic taxonomy and the patient
  confirmation loop.
- Errors are surfaced as ``AIMultimodalError`` so the ingestion use case decides
  retryability; no PHI or raw bytes are ever logged.

Existing behaviour is untouched: ``SarvamConversationProvider`` (chat layer) and
the clinical ``ProductionModelProvider``/``AIProvider`` flow remain as-is. These
adapters only ADD the multimodal capabilities.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.application.ports.ai_multimodal import (
    AIMultimodalError,
    ImageAnalysisProvider,
    ImageAnalysisResult,
    LanguageIdentifier,
    MediaProvenance,
    SpeechToTextProvider,
    TextToSpeechProvider,
    TranscriptionResult,
    TranslationProvider,
    UnsupportedMediaError,
)
from backend.infrastructure.ai.sarvam_client import SarvamClient, SarvamClientError

logger = logging.getLogger(__name__)


def _wrap(method: str, exc: BaseException, *, retryable: bool) -> AIMultimodalError:
    if isinstance(exc, AIMultimodalError):
        return exc
    return AIMultimodalError(
        f"sarvam {method} failed: {exc}",
        retryable=retryable,
        provider="sarvam",
    )


class SarvamSpeechToTextProvider:
    """Saaras ASR v3 voice note → Hinglish/Indic transcript adapter."""

    def __init__(
        self,
        client: SarvamClient | None = None,
        *,
        model: str = "",
        language_code: str = "unknown",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._client = client or SarvamClient()
        self._model = model or self._client.default_asr_model or "saaras:v3"
        self._language_code = language_code
        if timeout_seconds:
            self._client.timeout = timeout_seconds

    def transcribe(self, audio_bytes: bytes, mime_type: str) -> TranscriptionResult:
        if not audio_bytes:
            raise UnsupportedMediaError("empty audio payload", provider="sarvam")
        try:
            res = self._client.transcribe_audio(
                audio_bytes,
                filename="voice_note.bin",
                mime_type=mime_type or "audio/ogg",
                language_code=self._language_code,
                model=self._model,
            )
        except SarvamClientError as exc:
            raise _wrap("speech-to-text", exc, retryable=bool(exc.retryable)) from exc
        except Exception as exc:  # noqa: BLE001 - adapter boundary
            raise _wrap("speech-to-text", exc, retryable=True) from exc

        transcript = str(res.get("transcript") or "")
        language = str(res.get("language_code") or "")
        latency = float(res.get("latency_ms") or 0.0)
        return TranscriptionResult(
            transcript=transcript.strip(),
            language_code=language,
            quality="high" if transcript.strip() else "low",
            provenance=MediaProvenance(
                provider="sarvam",
                model=self._model,
                language_code=language,
                quality="high" if transcript.strip() else "low",
                latency_ms=latency,
            ),
        )


class SarvamLanguageIdentifier:
    """Language identification for short Indic/Hinglish transcripts.

    Saaras v3 already reports ``language_code`` per utterance inside the ASR
    response, so the STT adapter's ``TranscriptionResult.language_code`` is the
    primary source. This adapter is the deterministic port fallback for text
    that arrives without ASR metadata: Devanagari script → ``hi-IN``,
    otherwise ``en-IN`` (Hinglish in Latin script defaults to ``en-IN``).
    """

    def __init__(self, client: SarvamClient | None = None) -> None:
        self._client = client or SarvamClient()
        self._dev_script = range(0x0900, 0x0980)  # Devanagari block

    def identify(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        if any(ord(ch) in self._dev_script for ch in text):
            return "hi-IN"
        return "en-IN"


class SarvamTranslationProvider:
    """Mayura v1 bilingual translation adapter (en-IN ↔ hi-IN)."""

    def __init__(
        self,
        client: SarvamClient | None = None,
        *,
        model: str = "mayura:v1",
    ) -> None:
        self._client = client or SarvamClient()
        self._model = model

    def translate(
        self,
        text: str,
        target_language_code: str = "hi-IN",
        source_language_code: str = "en-IN",
    ) -> str:
        if not text or not text.strip():
            return ""
        try:
            res = self._client.translate(
                text,
                source_language_code=source_language_code,
                target_language_code=target_language_code,
                model=self._model,
            )
        except SarvamClientError as exc:
            raise _wrap("translate", exc, retryable=bool(exc.retryable)) from exc
        except Exception as exc:  # noqa: BLE001 - adapter boundary
            raise _wrap("translate", exc, retryable=True) from exc
        return str(res.get("translated_text") or "")


class SarvamTextToSpeechProvider:
    """Bulbul v3 TTS adapter returning PCM/WAV audio bytes."""

    def __init__(
        self,
        client: SarvamClient | None = None,
        *,
        model: str = "",
        speaker: str = "priya",
    ) -> None:
        self._client = client or SarvamClient()
        self._model = model or self._client.default_tts_model or "bulbul:v3"
        self._speaker = speaker

    def synthesize(self, text: str, language_code: str = "hi-IN", voice: str = "") -> bytes:
        import base64

        if not text or not text.strip():
            return b""
        try:
            res = self._client.text_to_speech(
                text,
                target_language_code=language_code,
                speaker=voice or self._speaker,
                model=self._model,
            )
        except SarvamClientError as exc:
            raise _wrap("text-to-speech", exc, retryable=bool(exc.retryable)) from exc
        except Exception as exc:  # noqa: BLE001 - adapter boundary
            raise _wrap("text-to-speech", exc, retryable=True) from exc
        b64 = str(res.get("audio_base64") or "")
        if not b64:
            raise AIMultimodalError(
                "sarvam text-to-speech returned no audio",
                retryable=False,
                provider="sarvam",
            )
        try:
            return base64.b64decode(b64)
        except Exception as exc:  # noqa: BLE001 - adapter boundary
            raise _wrap("text-to-speech", exc, retryable=False) from exc


class SarvamChatProvider:
    """Sarvam-105B chat completion adapter implementing the ChatProvider seam.

    Addresses conversational/product helper prompts (NO clinical interpretation).
    """

    def __init__(
        self,
        client: SarvamClient | None = None,
        *,
        model: str = "",
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> None:
        self._client = client or SarvamClient()
        self._model = model or self._client.default_model or "sarvam-105b-conversations"
        self._temperature = temperature
        self._max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        if not user or not user.strip():
            return ""
        if not self._client.is_configured:
            raise AIMultimodalError(
                "sarvam API key is not configured",
                retryable=False,
                provider="sarvam",
            )
        try:
            res = self._client.chat_completion(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                model=self._model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
        except SarvamClientError as exc:
            raise _wrap("chat-completion", exc, retryable=bool(exc.retryable)) from exc
        except Exception as exc:  # noqa: BLE001 - adapter boundary
            raise _wrap("chat-completion", exc, retryable=True) from exc
        return str(res.get("content") or "")


__all__ = [
    "SarvamSpeechToTextProvider",
    "SarvamLanguageIdentifier",
    "SarvamTranslationProvider",
    "SarvamTextToSpeechProvider",
    "SarvamChatProvider",
    "ImageAnalysisResult",  # re-export for convenience
]