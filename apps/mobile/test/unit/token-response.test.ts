import { describe, it, expect } from "vitest";
import { parseTokenResponse } from "../../src/auth/tokenResponse";

describe("tokenResponse", () => {
  it("parses a valid token response", () => {
    const res = parseTokenResponse({
      access_token: "at-123",
      refresh_token: "rt-456",
      id_token: "id-789",
      expires_in: 3600,
      token_type: "Bearer",
    });
    expect(res.access_token).toBe("at-123");
    expect(res.refresh_token).toBe("rt-456");
    expect(res.id_token).toBe("id-789");
    expect(res.expires_in).toBe(3600);
    expect(res.token_type).toBe("Bearer");
  });

  it("allows missing refresh_token and id_token", () => {
    const res = parseTokenResponse({
      access_token: "at-123",
      expires_in: 600,
      token_type: "Bearer",
    });
    expect(res.refresh_token).toBeUndefined();
    expect(res.id_token).toBeUndefined();
  });

  it("rejects responses with missing access_token", () => {
    expect(() =>
      parseTokenResponse({
        expires_in: 600,
        token_type: "Bearer",
      })
    ).toThrow();
  });

  it("rejects responses with non-Bearer token_type", () => {
    expect(() =>
      parseTokenResponse({
        access_token: "at-123",
        expires_in: 600,
        token_type: "basic",
      })
    ).toThrow();
  });

  it("rejects responses with non-positive expires_in", () => {
    expect(() =>
      parseTokenResponse({
        access_token: "at-123",
        expires_in: 0,
        token_type: "Bearer",
      })
    ).toThrow();
    expect(() =>
      parseTokenResponse({
        access_token: "at-123",
        expires_in: -10,
        token_type: "Bearer",
      })
    ).toThrow();
  });

  it("safely accepts standard Keycloak/OIDC provider responses with extra parameters per RFC 6749 Section 5.1", () => {
    const keycloakResponse = {
      access_token: "eyJhbGciOiJSUzI1NiIsInR5cCI...",
      expires_in: 300,
      refresh_expires_in: 1800,
      refresh_token: "eyJhbGciOiJIUzI1NiIsInR5cCI...",
      token_type: "Bearer",
      id_token: "eyJhbGciOiJSUzI1NiIsInR5cCI...",
      "not-before-policy": 0,
      session_state: "28a2a356-6c0f-4e99-9c56-4e80fb0b98cb",
      scope: "openid profile email offline_access",
    };
    const res = parseTokenResponse(keycloakResponse);
    expect(res.access_token).toBe(keycloakResponse.access_token);
    expect(res.refresh_token).toBe(keycloakResponse.refresh_token);
    expect(res.id_token).toBe(keycloakResponse.id_token);
    expect(res.expires_in).toBe(300);
    expect(res.token_type).toBe("Bearer");
    expect(res.scope).toBe("openid profile email offline_access");
  });
});
