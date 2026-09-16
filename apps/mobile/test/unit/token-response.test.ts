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
});
