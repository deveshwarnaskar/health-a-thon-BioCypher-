import { beforeEach, describe, expect, it } from "vitest";
import {
  areAllPermissionsGranted,
  checkAllPermissions,
  clearPermissionStorageForTesting,
  getMissingPermissions,
  hasCompletedInitialPrompt,
  openAppSettings,
  requestAllPermissions,
  requestPermission,
  resetAllPermissionData,
  setCompletedInitialPrompt,
} from "../../src/services/permissions/permissionService";
import {
  setPermissionAdapterForTesting,
  type PermissionAdapter,
} from "../../src/services/permissions/permissionAdapter";
import {
  INITIAL_PERMISSION_STATE,
  PERMISSION_METADATA,
  type PermissionState,
  type PermissionStatus,
  type PermissionType,
} from "../../src/services/permissions/types";

class MockPermissionAdapter implements PermissionAdapter {
  public state: PermissionState = {
    notifications: "undetermined",
    microphone: "undetermined",
    camera: "undetermined",
  };
  public openSettingsCalled = false;

  async check(type: PermissionType): Promise<PermissionStatus> {
    return this.state[type];
  }

  async checkAll(): Promise<PermissionState> {
    return { ...this.state };
  }

  async request(type: PermissionType): Promise<PermissionStatus> {
    if (this.state[type] !== "blocked") {
      this.state[type] = "granted";
    }
    return this.state[type];
  }

  async requestAll(): Promise<PermissionState> {
    for (const key of Object.keys(this.state) as PermissionType[]) {
      if (this.state[key] !== "blocked") {
        this.state[key] = "granted";
      }
    }
    return { ...this.state };
  }

  async openSettings(): Promise<void> {
    this.openSettingsCalled = true;
  }
}

describe("Permission System (First-Install & Recurring Prompt Lifecycle)", () => {
  let mockAdapter: MockPermissionAdapter;

  beforeEach(() => {
    clearPermissionStorageForTesting();
    mockAdapter = new MockPermissionAdapter();
    setPermissionAdapterForTesting(mockAdapter);
  });

  describe("Metadata and Default State", () => {
    it("defines proper metadata for notifications, microphone, and camera", () => {
      expect(PERMISSION_METADATA.notifications.title).toBe("Notifications");
      expect(PERMISSION_METADATA.microphone.title).toBe("Microphone");
      expect(PERMISSION_METADATA.camera.title).toBe("Camera");

      expect(PERMISSION_METADATA.notifications.shortDescription).toContain("Medication alerts");
      expect(PERMISSION_METADATA.microphone.shortDescription).toContain("Voice symptom");
      expect(PERMISSION_METADATA.camera.shortDescription).toContain("Meal plate");
    });

    it("has initial state with all permissions undetermined", () => {
      expect(INITIAL_PERMISSION_STATE).toEqual({
        notifications: "undetermined",
        microphone: "undetermined",
        camera: "undetermined",
      });
    });
  });

  describe("First-Time Install Flow (WhatsApp / Facebook style onboarding)", () => {
    it("starts with hasCompletedInitialPrompt as false on fresh install", async () => {
      const completed = await hasCompletedInitialPrompt();
      expect(completed).toBe(false);
    });

    it("marks hasCompletedInitialPrompt as true once user completes permission onboarding", async () => {
      expect(await hasCompletedInitialPrompt()).toBe(false);
      await setCompletedInitialPrompt(true);
      expect(await hasCompletedInitialPrompt()).toBe(true);
    });

    it("grants all permissions when user clicks 'Turn On All Permissions'", async () => {
      const result = await requestAllPermissions();
      expect(result).toEqual({
        notifications: "granted",
        microphone: "granted",
        camera: "granted",
      });

      expect(areAllPermissionsGranted(result)).toBe(true);
      expect(getMissingPermissions(result)).toEqual([]);
      expect(await hasCompletedInitialPrompt()).toBe(true);
    });

    it("allows granting permissions individually", async () => {
      const notifStatus = await requestPermission("notifications");
      expect(notifStatus).toBe("granted");

      const current = await checkAllPermissions();
      expect(current.notifications).toBe("granted");
      expect(current.microphone).toBe("undetermined");
      expect(current.camera).toBe("undetermined");
      expect(areAllPermissionsGranted(current)).toBe(false);
      expect(getMissingPermissions(current)).toEqual(["microphone", "camera"]);
    });

    it("isolates initial prompt state per user (new accounts always prompt)", async () => {
      // User A completes onboarding
      await setCompletedInitialPrompt(true, "user_alice");
      expect(await hasCompletedInitialPrompt("user_alice")).toBe(true);

      // User B logs in on same device: has NOT completed onboarding
      expect(await hasCompletedInitialPrompt("user_bob")).toBe(false);
    });

    it("resets all permission data when resetAllPermissionData is called", async () => {
      await setCompletedInitialPrompt(true, "user_charlie");
      expect(await hasCompletedInitialPrompt("user_charlie")).toBe(true);

      await resetAllPermissionData("user_charlie");
      expect(await hasCompletedInitialPrompt("user_charlie")).toBe(false);
      expect(await hasCompletedInitialPrompt()).toBe(false);
    });
  });

  describe("Subsequent Launch Flow (Prompting when permissions are not turned on)", () => {
    it("detects when permissions were denied or not turned on during first install", async () => {
      // Simulate user finished initial prompt, but denied microphone and camera
      await setCompletedInitialPrompt(true);
      mockAdapter.state = {
        notifications: "granted",
        microphone: "denied",
        camera: "denied",
      };

      const current = await checkAllPermissions();
      expect(await hasCompletedInitialPrompt()).toBe(true);
      expect(areAllPermissionsGranted(current)).toBe(false);
      expect(getMissingPermissions(current)).toEqual(["microphone", "camera"]);
    });

    it("detects all missing permissions if user dismissed everything", async () => {
      await setCompletedInitialPrompt(true);
      mockAdapter.state = {
        notifications: "denied",
        microphone: "denied",
        camera: "denied",
      };

      const current = await checkAllPermissions();
      expect(areAllPermissionsGranted(current)).toBe(false);
      expect(getMissingPermissions(current)).toEqual([
        "notifications",
        "microphone",
        "camera",
      ]);
    });

    it("allows user to grant missing permissions later, achieving all-granted state", async () => {
      await setCompletedInitialPrompt(true);
      mockAdapter.state = {
        notifications: "granted",
        microphone: "denied",
        camera: "denied",
      };

      // User subsequently grants camera
      await requestPermission("camera");
      let current = await checkAllPermissions();
      expect(current.camera).toBe("granted");
      expect(getMissingPermissions(current)).toEqual(["microphone"]);

      // User subsequently grants microphone
      await requestPermission("microphone");
      current = await checkAllPermissions();
      expect(areAllPermissionsGranted(current)).toBe(true);
      expect(getMissingPermissions(current)).toHaveLength(0);
    });

    it("opens app settings when user triggers openAppSettings", async () => {
      await openAppSettings();
      expect(mockAdapter.openSettingsCalled).toBe(true);
    });

    it("handles blocked permissions where user must visit system settings", async () => {
      await setCompletedInitialPrompt(true);
      mockAdapter.state = {
        notifications: "granted",
        microphone: "blocked",
        camera: "granted",
      };

      const current = await checkAllPermissions();
      expect(areAllPermissionsGranted(current)).toBe(false);
      expect(getMissingPermissions(current)).toEqual(["microphone"]);
      expect(current.microphone).toBe("blocked");

      // Requesting a blocked permission keeps it blocked until settings changed
      const res = await requestPermission("microphone");
      expect(res).toBe("blocked");

      // User goes to settings and toggles it to granted
      mockAdapter.state.microphone = "granted";
      const updated = await checkAllPermissions();
      expect(areAllPermissionsGranted(updated)).toBe(true);
    });
  });

  describe("Helper Utilities", () => {
    it("areAllPermissionsGranted returns true only when all three are granted", () => {
      expect(
        areAllPermissionsGranted({
          notifications: "granted",
          microphone: "granted",
          camera: "granted",
        })
      ).toBe(true);

      expect(
        areAllPermissionsGranted({
          notifications: "granted",
          microphone: "granted",
          camera: "denied",
        })
      ).toBe(false);

      expect(
        areAllPermissionsGranted({
          notifications: "undetermined",
          microphone: "granted",
          camera: "granted",
        })
      ).toBe(false);
    });

    it("getMissingPermissions accurately lists ungranted permissions", () => {
      expect(
        getMissingPermissions({
          notifications: "granted",
          microphone: "denied",
          camera: "blocked",
        })
      ).toEqual(["microphone", "camera"]);

      expect(
        getMissingPermissions({
          notifications: "granted",
          microphone: "granted",
          camera: "granted",
        })
      ).toEqual([]);
    });
  });
});
