import { describe, it, expect } from "vitest";
import { classifyRefreshOutcome, TokenEndpointError, TokenNetworkError, AuthTransientError } from "../../src/auth/tokenEndpoint";

describe("tokenEndpoint", () => {
  describe("classifyRefreshOutcome", () => {
    it("TokenNetworkError → transient", () => {
      expect(classifyRefreshOutcome(new TokenNetworkError())).toBe("transient");
    });
    it("TokenEndpointError httpStatus >= 500 → transient", () => {
      expect(classifyRefreshOutcome(new TokenEndpointError("Server error", 503))).toBe("transient");
    });
    it("TokenEndpointError httpStatus 429 → transient", () => {
      expect(classifyRefreshOutcome(new TokenEndpointError("Rate limited", 429))).toBe("transient");
    });
    it("TokenEndpointError invalid_grant → invalid_session_input", () => {
      expect(
        classifyRefreshOutcome(new TokenEndpointError("Bad grant", 400, "invalid_grant"))
      ).toBe("invalid_session_input");
    });
    it("TokenEndpointError invalid_client → invalid_session_input", () => {
      expect(
        classifyRefreshOutcome(new TokenEndpointError("Bad client", 400, "invalid_client"))
      ).toBe("invalid_session_input");
    });
    it("unknown error → invalid_session_input", () => {
      expect(classifyRefreshOutcome(new Error("something"))).toBe("invalid_session_input");
    });
  });

  describe("AuthTransientError", () => {
    it("sets a user-friendly message for network category", () => {
      const err = new AuthTransientError("network");
      expect(err.category).toBe("network");
      expect(err.name).toBe("AuthTransientError");
      expect(err.message).toMatch(/check your connection/i);
    });
    it("sets a user-friendly message for server_unavailable category", () => {
      const err = new AuthTransientError("server_unavailable");
      expect(err.message).toMatch(/temporarily unavailable/i);
    });
  });
});
