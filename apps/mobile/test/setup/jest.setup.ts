/* eslint-env jest */

jest.mock("expo-av", () => ({
  Audio: {
    requestPermissionsAsync: jest.fn().mockResolvedValue({ status: "granted" }),
    getPermissionsAsync: jest.fn().mockResolvedValue({ status: "granted" }),
    setAudioModeAsync: jest.fn().mockResolvedValue(undefined),
    Recording: jest.fn().mockImplementation(() => ({
      prepareToRecordAsync: jest.fn().mockResolvedValue(undefined),
      startAsync: jest.fn().mockResolvedValue(undefined),
      stopAndUnloadAsync: jest.fn().mockResolvedValue(undefined),
      getURI: jest.fn().mockReturnValue("file:///tmp/mock-voice.m4a"),
    })),
    RecordingOptionsPresets: {
      HIGH_QUALITY: {},
    },
  },
}), { virtual: true });

jest.mock("expo-file-system", () => ({
  readAsStringAsync: jest.fn().mockResolvedValue("bW9jay1hdWRpby1iYXNlNjQ="),
  EncodingType: {
    Base64: "base64",
  },
}));
