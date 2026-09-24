/**
 * Native Audio Engine for Voice Recording.
 *
 * Uses expo-audio for recording in the Expo SDK 57 native runtime.
 *
 * The module is resolved lazily so importing this service does not crash
 * when running in an environment without the native audio module.
 */

export type AudioEngineType = "expo-audio" | "none";

export type AudioRecordingSession = {
  stop: () => Promise<string | null>;
  cancel: () => Promise<void>;
};

export type StartRecordingResult = {
  session: AudioRecordingSession | null;
  error?: string;
};

// Safe lazy loader that never throws at module evaluation time.
function getExpoAudioModule(): any | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("expo-audio");

    if (
      mod &&
      (mod.AudioModule ||
        mod.useAudioRecorder ||
        mod.requestRecordingPermissionsAsync)
    ) {
      return mod;
    }

    return null;
  } catch {
    return null;
  }
}

function getFileSystemModule(): any | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const fs = require("expo-file-system");
    return fs;
  } catch {
    return null;
  }
}

/**
 * Detect whether expo-audio is linked and available
 * in the current native runtime.
 */
export function detectAudioEngine(): AudioEngineType {
  return getExpoAudioModule() ? "expo-audio" : "none";
}

/**
 * Check whether voice recording is supported
 * in the current environment.
 */
export function isVoiceRecordingAvailable(): boolean {
  return detectAudioEngine() === "expo-audio";
}

/**
 * Request microphone access permission via expo-audio.
 */
export async function requestMicrophonePermission(): Promise<{
  granted: boolean;
  message?: string;
}> {
  const expoAudio = getExpoAudioModule();

  if (expoAudio?.requestRecordingPermissionsAsync) {
    try {
      const res = await expoAudio.requestRecordingPermissionsAsync();

      if (res?.granted || res?.status === "granted") {
        return { granted: true };
      }

      return {
        granted: false,
        message:
          "Microphone permission was denied. Please allow microphone access in device settings.",
      };
    } catch (err: any) {
      return {
        granted: false,
        message:
          err?.message ||
          "Unable to request microphone permission.",
      };
    }
  }

  return {
    granted: false,
    message:
      "The native expo-audio module is not available. Please use the iOS development build.",
  };
}

/**
 * Start an audio recording session using expo-audio.
 */
export async function startAudioRecording(): Promise<StartRecordingResult> {
  const expoAudio = getExpoAudioModule();

  if (!expoAudio) {
    return {
      session: null,
      error:
        "The native expo-audio module is not available. Please use the iOS development build.",
    };
  }

  try {
    if (expoAudio.setAudioModeAsync) {
      await expoAudio
        .setAudioModeAsync({
          allowsRecording: true,
          playsInSilentMode: true,
        })
        .catch(() => { });
    }

    const AudioRecorderClass =
      expoAudio.AudioRecorder || expoAudio.AudioModule?.AudioRecorder;

    if (!AudioRecorderClass) {
      return {
        session: null,
        error:
          "expo-audio AudioRecorder is not available in this native build.",
      };
    }

    const presets = expoAudio.RecordingPresets?.HIGH_QUALITY || {};
    const recorder = new AudioRecorderClass(presets);

    if (recorder.prepareToRecordAsync) {
      await recorder.prepareToRecordAsync();
    }

    recorder.record();

    const session: AudioRecordingSession = {
      stop: async () => {
        try {
          await recorder.stop();
          return recorder.uri || null;
        } catch {
          return null;
        }
      },

      cancel: async () => {
        try {
          await recorder.stop();
        } catch {
          // Ignore cancellation errors.
        }
      },
    };

    return { session };
  } catch (err: any) {
    return {
      session: null,
      error:
        err?.message ||
        "Failed to start audio recording.",
    };
  }
}

async function readAudioAsBase64Internal(uri: string): Promise<string | null> {
  // 1. Data URI
  if (uri.startsWith("data:")) {
    const comma = uri.indexOf(",");
    if (comma !== -1) {
      const data = uri.substring(comma + 1).trim();
      return data || null;
    }
  }

  // 2. Web blob: URL or http URL in browser environment
  if (
    uri.startsWith("blob:") ||
    (typeof window !== "undefined" &&
      typeof FileReader !== "undefined" &&
      uri.startsWith("http"))
  ) {
    try {
      const response = await fetch(uri);
      const blob = await response.blob();
      const base64 = await new Promise<string | null>((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          const res = reader.result as string;
          if (res && res.includes(",")) {
            const parts = res.split(",");
            resolve(parts[1] || null);
          } else {
            resolve(res || null);
          }
        };
        reader.onerror = () => resolve(null);
        reader.readAsDataURL(blob);
      });
      if (base64 && base64.length > 0) return base64;
    } catch {
      // Fall through to next method
    }
  }

  // 3. Modern Expo FileSystem (Expo SDK 52-57+ File API)
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const fs = require("expo-file-system");
    if (fs?.File) {
      const file = new fs.File(uri);
      if (typeof file.base64 === "function") {
        const base64 = await file.base64();
        if (base64 && typeof base64 === "string" && base64.trim().length > 0) {
          return base64.trim();
        }
      }
    }
  } catch {
    // Fall through to legacy
  }

  // 4. Legacy Expo FileSystem (expo-file-system/legacy)
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const legacyFs = require("expo-file-system/legacy");
    if (legacyFs && typeof legacyFs.readAsStringAsync === "function") {
      const base64 = await legacyFs.readAsStringAsync(uri, {
        encoding: legacyFs.EncodingType?.Base64 || "base64",
      });
      if (base64 && typeof base64 === "string" && base64.trim().length > 0) {
        return base64.trim();
      }
    }
  } catch {
    // Fall through
  }

  // 5. Root expo-file-system readAsStringAsync (backward compatibility)
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const fs = require("expo-file-system");
    if (fs && typeof fs.readAsStringAsync === "function") {
      const base64 = await fs.readAsStringAsync(uri, {
        encoding: fs.EncodingType?.Base64 || "base64",
      });
      if (base64 && typeof base64 === "string" && base64.trim().length > 0) {
        return base64.trim();
      }
    }
  } catch {
    // Fall through
  }

  // 6. Generic fetch fallback (works for local file:// URIs on many React Native platforms)
  try {
    const response = await fetch(uri);
    const blob = await response.blob();
    if (typeof FileReader !== "undefined") {
      const base64 = await new Promise<string | null>((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          const res = reader.result as string;
          if (res && res.includes(",")) {
            const parts = res.split(",");
            resolve(parts[1] || null);
          } else {
            resolve(res || null);
          }
        };
        reader.onerror = () => resolve(null);
        reader.readAsDataURL(blob);
      });
      if (base64 && base64.length > 0) return base64;
    }
  } catch {
    // All methods exhausted
  }

  return null;
}

/**
 * Read recorded audio file as Base64 string
 * for API transmission. Retries briefly to allow native filesystem flush.
 */
export async function readAudioAsBase64(
  uri: string
): Promise<string | null> {
  if (!uri || typeof uri !== "string" || uri.trim().length === 0) {
    return null;
  }

  const cleanUri = uri.trim();

  // Retry up to 3 times (0ms, 60ms, 120ms) to ensure file write buffer has flushed to disk
  for (let attempt = 0; attempt < 3; attempt++) {
    const result = await readAudioAsBase64Internal(cleanUri);
    if (result && result.length > 0) {
      return result;
    }
    if (attempt < 2) {
      await new Promise((r) => setTimeout(r, 60));
    }
  }

  return null;
}