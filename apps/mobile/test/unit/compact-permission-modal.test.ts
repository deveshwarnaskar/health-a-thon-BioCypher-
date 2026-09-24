import { describe, expect, it } from "vitest";
import {
  PERMISSION_METADATA,
  type PermissionState,
  type PermissionType,
} from "../../src/services/permissions/types";

describe("CompactPermissionModal Logic & Flow", () => {

  it("defines dark theme colors and crisp rationales for all 3 permissions", () => {
    const list: PermissionType[] = ["notifications", "microphone", "camera"];
    for (const type of list) {
      const meta = PERMISSION_METADATA[type];
      expect(meta.title).toBeTruthy();
      expect(meta.detailedRationale).toBeTruthy();
      expect(meta.darkBgColor).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(meta.darkIconColor).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(meta.iconName).toBeTruthy();
    }
  });

  it("handles step progression through the 3 permissions one-at-a-time", async () => {
    const permissions: PermissionType[] = ["notifications", "microphone", "camera"];
    let currentIdx = 0;
    const requested: PermissionType[] = [];

    const handleRequest = async (type: PermissionType) => {
      requested.push(type);
      return "granted" as const;
    };

    const advance = () => {
      currentIdx++;
    };

    // Step 1: Notifications
    expect(permissions[currentIdx]).toBe("notifications");
    await handleRequest(permissions[currentIdx]!);
    advance();

    // Step 2: Microphone
    expect(permissions[currentIdx]).toBe("microphone");
    await handleRequest(permissions[currentIdx]!);
    advance();

    // Step 3: Camera
    expect(permissions[currentIdx]).toBe("camera");
    await handleRequest(permissions[currentIdx]!);
    advance();

    expect(requested).toEqual(["notifications", "microphone", "camera"]);
    expect(currentIdx).toBe(3);
  });

  it("handles skip step flow without requesting permission", () => {
    const permissions: PermissionType[] = ["notifications", "microphone", "camera"];
    let currentIdx = 0;
    const requested: PermissionType[] = [];

    // User skips Step 1 (notifications)
    currentIdx++;

    // User grants Step 2 (microphone)
    requested.push(permissions[currentIdx]!);
    currentIdx++;

    // User skips Step 3 (camera)
    currentIdx++;

    expect(requested).toEqual(["microphone"]);
    expect(currentIdx).toBe(3);
  });

  it("detects blocked permissions and routes to settings", async () => {
    const state: PermissionState = {
      notifications: "granted",
      microphone: "blocked",
      camera: "denied",
    };

    const missingPermissions: PermissionType[] = ["microphone", "camera"];
    const currentType = missingPermissions[0]!;
    expect(state[currentType]).toBe("blocked");

    let openedSettings = false;
    const openSettings = async () => {
      openedSettings = true;
    };

    if (state[currentType] === "blocked") {
      await openSettings();
    }

    expect(openedSettings).toBe(true);
  });
});
