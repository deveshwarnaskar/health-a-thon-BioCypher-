import { describe, it, expect } from "vitest";
import {
  readOidcConfig,
  parseOidcScopes,
  requireOidcConfigured,
  buildDiscoveryUrl,
  OidcConfigError,
  oidcConfigSchema,
  DEFAULT_SCOPES,
} from "../../src/auth/oidcConfig";

describe("oidcConfig", () => {
  describe("readOidcConfig", () => {
    it("reads EXPO_PUBLIC_KEYCLOAK_* variables from the provided env", () => {
      const env = {
        EXPO_PUBLIC_KEYCLOAK_ISSUER_URL: "http://keycloak.test/realms/demo",
        EXPO_PUBLIC_KEYCLOAK_REALM: "demo",
        EXPO_PUBLIC_KEYCLOAK_CLIENT_ID: "my-app",
        EXPO_PUBLIC_KEYCLOAK_REDIRECT_URI: "myapp://callback",
      };
      const config = readOidcConfig(env);
      expect(config.issuerUrl).toBe("http://keycloak.test/realms/demo");
      expect(config.realm).toBe("demo");
      expect(config.clientId).toBe("my-app");
      expect(config.redirectUri).toBe("myapp://callback");
    });

    it("defaults scopes to DEFAULT_SCOPES when EXPO_PUBLIC_KEYCLOAK_SCOPES is absent", () => {
      const config = readOidcConfig({});
      expect(config.scopes).toEqual(DEFAULT_SCOPES);
    });
  });

  describe("parseOidcScopes", () => {
    it("splits space-separated scopes and deduplicates", () => {
      expect(parseOidcScopes("openid email email profile")).toEqual(["openid", "email", "profile"]);
    });
    it("returns DEFAULT_SCOPES for undefined/empty input", () => {
      expect(parseOidcScopes(undefined)).toEqual(DEFAULT_SCOPES);
      expect(parseOidcScopes("   ")).toEqual(DEFAULT_SCOPES);
    });
  });

  describe("requireOidcConfigured", () => {
    it("throws OidcConfigError when a required field is missing", () => {
      expect(() => requireOidcConfigured(readOidcConfig({}))).toThrow(OidcConfigError);
      expect(() =>
        requireOidcConfigured({
          issuerUrl: "http://issuer",
          realm: "",
          clientId: "c",
          redirectUri: "r",
          scopes: ["openid"],
        })
      ).toThrow(OidcConfigError);
    });

    it("returns the config unchanged when all fields are present", () => {
      const env = {
        EXPO_PUBLIC_KEYCLOAK_ISSUER_URL: "http://issuer",
        EXPO_PUBLIC_KEYCLOAK_REALM: "r",
        EXPO_PUBLIC_KEYCLOAK_CLIENT_ID: "c",
        EXPO_PUBLIC_KEYCLOAK_REDIRECT_URI: "redir",
      };
      expect(requireOidcConfigured(readOidcConfig(env))).toEqual(
        expect.objectContaining({ issuerUrl: "http://issuer" })
      );
    });
  });

  describe("buildDiscoveryUrl", () => {
    it("appends .well-known/openid-configuration, stripping trailing slashes", () => {
      expect(buildDiscoveryUrl("http://keycloak.test/realms/thali")).toBe(
        "http://keycloak.test/realms/thali/.well-known/openid-configuration"
      );
      expect(buildDiscoveryUrl("http://keycloak.test/realms/thali/")).toBe(
        "http://keycloak.test/realms/thali/.well-known/openid-configuration"
      );
    });
  });

  describe("oidcConfigSchema", () => {
    it("accepts a valid config object", () => {
      const result = oidcConfigSchema.safeParse({
        issuerUrl: "http://issuer",
        realm: "r",
        clientId: "c",
        redirectUri: "redir",
        scopes: ["openid"],
      });
      expect(result.success).toBe(true);
    });
    it("rejects an object with extra keys", () => {
      const result = oidcConfigSchema.safeParse({
        issuerUrl: "http://issuer",
        realm: "r",
        clientId: "c",
        redirectUri: "redir",
        scopes: ["openid"],
        extra: "nope",
      });
      expect(result.success).toBe(false);
    });
  });
});
