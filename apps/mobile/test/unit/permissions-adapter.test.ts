import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  DefaultPermissionAdapter,
  setPermissionAdapterForTesting,
} from "../../src/services/permissions/permissionAdapter";
import { clearPermissionStorageForTesting } from "../../src/services/permissions/permissionStorage";
import { Linking, PermissionsAndroid, Platform } from "react-native";

describe("DefaultPermissionAdapter & Platform Native Mapping", () => {
  let adapter: DefaultPermissionAdapter;

  beforeEach(() => {
    clearPermissionStorageForTesting();
    vi.clearAllMocks();
    adapter = new DefaultPermissionAdapter();
    setPermissionAdapterForTesting(adapter);
    (Platform as any).OS = "android";
    (Platform as any).Version = 34;
  });

  it("checks camera permission using PermissionsAndroid", async () => {
    vi.mocked(PermissionsAndroid.check).mockResolvedValueOnce(true);
    const status = await adapter.check("camera");
    expect(PermissionsAndroid.check).toHaveBeenCalledWith(
      "android.permission.CAMERA"
    );
    expect(status).toBe("granted");
  });

  it("checks microphone permission using PermissionsAndroid", async () => {
    vi.mocked(PermissionsAndroid.check).mockResolvedValueOnce(false);
    const status = await adapter.check("microphone");
    expect(PermissionsAndroid.check).toHaveBeenCalledWith(
      "android.permission.RECORD_AUDIO"
    );
    expect(status).toBe("denied");
  });

  it("checks notification permission on Android 33+ (API 34)", async () => {
    vi.mocked(PermissionsAndroid.check).mockResolvedValueOnce(true);
    const status = await adapter.check("notifications");
    expect(PermissionsAndroid.check).toHaveBeenCalledWith(
      "android.permission.POST_NOTIFICATIONS"
    );
    expect(status).toBe("granted");
  });

  it("auto-grants notification check on older Android versions (<33)", async () => {
    (Platform as any).Version = 30;
    const status = await adapter.check("notifications");
    expect(status).toBe("granted");
  });

  it("requests multiple permissions on Android simultaneously", async () => {
    vi.mocked(PermissionsAndroid.requestMultiple).mockResolvedValueOnce({
      "android.permission.CAMERA": "granted",
      "android.permission.RECORD_AUDIO": "granted",
      "android.permission.POST_NOTIFICATIONS": "granted",
    } as any);

    const result = await adapter.requestAll();
    expect(result).toEqual({
      camera: "granted",
      microphone: "granted",
      notifications: "granted",
    });
  });

  it("maps NEVER_ASK_AGAIN to blocked on Android", async () => {
    vi.mocked(PermissionsAndroid.requestMultiple).mockResolvedValueOnce({
      "android.permission.CAMERA": "granted",
      "android.permission.RECORD_AUDIO": "never_ask_again",
      "android.permission.POST_NOTIFICATIONS": "denied",
    } as any);

    const result = await adapter.requestAll();
    expect(result).toEqual({
      camera: "granted",
      microphone: "blocked",
      notifications: "denied",
    });
  });

  it("calls Linking.openSettings when openSettings is invoked", async () => {
    await adapter.openSettings();
    expect(Linking.openSettings).toHaveBeenCalled();
  });
});
