"""Provider-neutral multimodal AI ports (additive multimodal layer).

These Protocol seams sit behind the existing WhatsApp intake pipeline and are the
ONLY interface the application layer knows about. Concrete adapters (Sarvam,
Gemini, local/deterministic fallbacks) live in ``backend.infrastructure.ai`` and
are selected by configuration. The whole layer is strictly additive: it does not
modify or replace the existing ``AIProvider`` chat/artifact abstraction.

Invariants enforced here and by the surrounding use cases:

- Providers are *pure signal converters*. They never create domain events, never
  mutate ``MealObservation``/``MedicationPlan``, never compute canonical
  nutrition, and never bypass the intent firewall / patient confirmation /
  evidence / audit flow.
- Whatever a provider returns is a *candidate*: transcribed text and image item
  lists must still round-trip through the deterministic Hinglish parser and the
  ``classify_text`` / ``estimate_nutrition`` taxonomy before any observation can
  exist.
- Providers never log raw payload bytes or PHI. Latency, errors, and outcomes
  are surfaced through the operational metrics layer using fixed, PHI-free
  label keys.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Canonical safe-copy served whenever a provider cannot reliably identify
# content. Never replaced by model output; the pipeline returns this verbatim
# (never a hallucinated replacement) on low confidence / empty results.
# ---------------------------------------------------------------------------
LOW_CONFIDENCE_GUIDANCE = (
    "Main photo mein khana sahi se pehchan nahi paya. "
    "Kripya thoda clear photo bhejein ya khane ka naam likh kar bhejein "
    "(jaise: '2 roti dal'). Aapki sehih health record ke liye confirm hona zaroori hai."
)

VOICE_MEDIA_TYPES = frozenset({"audio", "voice", "ptt", "ogg", "amr", "mpeg", "mp3", "wav"})
IMAGE_MEDIA_TYPES = frozenset({"image", "jpeg", "jpg", "png", "webp"})

# Hard media caps enforced at the ingestion boundary (bytes).
MAX_VOICE_MEDIA_BYTES = 15_000_000
MAX_IMAGE_MEDIA_BYTES = 10_000_000

ALLOWED_VOICE_MIME_PREFIXES = ("audio/", "video/")
ALLOWED_IMAGE_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/jpg"}
)


class AIMultimodalError(RuntimeError):
    """A provider adapter failed in a retryable-or-not way.

    ``retryable`` lets the ingestion use case decide whether the whole job
    should be retried by the outbox worker or surfaced to the patient with the
    safe-copy guidance text.
    """

    def __init__(self, message: str, *, retryable: bool = False, provider: str = "") -> None:
        super().__init__(message)
        self.retryable = retryable
        self.provider = provider


class UnsupportedMediaError(AIMultimodalError):
    """The media kind / MIME / size cannot be handled by any configured adapter."""


# ---------------------------------------------------------------------------
# Provenance value object — carried by every multimodal result and threaded into
# canonical events / audit so each observation records how it was produced.
# It contains provider/model identifiers and engagement latency, never raw bytes.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MediaProvenance:
    provider: str
    model: str
    language_code: str = ""
    quality: str = ""                       # "high" | "medium" | "" (unclassified)
    latency_ms: float = 0.0
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "language_code": self.language_code,
            "quality": self.quality,
            "latency_ms": self.latency_ms,
            **_safe_details(self.details),
        }


def _safe_details(details: dict) -> dict:
    """Strip PHI-ish keys (transcripts, raw language) from provenance details."""
    forbidden = {"transcript", "raw", "text", "query", "input", "response"}
    return {k: v for k, v in dict(details).items() if k not in forbidden}


@dataclass(frozen=True)
class TranscriptionResult:
    transcript: str
    language_code: str = ""
    quality: str = ""
    provenance: MediaProvenance = field(default_factory=lambda: MediaProvenance("", ""))


@dataclass(frozen=True)
class FoodItemCandidate:
    """One name/portion hypothesis from an image. Never a nutrition value."""

    name: str                              # Hinglish food name used for taxonomy match
    portion: str = ""                      # serving descriptor ("1 katori", "2 roti")


@dataclass(frozen=True)
class ImageAnalysisResult:
    """Image → structured candidate. ``unidentifiable`` forces the safe copy."""

    items: tuple[FoodItemCandidate, ...] = ()
    description: str = ""                  # Hinglish plate description (draft text)
    confidence: str = "low"                # "high" | "medium" | "low"
    unidentifiable: bool = True
    provenance: MediaProvenance = field(default_factory=lambda: MediaProvenance("", ""))

    def to_dict(self) -> dict:
        return {
            "items": [{"name": i.name, "portion": i.portion} for i in self.items],
            "description": self.description,
            "confidence": self.confidence,
            "unidentifiable": self.unidentifiable,
        }


# ---------------------------------------------------------------------------
# Provider Protocols
# ---------------------------------------------------------------------------
@runtime_checkable
class SpeechToTextProvider(Protocol):
    def transcribe(self, audio_bytes: bytes, mime_type: str) -> TranscriptionResult: ...


@runtime_checkable
class LanguageIdentifier(Protocol):
    def identify(self, text: str) -> str: ...


@runtime_checkable
class TranslationProvider(Protocol):
    def translate(self, text: str, target_language_code: str = "hi-IN", source_language_code: str = "en-IN") -> str: ...


@runtime_checkable
class TextToSpeechProvider(Protocol):
    def synthesize(self, text: str, language_code: str = "hi-IN", voice: str = "") -> bytes: ...


@runtime_checkable
class ImageAnalysisProvider(Protocol):
    def analyze_meal(self, image_bytes: bytes, mime_type: str) -> ImageAnalysisResult: ...


@dataclass(frozen=True)
class MultimodalProviderBundle:
    """The complete optional bundle handed to the ingestion pipeline."""

    speech_to_text: SpeechToTextProvider | None = None
    language_identifier: LanguageIdentifier | None = None
    translation: TranslationProvider | None = None
    text_to_speech: TextToSpeechProvider | None = None
    image_analysis: ImageAnalysisProvider | None = None
    enabled: bool = False