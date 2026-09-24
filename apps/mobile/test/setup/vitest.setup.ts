import { vi } from "vitest";

// expo-crypto is a native-bound module. In the Node test environment we
// substitute the platform's own crypto.randomUUID implementation so the
// production UUID path (src/services/api/correlation.ts) is exercised
// without native modules.
vi.mock("expo-crypto", async () => {
  const { randomUUID } = await import("node:crypto");
  return { randomUUID };
});

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn().mockResolvedValue(null),
  setItemAsync: vi.fn().mockResolvedValue(undefined),
  deleteItemAsync: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("expo-av", () => ({
  Audio: {
    requestPermissionsAsync: vi.fn().mockResolvedValue({ status: "granted" }),
    getPermissionsAsync: vi.fn().mockResolvedValue({ status: "granted" }),
    setAudioModeAsync: vi.fn().mockResolvedValue(undefined),
    Recording: vi.fn().mockImplementation(() => ({
      prepareToRecordAsync: vi.fn().mockResolvedValue(undefined),
      startAsync: vi.fn().mockResolvedValue(undefined),
      stopAndUnloadAsync: vi.fn().mockResolvedValue(undefined),
      getURI: vi.fn().mockReturnValue("file:///tmp/mock-voice.m4a"),
    })),
    RecordingOptionsPresets: {
      HIGH_QUALITY: {},
    },
  },
}));

vi.mock("expo-file-system", () => ({
  readAsStringAsync: vi.fn().mockResolvedValue("bW9jay1hdWRpby1iYXNlNjQ="),
  EncodingType: {
    Base64: "base64",
  },
}));

vi.mock("expo-camera", () => ({
  CameraView: "CameraView",
  useCameraPermissions: vi.fn().mockReturnValue([
    { granted: true, canAskAgain: true, status: "granted" },
    vi.fn().mockResolvedValue({ granted: true, status: "granted" }),
  ]),
  getCameraPermissionsAsync: vi.fn().mockResolvedValue({ granted: true, status: "granted" }),
  requestCameraPermissionsAsync: vi.fn().mockResolvedValue({ granted: true, status: "granted" }),
}));

vi.mock("expo-image-picker", () => ({
  launchCameraAsync: vi.fn().mockResolvedValue({
    canceled: false,
    assets: [{ uri: "file:///mock/meal.jpg", base64: "bW9ja2Jhc2U2NA==", width: 400, height: 300 }],
  }),
  launchImageLibraryAsync: vi.fn().mockResolvedValue({
    canceled: false,
    assets: [{ uri: "file:///mock/meal.jpg", base64: "bW9ja2Jhc2U2NA==", width: 400, height: 300 }],
  }),
  requestCameraPermissionsAsync: vi.fn().mockResolvedValue({ granted: true, status: "granted" }),
  requestMediaLibraryPermissionsAsync: vi.fn().mockResolvedValue({ granted: true, status: "granted" }),
}));

vi.mock("react-native", () => ({
  Platform: {
    OS: "android",
    Version: 34,
    select: (obj: any) => obj.android ?? obj.default,
  },
  Linking: {
    openSettings: vi.fn().mockResolvedValue(undefined),
    openURL: vi.fn().mockResolvedValue(undefined),
  },
  PermissionsAndroid: {
    PERMISSIONS: {
      CAMERA: "android.permission.CAMERA",
      RECORD_AUDIO: "android.permission.RECORD_AUDIO",
      POST_NOTIFICATIONS: "android.permission.POST_NOTIFICATIONS",
    },
    RESULTS: {
      GRANTED: "granted",
      DENIED: "denied",
      NEVER_ASK_AGAIN: "never_ask_again",
    },
    check: vi.fn().mockResolvedValue(true),
    request: vi.fn().mockResolvedValue("granted"),
    requestMultiple: vi.fn().mockResolvedValue({}),
  },
  AppState: {
    addEventListener: vi.fn().mockReturnValue({ remove: vi.fn() }),
  },
  StyleSheet: {
    create: (styles: any) => styles,
  },
  Modal: "Modal",
  SafeAreaView: "SafeAreaView",
  ScrollView: "ScrollView",
  Text: "Text",
  TouchableOpacity: "TouchableOpacity",
  View: "View",
}));