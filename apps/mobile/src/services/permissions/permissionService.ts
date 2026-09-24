import { getPermissionAdapter } from "./permissionAdapter";
import {
  clearPermissionStorageForTesting,
  getCachedPermissionState,
  hasCompletedInitialPrompt as storageHasCompletedInitialPrompt,
  resetAllPermissionData as storageResetAllPermissionData,
  saveCachedPermissionState,
  setCompletedInitialPrompt as storageSetCompletedInitialPrompt,
} from "./permissionStorage";
import type { PermissionState, PermissionStatus, PermissionType } from "./types";

export async function checkPermission(type: PermissionType): Promise<PermissionStatus> {
  const adapter = getPermissionAdapter();
  return adapter.check(type);
}

export async function checkAllPermissions(): Promise<PermissionState> {
  const adapter = getPermissionAdapter();
  return adapter.checkAll();
}

export async function requestPermission(type: PermissionType): Promise<PermissionStatus> {
  const adapter = getPermissionAdapter();
  return adapter.request(type);
}

export async function requestAllPermissions(userId?: string): Promise<PermissionState> {
  const adapter = getPermissionAdapter();
  const state = await adapter.requestAll();
  await storageSetCompletedInitialPrompt(true, userId);
  return state;
}

export function areAllPermissionsGranted(state: PermissionState): boolean {
  return (
    state.notifications === "granted" &&
    state.microphone === "granted" &&
    state.camera === "granted"
  );
}

export function getMissingPermissions(state: PermissionState): PermissionType[] {
  const missing: PermissionType[] = [];
  if (state.notifications !== "granted") missing.push("notifications");
  if (state.microphone !== "granted") missing.push("microphone");
  if (state.camera !== "granted") missing.push("camera");
  return missing;
}

export async function openAppSettings(): Promise<void> {
  const adapter = getPermissionAdapter();
  return adapter.openSettings();
}

export async function hasCompletedInitialPrompt(userId?: string): Promise<boolean> {
  return storageHasCompletedInitialPrompt(userId);
}

export async function setCompletedInitialPrompt(completed: boolean, userId?: string): Promise<void> {
  return storageSetCompletedInitialPrompt(completed, userId);
}

export async function resetAllPermissionData(userId?: string): Promise<void> {
  return storageResetAllPermissionData(userId);
}

export async function clearPermissionCache(): Promise<void> {
  clearPermissionStorageForTesting();
}

export {
  clearPermissionStorageForTesting,
  getCachedPermissionState,
  saveCachedPermissionState,
};

