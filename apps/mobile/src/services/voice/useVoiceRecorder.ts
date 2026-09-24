import { useState, useRef, useEffect, useCallback } from "react";
import { Platform } from "react-native";
import { apiClient } from "../api/client";
import { aiEndpoints } from "../api/endpoints/ai";
import type { TranscribeAiResponse } from "../schemas/ai";
import {
  requestMicrophonePermission,
  startAudioRecording,
  readAudioAsBase64,
  isVoiceRecordingAvailable,
  type AudioRecordingSession,
} from "./audioEngine";

export type VoiceRecorderStatus =
  | "idle"
  | "recording"
  | "transcribing"
  | "success"
  | "error";

export type UseVoiceRecorderResult = {
  status: VoiceRecorderStatus;
  durationSeconds: number;
  transcript: string | null;
  error: string | null;
  isRecording: boolean;
  isTranscribing: boolean;
  isVoiceAvailable: boolean;
  startRecording: () => Promise<boolean>;
  stopAndTranscribe: () => Promise<string | null>;
  cancelRecording: () => Promise<void>;
  reset: () => void;
};

export function useVoiceRecorder(): UseVoiceRecorderResult {
  const [status, setStatus] = useState<VoiceRecorderStatus>("idle");
  const [durationSeconds, setDurationSeconds] = useState<number>(0);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sessionRef = useRef<AudioRecordingSession | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const recordingStartTimeRef = useRef<number>(0);

  // Clear timer and active session on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (sessionRef.current) {
        sessionRef.current.cancel().catch(() => {});
      }
    };
  }, []);

  const reset = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    sessionRef.current = null;
    recordingStartTimeRef.current = 0;
    setStatus("idle");
    setDurationSeconds(0);
    setTranscript(null);
    setError(null);
  }, []);

  const startRecording = useCallback(async (): Promise<boolean> => {
    try {
      setError(null);
      setTranscript(null);
      setDurationSeconds(0);

      // Request microphone permission through safe adapter
      const permResult = await requestMicrophonePermission();
      if (!permResult.granted) {
        setStatus("error");
        setError(
          permResult.message ||
            "Microphone permission was denied. Please allow microphone access in device settings."
        );
        return false;
      }

      // Start recording through safe adapter
      const recordResult = await startAudioRecording();
      if (!recordResult.session) {
        setStatus("error");
        setError(
          recordResult.error || "Failed to initialize microphone recording."
        );
        return false;
      }

      sessionRef.current = recordResult.session;
      recordingStartTimeRef.current = Date.now();
      setStatus("recording");

      // Start elapsed timer
      timerRef.current = setInterval(() => {
        setDurationSeconds((prev) => prev + 1);
      }, 1000);

      return true;
    } catch (err: any) {
      setStatus("error");
      setError(err?.message || "Failed to start microphone recording.");
      return false;
    }
  }, []);

  const stopAndTranscribe = useCallback(async (): Promise<string | null> => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    const session = sessionRef.current;
    if (!session) {
      setStatus("error");
      setError("No active recording session found.");
      return null;
    }

    const durationMs = Date.now() - recordingStartTimeRef.current;

    try {
      setStatus("transcribing");

      // If recording was under 1000ms, brief wait ensures non-empty audio container
      if (durationMs < 1000) {
        await new Promise((r) => setTimeout(r, 1000 - durationMs));
      }

      const uri = await session.stop();
      sessionRef.current = null;

      if (!uri) {
        setStatus("error");
        setError("Audio capture completed but no audio file was generated.");
        return null;
      }

      // Convert audio file to Base64
      const base64Audio = await readAudioAsBase64(uri);

      if (!base64Audio) {
        setStatus("error");
        setError("Could not read captured audio file.");
        return null;
      }

      // Determine appropriate MIME type and filename according to URI and platform
      let mimeType = "audio/x-m4a";
      let filename = "dictation.m4a";

      const lowerUri = uri.toLowerCase();
      if (
        lowerUri.endsWith(".webm") ||
        lowerUri.includes("webm") ||
        Platform.OS === "web"
      ) {
        mimeType = "audio/webm";
        filename = "dictation.webm";
      } else if (lowerUri.endsWith(".mp4")) {
        mimeType = "audio/mp4";
        filename = "dictation.mp4";
      } else if (lowerUri.endsWith(".3gp")) {
        mimeType = "audio/3gp";
        filename = "dictation.3gp";
      } else if (lowerUri.endsWith(".wav")) {
        mimeType = "audio/wav";
        filename = "dictation.wav";
      } else if (lowerUri.endsWith(".aac")) {
        mimeType = "audio/aac";
        filename = "dictation.aac";
      } else if (lowerUri.endsWith(".ogg")) {
        mimeType = "audio/ogg";
        filename = "dictation.ogg";
      }

      // Submit to backend AI transcription API (Sarvam Saaras ASR / Gemini fallback)
      const res = await apiClient.request<TranscribeAiResponse>({
        method: aiEndpoints.transcribe.method,
        path: aiEndpoints.transcribe.path,
        body: {
          audio_base64: base64Audio,
          mime_type: mimeType,
          filename: filename,
          language_code: "unknown",
        },
        schema: aiEndpoints.transcribe.responseSchema,
      });

      const cleanTranscript = (res.transcript || "").trim();
      if (cleanTranscript.length === 0) {
        setStatus("error");
        setError("No speech was detected. Please speak closer to the microphone and try again.");
        return null;
      }

      setTranscript(cleanTranscript);
      setStatus("success");
      return cleanTranscript;
    } catch (err: any) {
      setStatus("error");
      const rawMessage: string = err?.message || "";
      let message =
        "Audio transcription failed. Please verify your connection or type your entry.";
      if (
        rawMessage.toLowerCase().includes("duration is 0") ||
        rawMessage.toLowerCase().includes("too short") ||
        rawMessage.toLowerCase().includes("silent")
      ) {
        message = "Recording was too short or silent. Please speak clearly for at least 1-2 seconds.";
      } else if (
        rawMessage &&
        !rawMessage.toLowerCase().includes("the request could not be completed") &&
        !rawMessage.toLowerCase().includes("request could not be completed")
      ) {
        message = rawMessage;
      }
      setError(message);
      return null;
    }
  }, []);

  const cancelRecording = useCallback(async () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    if (sessionRef.current) {
      try {
        await sessionRef.current.cancel();
      } catch {
        // Ignore errors on cancel
      }
      sessionRef.current = null;
    }

    reset();
  }, [reset]);

  return {
    status,
    durationSeconds,
    transcript,
    error,
    isRecording: status === "recording",
    isTranscribing: status === "transcribing",
    isVoiceAvailable: isVoiceRecordingAvailable(),
    startRecording,
    stopAndTranscribe,
    cancelRecording,
    reset,
  };
}
