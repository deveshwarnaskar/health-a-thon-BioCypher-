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

  it("enforces HTTPS and rejects localhost in production environment", () => {
    const prodLocalhost = readApiConfig({
      EXPO_PUBLIC_ENVIRONMENT: "production",
      EXPO_PUBLIC_API_BASE_URL: "http://localhost:8000",
    });
    expect(() => requireConfigured(prodLocalhost)).toThrow(
      "Production environment requires a secure HTTPS API endpoint, non-localhost",
    );

    const prodHttp = readApiConfig({
      EXPO_PUBLIC_ENVIRONMENT: "production",
      EXPO_PUBLIC_API_BASE_URL: "http://api.thali.in",
    });
    expect(() => requireConfigured(prodHttp)).toThrow(
      "Production environment requires a secure HTTPS API endpoint, non-localhost",
    );

    const prodHttps = readApiConfig({
      EXPO_PUBLIC_ENVIRONMENT: "production",
      EXPO_PUBLIC_API_BASE_URL: "https://api.thali.in",
    });
    expect(requireConfigured(prodHttps).apiBaseUrl).toBe("https://api.thali.in");
  });
});