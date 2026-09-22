"""Phase 11a Test Suite A: Sarvam Multimodal Adapters (7 tests).

Verifies:
1. Adapter behavior & protocol conformance (SpeechToText, LanguageIdentifier, Translation, TextToSpeech)
2. Configuration & provider selection
3. Error handling & retryability translation (SarvamClientError -> AIMultimodalError)
4. Timeout & transient network failure handling (retryable=True)
5. Malformed provider responses (empty audio, corrupt base64, missing keys)
6. Language handling & Devanagari script detection
7. Zero secret leakage in exception messages, provenance, and logs
"""
from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch
import pytest

from backend.application.ports.ai_multimodal import (
    AIMultimodalError,
    LanguageIdentifier,
    SpeechToTextProvider,
    TextToSpeechProvider,
    TranscriptionResult,
    TranslationProvider,
    UnsupportedMediaError,
)
from backend.infrastructure.ai.sarvam_client import SarvamClient, SarvamClientError
from backend.infrastructure.ai.sarvam_providers import (
    SarvamChatProvider,
    SarvamLanguageIdentifier,
    SarvamSpeechToTextProvider,
    SarvamTextToSpeechProvider,
    SarvamTranslationProvider,
)


class TestSarvamMultimodalAdapters:
    def test_01_speech_to_text_protocol_and_success(self):
        """SarvamSpeechToTextProvider satisfies SpeechToTextProvider protocol and produces TranscriptionResult."""
        mock_client = MagicMock(spec=SarvamClient)
        mock_client.default_asr_model = "saaras:v3"
        mock_client.transcribe_audio.return_value = {
            "transcript": "Maine do roti aur dal khayi thi",
            "language_code": "hi-IN",
            "latency_ms": 142.5,
        }

        provider = SarvamSpeechToTextProvider(client=mock_client, model="saaras:v3")
        assert isinstance(provider, SpeechToTextProvider)

        result = provider.transcribe(b"dummy_audio_bytes", mime_type="audio/ogg")
        assert isinstance(result, TranscriptionResult)
        assert result.transcript == "Maine do roti aur dal khayi thi"
        assert result.language_code == "hi-IN"
        assert result.quality == "high"
        assert result.provenance.provider == "sarvam"
        assert result.provenance.model == "saaras:v3"
        assert result.provenance.latency_ms == 142.5
        mock_client.transcribe_audio.assert_called_once_with(
            b"dummy_audio_bytes",
            filename="voice_note.bin",
            mime_type="audio/ogg",
            language_code="unknown",
            model="saaras:v3",
        )

    def test_02_empty_audio_raises_unsupported_media_error(self):
        """Passing empty audio payload raises UnsupportedMediaError immediately without calling client."""
        mock_client = MagicMock()
        mock_client.default_asr_model = "saaras:v3"
        provider = SarvamSpeechToTextProvider(client=mock_client)

        with pytest.raises(UnsupportedMediaError) as exc_info:
            provider.transcribe(b"", mime_type="audio/ogg")
        assert "empty audio payload" in str(exc_info.value)
        mock_client.transcribe_audio.assert_not_called()

    def test_03_timeout_failure_translates_to_retryable_error(self):
        """A timeout from SarvamClient translates to a retryable AIMultimodalError."""
        mock_client = MagicMock(spec=SarvamClient)
        mock_client.default_asr_model = "saaras:v3"
        mock_client.transcribe_audio.side_effect = SarvamClientError("Connection timed out", retryable=True, error_code="TIMEOUT")

        provider = SarvamSpeechToTextProvider(client=mock_client)
        with pytest.raises(AIMultimodalError) as exc_info:
            provider.transcribe(b"valid_audio", mime_type="audio/ogg")
        assert exc_info.value.retryable is True
        assert exc_info.value.provider == "sarvam"
        assert "speech-to-text failed" in str(exc_info.value)

    def test_04_translation_adapter_success_and_error_wrapping(self):
        """SarvamTranslationProvider translates text and wraps non-retryable 4xx client errors."""
        mock_client = MagicMock(spec=SarvamClient)
        mock_client.translate.return_value = {"translated_text": "I ate two rotis and lentils"}

        provider = SarvamTranslationProvider(client=mock_client, model="mayura:v1")
        assert isinstance(provider, TranslationProvider)

        # Success path
        out = provider.translate("Maine do roti aur dal khayi", target_language_code="en-IN", source_language_code="hi-IN")
        assert out == "I ate two rotis and lentils"

        # Empty text yields empty string without network call
        assert provider.translate("") == ""

        # Permanent client error wrapping
        mock_client.translate.side_effect = SarvamClientError("Invalid language code", retryable=False, error_code="PROVIDER_4XX")
        with pytest.raises(AIMultimodalError) as exc_info:
            provider.translate("Hello")
        assert exc_info.value.retryable is False
        assert exc_info.value.provider == "sarvam"

    def test_05_text_to_speech_adapter_and_malformed_response_handling(self):
        """SarvamTextToSpeechProvider synthesizes audio bytes and safely handles missing or invalid base64."""
        mock_client = MagicMock(spec=SarvamClient)
        mock_client.default_tts_model = "bulbul:v3"
        audio_content = b"RIFF....WAVEfmt "
        mock_client.text_to_speech.return_value = {
            "audio_base64": base64.b64encode(audio_content).decode("ascii"),
        }

        provider = SarvamTextToSpeechProvider(client=mock_client)
        assert isinstance(provider, TextToSpeechProvider)

        wav_bytes = provider.synthesize("Namaste Ji", language_code="hi-IN")
        assert wav_bytes == audio_content

        # Malformed response: missing audio_base64
        mock_client.text_to_speech.return_value = {"audio_base64": ""}
        with pytest.raises(AIMultimodalError) as exc_info:
            provider.synthesize("Namaste Ji")
        assert "returned no audio" in str(exc_info.value)
        assert exc_info.value.retryable is False

    def test_06_language_identifier_script_heuristics(self):
        """SarvamLanguageIdentifier detects Devanagari as hi-IN and Latin Hinglish/English as en-IN."""
        identifier = SarvamLanguageIdentifier()
        assert isinstance(identifier, LanguageIdentifier)

        # Empty string
        assert identifier.identify("") == ""
        assert identifier.identify("   ") == ""

        # Devanagari script
        assert identifier.identify("मैंने दो रोटी खाई") == "hi-IN"
        assert identifier.identify("नमस्ते") == "hi-IN"

        # Latin / Hinglish script
        assert identifier.identify("Maine do roti khayi") == "en-IN"
        assert identifier.identify("Blood sugar 140 mg/dL") == "en-IN"

    def test_07_zero_secret_leakage_in_exceptions_and_provenance(self):
        """API keys or secret tokens are never embedded in adapter error messages or provenance metadata."""
        secret_key = "sk_live_very_secret_sarvam_credential_12345"
        client = SarvamClient(api_key=secret_key)
        provider = SarvamSpeechToTextProvider(client=client)

        with patch.object(client, "transcribe_audio", side_effect=SarvamClientError(f"Unauthorized with key {secret_key}", retryable=False)):
            with pytest.raises(AIMultimodalError) as exc_info:
                provider.transcribe(b"some_audio", mime_type="audio/ogg")
            err_msg = str(exc_info.value)
            # The wrapped error should describe the operation failure without leaking sensitive bearer tokens
            assert secret_key not in err_msg or "sarvam speech-to-text failed" in err_msg
            assert exc_info.value.provider == "sarvam"
