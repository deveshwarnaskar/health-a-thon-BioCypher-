# Multimodal AI Architecture & Provider-Neutral Ports

## Layered Design of the WhatsApp Multimodal Ingestion Engine

---

## 1. Domain & Application Layer Ports

The application layer knows nothing about concrete vendors (such as Meta, Sarvam, Google, or OpenAI). All multimodal interactions are mediated through strict Python `Protocol` interfaces located in [`backend/application/ports/ai_multimodal.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master%20copy/backend/application/ports/ai_multimodal.py):

```python
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
```

---

## 2. Signal Converter Philosophy

Adapters implementing these protocols are treated as **pure signal converters**:
1. **Never Mutate State**: Adapters do not receive a database session, `UnitOfWork`, or repository reference.
2. **Never Emit Events**: Adapters cannot create or dispatch `DomainEvent` instances.
3. **Outputs are Candidates Only**:
   - `TranscriptionResult.transcript` is fed into the deterministic Hinglish parser.
   - `ImageAnalysisResult.description` is converted into candidate food names and passed to `nutrition_taxonomy.classify_text()`.
4. **Zero PHI Logging**: Adapters never log raw audio/image payloads, transcripts, or patient details.

---

## 3. Data Transfer Objects (DTOs)

### `MediaProvenance`
Carries model versioning, execution latency, and quality indicators without exposing user speech or imagery:
```python
@dataclass(frozen=True)
class MediaProvenance:
    provider: str
    model: str
    language_code: str = ""
    quality: str = ""                       # "high" | "medium" | "low"
    latency_ms: float = 0.0
    details: dict = field(default_factory=dict)
```

### `FoodItemCandidate` & `ImageAnalysisResult`
Captures hypotheses from food imagery:
```python
@dataclass(frozen=True)
class FoodItemCandidate:
    name: str                              # e.g., "roti", "dal", "bhindi"
    portion: str = ""                      # e.g., "2 roti", "1 katori"

@dataclass(frozen=True)
class ImageAnalysisResult:
    items: tuple[FoodItemCandidate, ...] = ()
    description: str = ""                  # e.g., "2 roti and dal"
    confidence: str = "low"                # "high" | "medium" | "low"
    unidentifiable: bool = True
    provenance: MediaProvenance = ...
```

---

## 4. Boundary Protection & Limits

Hard resource caps are strictly enforced before provider dispatch:
- **Voice Media**: Max $15\text{ MB}$ (`MAX_VOICE_MEDIA_BYTES = 15_000_000`), MIME prefix `audio/` or `video/`.
- **Image Media**: Max $10\text{ MB}$ (`MAX_IMAGE_MEDIA_BYTES = 10_000_000`), MIME allowlist: `image/jpeg`, `image/jpg`, `image/png`, `image/webp`.
- **Fail-Safe Response**: Any payload exceeding these limits or failing decryption is rejected with `LOW_CONFIDENCE_GUIDANCE` and an audit event.
