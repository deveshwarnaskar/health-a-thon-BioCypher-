import * as SecureStore from "expo-secure-store";
import type { PermissionState } from "./types";

const INITIAL_PROMPT_STORAGE_KEY = "thali.permissions.initial_prompt_completed";
const CACHED_STATE_STORAGE_KEY = "thali.permissions.cached_state";

// In-memory fallback for unit testing, SSR, and web environments
const memoryStore: Record<string, string> = {};

export function clearPermissionStorageForTesting(): void {
  for (const key of Object.keys(memoryStore)) {
    delete memoryStore[key];
  }
}

async function safeGetItem(key: string): Promise<string | null> {
  if (memoryStore[key] !== undefined) {
    return memoryStore[key];
  }
  try {
    const val = await SecureStore.getItemAsync(key);
    if (val !== null) {
      memoryStore[key] = val;
    }
    return val;
  } catch {
    return memoryStore[key] ?? null;
  }
}

async function safeSetItem(key: string, value: string): Promise<void> {
  memoryStore[key] = value;
  try {
    await SecureStore.setItemAsync(key, value);
  } catch {
    // Non-fatal if secure store is unavailable in current runtime/test harness
  }
}

async function safeDeleteItem(key: string): Promise<void> {
  delete memoryStore[key];
  try {
    await SecureStore.deleteItemAsync(key);
  } catch {
    // Non-fatal
  }
}

export async function hasCompletedInitialPrompt(userId?: string): Promise<boolean> {
  if (userId) {
    const userVal = await safeGetItem(`thali.permissions.initial_prompt_${userId}`);
    return userVal === "true";
  }
  const value = await safeGetItem(INITIAL_PROMPT_STORAGE_KEY);
  return value === "true";
}

export async function setCompletedInitialPrompt(
  completed: boolean,
  userId?: string
): Promise<void> {
  const strVal = completed ? "true" : "false";
  await safeSetItem(INITIAL_PROMPT_STORAGE_KEY, strVal);
  if (userId) {
    await safeSetItem(`thali.permissions.initial_prompt_${userId}`, strVal);
  }
}

export async function resetAllPermissionData(userId?: string): Promise<void> {
  await safeDeleteItem(INITIAL_PROMPT_STORAGE_KEY);
  if (userId) {
    await safeDeleteItem(`thali.permissions.initial_prompt_${userId}`);
  }
  await safeDeleteItem(CACHED_STATE_STORAGE_KEY);
}

export async function getCachedPermissionState(): Promise<PermissionState | null> {
  const raw = await safeGetItem(CACHED_STATE_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PermissionState;
  } catch {
    return null;
  }
}

export async function saveCachedPermissionState(state: PermissionState): Promise<void> {
  await safeSetItem(CACHED_STATE_STORAGE_KEY, JSON.stringify(state));
}

