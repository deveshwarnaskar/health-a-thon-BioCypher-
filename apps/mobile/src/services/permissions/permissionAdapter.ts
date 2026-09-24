import { Linking, PermissionsAndroid, Platform, type Permission } from "react-native";
import type { PermissionState, PermissionStatus, PermissionType } from "./types";
import { getCachedPermissionState, saveCachedPermissionState } from "./permissionStorage";

export interface PermissionAdapter {
  check(type: PermissionType): Promise<PermissionStatus>;
  checkAll(): Promise<PermissionState>;
  request(type: PermissionType): Promise<PermissionStatus>;
  requestAll(): Promise<PermissionState>;
  openSettings(): Promise<void>;
}

// Android mapping helper
function getAndroidPermission(type: PermissionType): Permission | null {
  switch (type) {
    case "camera":
      return PermissionsAndroid.PERMISSIONS.CAMERA;
    case "microphone":
      return PermissionsAndroid.PERMISSIONS.RECORD_AUDIO;
    case "notifications":
      // POST_NOTIFICATIONS was introduced in Android 13 (API 33)
      if (typeof Platform.Version === "number" && Platform.Version < 33) {
        return null;
      }
      return PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS;
  }
}

function mapAndroidResult(result: string): PermissionStatus {
  switch (result) {
    case PermissionsAndroid.RESULTS.GRANTED:
      return "granted";
    case PermissionsAndroid.RESULTS.NEVER_ASK_AGAIN:
      return "blocked";
    case PermissionsAndroid.RESULTS.DENIED:
    default:
      return "denied";
  }
}

export class DefaultPermissionAdapter implements PermissionAdapter {
  async check(type: PermissionType): Promise<PermissionStatus> {
    if (Platform.OS === "android") {
      const permission = getAndroidPermission(type);
      if (!permission) {
        // Notification permission automatically granted on Android < 33
        return "granted";
      }
      try {
        const has = await PermissionsAndroid.check(permission);
        return has ? "granted" : "denied";
      } catch {
        return "undetermined";
      }
    }

    if (Platform.OS === "web" && typeof window !== "undefined") {
      if (type === "notifications" && "Notification" in window) {
        if (Notification.permission === "granted") return "granted";
        if (Notification.permission === "denied") return "blocked";
        return "undetermined";
      }
      if (navigator.permissions && navigator.permissions.query) {
        try {
          const res = await navigator.permissions.query({
            name: (type === "camera" ? "camera" : "microphone") as any,
          });
          if (res.state === "granted") return "granted";
          if (res.state === "denied") return "blocked";
          return "undetermined";
        } catch {
          // Some browsers do not support querying camera/microphone via Permissions API
        }
      }
    }

    // Default or iOS fallback: check cached state from persistent store
    const cached = await getCachedPermissionState();
    return cached?.[type] ?? "undetermined";
  }

  async checkAll(): Promise<PermissionState> {
    const [notifications, microphone, camera] = await Promise.all([
      this.check("notifications"),
      this.check("microphone"),
      this.check("camera"),
    ]);

    const state: PermissionState = { notifications, microphone, camera };
    await saveCachedPermissionState(state);
    return state;
  }

  async request(type: PermissionType): Promise<PermissionStatus> {
    if (Platform.OS === "android") {
      const permission = getAndroidPermission(type);
      if (!permission) {
        return "granted";
      }

      try {
        const rationale = {
          title: `Enable ${type} permission`,
          message: `THALI requires ${type} access to function properly.`,
          buttonPositive: "Allow",
          buttonNegative: "Don't allow",
        };
        const result = await PermissionsAndroid.request(permission, rationale);
        const mapped = mapAndroidResult(result);
        const cached = (await getCachedPermissionState()) ?? {
          notifications: "undetermined",
          microphone: "undetermined",
          camera: "undetermined",
        };
        cached[type] = mapped;
        await saveCachedPermissionState(cached);
        return mapped;
      } catch {
        return "denied";
      }
    }

    if (Platform.OS === "web" && typeof window !== "undefined") {
      if (type === "notifications" && "Notification" in window) {
        try {
          const res = await Notification.requestPermission();
          const mapped: PermissionStatus = res === "granted" ? "granted" : "denied";
          const cached = (await getCachedPermissionState()) ?? {
            notifications: "undetermined",
            microphone: "undetermined",
            camera: "undetermined",
          };
          cached.notifications = mapped;
          await saveCachedPermissionState(cached);
          return mapped;
        } catch {
          return "denied";
        }
      }

      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
          const constraints =
            type === "camera" ? { video: true } : { audio: true };
          const stream = await navigator.mediaDevices.getUserMedia(constraints);
          stream.getTracks().forEach((track) => track.stop());
          const cached = (await getCachedPermissionState()) ?? {
            notifications: "undetermined",
            microphone: "undetermined",
            camera: "undetermined",
          };
          cached[type] = "granted";
          await saveCachedPermissionState(cached);
          return "granted";
        } catch {
          return "denied";
        }
      }
    }

    // Default / iOS: simulate grant and persist (or user can open settings)
    const cached = (await getCachedPermissionState()) ?? {
      notifications: "undetermined",
      microphone: "undetermined",
      camera: "undetermined",
    };
    cached[type] = "granted";
    await saveCachedPermissionState(cached);
    return "granted";
  }

  async requestAll(): Promise<PermissionState> {
    if (Platform.OS === "android") {
      const perms: Permission[] = [];
      const cam = getAndroidPermission("camera");
      const mic = getAndroidPermission("microphone");
      const notif = getAndroidPermission("notifications");

      if (cam) perms.push(cam);
      if (mic) perms.push(mic);
      if (notif) perms.push(notif);

      if (perms.length > 0) {
        try {
          const results = (await PermissionsAndroid.requestMultiple(perms)) as Record<string, string>;
          const state: PermissionState = {
            camera: cam ? mapAndroidResult(results[cam] ?? "") : "granted",
            microphone: mic ? mapAndroidResult(results[mic] ?? "") : "granted",
            notifications: notif ? mapAndroidResult(results[notif] ?? "") : "granted",
          };
          await saveCachedPermissionState(state);
          return state;
        } catch {
          // Fall through to sequential request
        }
      }
    }

    // Sequential requests for Web / iOS / fallbacks
    const notifications = await this.request("notifications");
    const microphone = await this.request("microphone");
    const camera = await this.request("camera");

    const state: PermissionState = { notifications, microphone, camera };
    await saveCachedPermissionState(state);
    return state;
  }

  async openSettings(): Promise<void> {
    try {
      await Linking.openSettings();
    } catch {
      // Non-fatal if openSettings is not supported
    }
  }
}

// Global active adapter with testing override capability
let activeAdapter: PermissionAdapter = new DefaultPermissionAdapter();

export function getPermissionAdapter(): PermissionAdapter {
  return activeAdapter;
}

export function setPermissionAdapterForTesting(adapter: PermissionAdapter | null): void {
  activeAdapter = adapter ?? new DefaultPermissionAdapter();
}
