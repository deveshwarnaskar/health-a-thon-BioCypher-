# Sarvam AI Indic Platform Integration

## Integration Guide: Saaras v3 ASR, Mayura v1 Translation, Bulbul v3 TTS, and Sarvam-105B

---

## 1. Overview

[Sarvam AI](https://sarvam.ai) provides specialized Indic models tailored for Indian linguistic nuances, dialectal code-mixing (Hinglish, Tamil-English, Bengali-English), and cultural contexts. In **THALI × P.L.A.T.E.**, Sarvam is leveraged across three distinct layers:
1. **Multimodal Telemetry Intake**: Voice note transcription (`SarvamSpeechToTextProvider`).
2. **Ambient Companion / Onboarding**: Conversational healthcare guidance in Hinglish (`SarvamChatProvider`).
3. **Clinical Draft Preparation**: Dietary and glycemic clinical summarization (`SarvamAIProvider`).

---

## 2. Implemented Adapters

The adapters reside in [`backend/infrastructure/ai/sarvam_providers.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master%20copy/backend/infrastructure/ai/sarvam_providers.py) and [`backend/infrastructure/ai/sarvam_provider.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master%20copy/backend/infrastructure/ai/sarvam_provider.py):

### A. `SarvamSpeechToTextProvider` (Saaras v3)
- **Model**: `saaras:v3` (ASR optimized for 10+ Indian languages and code-mixed speech).
- **Endpoint**: `POST /speech-to-text`
- **Behavior**: Transcribes raw audio bytes into Indic/Latin text and reports `language_code` and processing latency.

### B. `SarvamLanguageIdentifier`
- **Strategy**: Primary language detection is reported by Saaras v3 ASR. When processing raw text without audio context, a deterministic Unicode block analyzer detects Devanagari (`\u0900-\u097F`) as `hi-IN` and Latin script as `en-IN` (Hinglish standard).

### C. `SarvamTranslationProvider` (Mayura v1)
- **Model**: `mayura:v1`
- **Endpoint**: `POST /translate`
- **Capability**: Bidirectional translation between Indian English (`en-IN`) and Hindi (`hi-IN`).

### D. `SarvamTextToSpeechProvider` (Bulbul v3)
- **Model**: `bulbul:v3`
- **Endpoint**: `POST /text-to-speech`
- **Voice**: Standard female voice (`"priya"`). Returns decoded binary audio bytes (WAV/MP3).

### E. `SarvamAIProvider` (Gate 04 & 10M)
- **Model**: `sarvam-105b-conversations` / `sarvam-m`
- **Role**: Summarizes glycemic evidence packages for doctors into structured draft SOAP notes.

---

## 3. Fail-Safe Error Handling Matrix

Every network call through `SarvamClient` is mapped deterministically:

| Provider Error | HTTP Code / Cause | `SarvamClientError.error_code` | Retryable | Ingestion Handler Action |
| :--- | :--- | :--- | :--- | :--- |
| Missing API Key | Client not configured | `CREDENTIALS_MISSING` | `False` | Fails safe to `LOW_CONFIDENCE_GUIDANCE` |
| Read/Connect Timeout | Network timeout (>15s) | `TIMEOUT` | `True` | Backoff retry via outbox worker |
| Rate Limit | HTTP 429 Too Many Requests | `RATE_LIMITED` | `True` | Backoff retry, metric counter increment |
| Bad Request | HTTP 400 Malformed payload | `PROVIDER_4XX` | `False` | Permanent failure, log audit, safe copy reply |
| Server Error | HTTP 500/502/503 | `PROVIDER_5XX` | `True` | Backoff retry via outbox worker |
| Malformed JSON | Non-JSON response body | `MALFORMED_OUTPUT` | `False` | Permanent failure, fallback to safe copy |

---

## 4. Configuration & Secrets

Keys are loaded from environment variables or settings:
- `SARVAM_API_KEY`: API authentication key (bearer token).
- `SARVAM_MODEL`: Default chat model (default: `sarvam-105b-conversations`).
- `SARVAM_BASE_URL`: API gateway endpoint (default: `https://api.sarvam.ai`).
- `SARVAM_ENABLED`: Boolean flag activating the multimodal bundle (`true`/`false`).
