import { describe, it, expect } from "vitest";
import { denialReasonFromApiError, denialMessage } from "../../src/auth/denial";
import type { ApiErrorDetails } from "../../src/services/api/errors";

function apiError(overrides: Partial<ApiErrorDetails> = {}): ApiErrorDetails {
  return {
    kind: "UNKNOWN",
    httpStatus: overrides.httpStatus ?? 403,
    code: overrides.code ?? "FORBIDDEN",
    message: overrides.message ?? "forbidden",
    forbiddenReason: overrides.forbiddenReason,
  };
}

describe("denial", () => {
  describe("denialReasonFromApiError", () => {
    it("401 → deactivated", () => {
      expect(denialReasonFromApiError(apiError({ httpStatus: 401 }))).toBe("deactivated");
    });
    it("403 unlinked_identity → unlinked_identity", () => {
      expect(
        denialReasonFromApiError(apiError({ httpStatus: 403, forbiddenReason: "unlinked_identity" }))
      ).toBe("unlinked_identity");
    });
    it("403 revoked_relationship → caregiver_revoked", () => {
      expect(
        denialReasonFromApiError(apiError({ httpStatus: 403, forbiddenReason: "revoked_relationship" }))
      ).toBe("caregiver_revoked");
    });
    it("403 expired_relationship → caregiver_expired", () => {
      expect(
        denialReasonFromApiError(apiError({ httpStatus: 403, forbiddenReason: "expired_relationship" }))
      ).toBe("caregiver_expired");
    });
    it("403 facility_mismatch → facility_mismatch", () => {
      expect(
        denialReasonFromApiError(apiError({ httpStatus: 403, forbiddenReason: "facility_mismatch" }))
      ).toBe("facility_mismatch");
    });
    it("403 insufficient_capability → insufficient_capability", () => {
      expect(
        denialReasonFromApiError(apiError({ httpStatus: 403, forbiddenReason: "insufficient_capability" }))
      ).toBe("insufficient_capability");
    });
    it("403 authorization_denied → general", () => {
      expect(
        denialReasonFromApiError(apiError({ httpStatus: 403, forbiddenReason: "authorization_denied" }))
      ).toBe("general");
    });
    it("non-401/403 → general", () => {
      expect(denialReasonFromApiError(apiError({ httpStatus: 500 }))).toBe("general");
    });
  });

  describe("denialMessage", () => {
    it("returns a human-readable message for every reason", () => {
      const reasons = [
        "unknown_role",
        "unlinked_identity",
        "caregiver_revoked",
        "caregiver_expired",
        "facility_mismatch",
        "insufficient_capability",
        "deactivated",
        "general",
      ] as const;
      for (const reason of reasons) {
        expect(typeof denialMessage(reason)).toBe("string");
        expect(denialMessage(reason).length).toBeGreaterThan(10);
      }
    });
  });
});
