import { afterEach, describe, expect, it } from "vitest";
import {
  ApiConfigError,
  getApiConfig,
  readApiConfig,
  requireConfigured,
  resetApiConfig,
} from "../../src/services/api/config";

afterEach(() => {
  resetApiConfig();
  delete process.env.EXPO_PUBLIC_API_BASE_URL;
  delete process.env.EXPO_PUBLIC_AUTH_ENABLED;
  delete process.env.EXPO_PUBLIC_ENVIRONMENT;
});

describe("API URL configuration (anti hard-coded URLs)", () => {
  it("reads the client-safe base URL from EXPO_PUBLIC_ env", () => {
    process.env.EXPO_PUBLIC_API_BASE_URL = "http://backend.test:8000";
    expect(readApiConfig().apiBaseUrl).toBe("http://backend.test:8000");
  });

  it("defaults auth to off and environment to development when unset", () => {
    const config = readApiConfig({});
    expect(config.authEnabled).toBe(false);
    expect(config.environment).toBe("development");
  });

  it("resolves configuration lazily from process.env", () => {
    process.env.EXPO_PUBLIC_API_BASE_URL = "http://api.local/v2";
    expect(getApiConfig().apiBaseUrl).toBe("http://api.local/v2");
  });

  it("fails loudly when no base URL is configured", () => {
    expect(() => requireConfigured(readApiConfig({}))).toThrow(ApiConfigError);
    expect(() => requireConfigured(readApiConfig({})).apiBaseUrl).toThrow(
      "EXPO_PUBLIC_API_BASE_URL",
    );
  });
});