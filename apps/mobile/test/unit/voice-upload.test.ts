import { describe, expect, it, vi, beforeEach } from "vitest";
import { parseGlucoseVoiceTranscript } from "../../src/features/glucose/voiceParser";
import {
  transcribeAiRequestSchema,
  transcribeAiResponseSchema,
} from "../../src/services/schemas/ai";
import { aiEndpoints } from "../../src/services/api/endpoints/ai";

describe("Voice Upload Feature & AI Integration Tests", () => {
  describe("parseGlucoseVoiceTranscript", () => {
    it("extracts fasting value and tag from English phrase", () => {
      const result = parseGlucoseVoiceTranscript("My fasting sugar is 115 mg/dL");
      expect(result.value).toBe(115);
      expect(result.tag).toBe("fasting");
    });

    it("extracts post-lunch reading from Hinglish phrase", () => {
      const result = parseGlucoseVoiceTranscript("Mera sugar 142 aaya lunch ke baad");
      expect(result.value).toBe(142);
      expect(result.tag).toBe("postlunch");
    });

    it("extracts pre-meal reading", () => {
      const result = parseGlucoseVoiceTranscript("Pre-meal glucose 98");
      expect(result.value).toBe(98);
      expect(result.tag).toBe("premeal");
    });

    it("extracts post-dinner reading", () => {
      const result = parseGlucoseVoiceTranscript("Raat ke khane ke baad 180 sugar");
      expect(result.value).toBe(180);
      expect(result.tag).toBe("postdinner");
    });

    it("extracts post-breakfast reading", () => {
      const result = parseGlucoseVoiceTranscript("Nashta ke baad 155");
      expect(result.value).toBe(155);
      expect(result.tag).toBe("postbreakfast");
    });

    it("extracts bare number without context tag", () => {
      const result = parseGlucoseVoiceTranscript("108");
      expect(result.value).toBe(108);
      expect(result.tag).toBeNull();
    });

    it("handles out of clinical range numbers gracefully", () => {
      // 15 is < 20, 750 is > 600
      const lowResult = parseGlucoseVoiceTranscript("Sugar 15");
      expect(lowResult.value).toBeNull();

      const highResult = parseGlucoseVoiceTranscript("Sugar 750");
      expect(highResult.value).toBeNull();
    });

    it("handles empty or non-numeric transcripts", () => {
      const emptyResult = parseGlucoseVoiceTranscript("");
      expect(emptyResult.value).toBeNull();
      expect(emptyResult.tag).toBeNull();

      const textOnly = parseGlucoseVoiceTranscript("Just checking my sugar today");
      expect(textOnly.value).toBeNull();
      expect(textOnly.tag).toBeNull();
    });
  });

  describe("Transcribe AI Schemas & Endpoint", () => {
    it("validates valid transcribe request", () => {
      const validReq = transcribeAiRequestSchema.safeParse({
        audio_base64: "dGVzdC1hdWRpby1ieXRlcw==",
        mime_type: "audio/m4a",
        filename: "voice.m4a",
        language_code: "hi-IN",
      });
      expect(validReq.success).toBe(true);
    });

    it("validates valid transcribe response from Sarvam AI", () => {
      const validRes = transcribeAiResponseSchema.safeParse({
        transcript: "2 roti aur dal khaya",
        language_code: "hi-IN",
        provider: "sarvam_saaras_v2",
        latency_ms: 320,
      });
      expect(validRes.success).toBe(true);
      if (validRes.success) {
        expect(validRes.data.transcript).toBe("2 roti aur dal khaya");
        expect(validRes.data.provider).toBe("sarvam_saaras_v2");
      }
    });

    it("verifies aiEndpoints.transcribe definition", () => {
      expect(aiEndpoints.transcribe.method).toBe("POST");
      expect(aiEndpoints.transcribe.path).toBe("/api/v2/ai/transcribe-base64");
      expect(aiEndpoints.transcribe.requiresIdempotencyKey).toBe(false);
    });
  });

  describe("Safe Audio Engine & Degradation", () => {
    it("safely detects audio engine without crashing runtime", async () => {
      const { detectAudioEngine, isVoiceRecordingAvailable } = await import(
        "../../src/services/voice/audioEngine"
      );
      const engine = detectAudioEngine();
      expect(["expo-audio", "expo-av", "none"]).toContain(engine);
      expect(typeof isVoiceRecordingAvailable()).toBe("boolean");
    });

    it("safely handles requestMicrophonePermission without crashing", async () => {
      const { requestMicrophonePermission } = await import(
        "../../src/services/voice/audioEngine"
      );
      const res = await requestMicrophonePermission();
      expect(res).toBeDefined();
      expect(typeof res.granted).toBe("boolean");
    });

    it("safely handles startAudioRecording when module unavailable without crashing", async () => {
      const { startAudioRecording } = await import(
        "../../src/services/voice/audioEngine"
      );
      const res = await startAudioRecording();
      expect(res).toBeDefined();
      if (!res.session) {
        expect(res.error).toBeDefined();
      }
    });

    it("safely handles readAudioAsBase64 when file does not exist", async () => {
      const { readAudioAsBase64 } = await import(
        "../../src/services/voice/audioEngine"
      );
      const res = await readAudioAsBase64("non_existent_file.m4a");
      expect(res).toBeNull();
    });

    it("correctly extracts base64 data from a data URI", async () => {
      const { readAudioAsBase64 } = await import(
        "../../src/services/voice/audioEngine"
      );
      const testData = "T3JpZ2luYWxCYXNlNjREYXRh";
      const dataUri = `data:audio/m4a;base64,${testData}`;
      const res = await readAudioAsBase64(dataUri);
      expect(res).toBe(testData);
    });

    it("returns null for empty or whitespace-only URI", async () => {
      const { readAudioAsBase64 } = await import(
        "../../src/services/voice/audioEngine"
      );
      expect(await readAudioAsBase64("")).toBeNull();
      expect(await readAudioAsBase64("   ")).toBeNull();
    });
  });
});

