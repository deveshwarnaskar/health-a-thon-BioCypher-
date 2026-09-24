/**
 * Meal Photo Capture & Vision AI Analysis Service.
 *
 * Uses native expo-camera (CameraView) for direct in-app viewfinder capture,
 * expo-file-system for base64 encoding, and safe optional loading for
 * expo-image-picker (gallery upload).
 */

import { NativeModules, Platform } from "react-native";
import * as FileSystem from "expo-file-system";
import { apiClient } from "../api/client";
import { aiEndpoints } from "../api/endpoints/ai";
import type { AnalyzeMealPhotoAiResponse } from "../schemas/ai";

export type CapturedPhotoResult = {
  uri: string;
  base64: string;
  mimeType: string;
  width?: number;
  height?: number;
};

/**
 * Check whether the native ExponentImagePicker module is actually linked in the runtime binary.
 * This prevents "Cannot find native module 'ExponentImagePicker'" crashes when running
 * in pre-built development clients that haven't been recompiled yet.
 */
export function hasNativeImagePicker(): boolean {
  if (Platform.OS === "web") {
    return true;
  }
  try {
    const expoModules = (globalThis as any).expo?.modules;
    if (expoModules && (Boolean(expoModules.ExponentImagePicker) || Boolean(expoModules.ExpoImagePicker))) {
      return true;
    }
    if (NativeModules && (Boolean(NativeModules.ExponentImagePicker) || Boolean(NativeModules.ExpoImagePicker))) {
      return true;
    }
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("expo-image-picker");
    return Boolean(mod?.launchImageLibraryAsync);
  } catch {
    return false;
  }
}

/**
 * Safe lazy loader for expo-image-picker.
 * ONLY called if hasNativeImagePicker() is true to avoid native module lookup exceptions.
 */
function getImagePickerModule(): any | null {
  if (!hasNativeImagePicker()) {
    return null;
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require("expo-image-picker");
  } catch {
    return null;
  }
}

/**
 * Check whether camera is available in the current environment.
 */
export function isCameraAvailable(): boolean {
  if (Platform.OS === "web") return false;
  try {
    const expoModules = (globalThis as any).expo?.modules;
    if (expoModules && Boolean(expoModules.ExpoCamera)) {
      return true;
    }
    if (NativeModules && Boolean(NativeModules.ExpoCamera)) {
      return true;
    }
    // Default to true on native platforms because ExpoCamera (57.0.5) is compiled into the app
    return true;
  } catch {
    return true;
  }
}

/**
 * Convert a local file URI to a base64 string using expo-file-system.
 */
export async function convertUriToBase64(uri: string): Promise<string> {
  try {
    return await FileSystem.readAsStringAsync(uri, {
      encoding: FileSystem.EncodingType.Base64,
    });
  } catch {
    // Web or fallback using fetch/blob
    if (typeof fetch !== "undefined") {
      const resp = await fetch(uri);
      const blob = await resp.blob();
      if (typeof FileReader !== "undefined") {
        return new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => {
            const res = (reader.result as string) || "";
            const comma = res.indexOf(",");
            resolve(comma !== -1 ? res.substring(comma + 1) : res);
          };
          reader.onerror = reject;
          reader.readAsDataURL(blob);
        });
      }
    }
    throw new Error("Could not read image file to base64.");
  }
}

/**
 * Pick meal photo from gallery if native image picker is available.
 */
export async function pickMealPhotoFromLibrary(): Promise<CapturedPhotoResult | null> {
  if (!hasNativeImagePicker()) {
    throw new Error(
      "Gallery upload is not available in the current app build. Please use the camera directly to photograph your meal!"
    );
  }

  const picker = getImagePickerModule();
  if (!picker?.launchImageLibraryAsync) {
    throw new Error(
      "Gallery upload is not available in the current app build. Please use the camera directly to photograph your meal!"
    );
  }

  if (picker.requestMediaLibraryPermissionsAsync) {
    const perm = await picker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted && perm.status !== "granted") {
      throw new Error("Photo library permission is required to choose a meal image.");
    }
  }

  const result = await picker.launchImageLibraryAsync({
    mediaTypes: ["images"],
    allowsEditing: true,
    quality: 0.8,
    base64: true,
  });

  if (result.canceled || !result.assets || result.assets.length === 0) {
    return null;
  }

  const asset = result.assets[0];
  let base64 = asset.base64 || "";

  if (!base64 && asset.uri) {
    try {
      base64 = await convertUriToBase64(asset.uri);
    } catch {
      // Fallback
    }
  }

  const mimeType =
    asset.mimeType || (asset.uri?.toLowerCase().endsWith(".png") ? "image/png" : "image/jpeg");

  return {
    uri: asset.uri,
    base64,
    mimeType,
    width: asset.width,
    height: asset.height,
  };
}

/**
 * Submit meal photo to backend Gemini Vision AI for analysis.
 */
export async function analyzeMealPhoto(
  photo: CapturedPhotoResult,
  patientName = ""
): Promise<AnalyzeMealPhotoAiResponse> {
  return apiClient.request<AnalyzeMealPhotoAiResponse>({
    method: aiEndpoints.analyzeMealPhoto.method,
    path: aiEndpoints.analyzeMealPhoto.path,
    body: {
      image_base64: photo.base64,
      mime_type: photo.mimeType,
      patient_name: patientName,
    },
    schema: aiEndpoints.analyzeMealPhoto.responseSchema,
  });
}
