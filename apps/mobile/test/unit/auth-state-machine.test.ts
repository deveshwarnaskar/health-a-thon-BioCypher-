import { describe, it, expect } from "vitest";
import {
  authStateReducer,
  INITIAL_STATE,
  type AuthFlowState,
} from "../../src/auth/authStateMachine";

function user(overrides?: Partial<{ role: string }>) {
  return {
    actor_id: "actor-1",
    tenant_id: "tenant-1",
    facility_id: null,
    role: overrides?.role ?? "patient",
    capabilities: ["view_own_records"],
    roles: ["patient"],
  };
}

describe("authStateReducer", () => {
  it("BOOTSTRAP_COMPLETE with no tokens → unauthenticated", () => {
    const next = authStateReducer(INITIAL_STATE, { type: "BOOTSTRAP_COMPLETE", hasTokens: false });
    expect(next.name).toBe("unauthenticated");
  });

  it("BOOTSTRAP_COMPLETE with tokens → bootstrapping", () => {
    const next = authStateReducer(INITIAL_STATE, { type: "BOOTSTRAP_COMPLETE", hasTokens: true });
    expect(next.name).toBe("bootstrapping");
  });

  it("AUTH_INITIATED from unauthenticated → authenticating", () => {
    const next = authStateReducer(
      { name: "unauthenticated" },
      { type: "AUTH_INITIATED" }
    );
    expect(next.name).toBe("authenticating");
  });

  it("AUTH_SUCCESS from authenticating → authenticated with user", () => {
    const u = user();
    const next = authStateReducer(
      { name: "authenticating" },
      { type: "AUTH_SUCCESS", user: u, accessToken: "at-1" }
    );
    expect(next.name).toBe("authenticated");
    expect(next).toHaveProperty("user");
    expect(next).toHaveProperty("accessToken", "at-1");
  });

  it("REFRESH_SUCCESS from authenticated → authenticated with new token", () => {
    const u = user();
    const state: AuthFlowState = { name: "authenticated", user: u, accessToken: "at-old" };
    const next = authStateReducer(state, { type: "REFRESH_SUCCESS", accessToken: "at-new" });
    expect(next.name).toBe("authenticated");
    expect(next).toHaveProperty("accessToken", "at-new");
  });

  it("REFRESH_FAILURE from session_expiring → session_expired", () => {
    const u = user();
    const state: AuthFlowState = { name: "session_expiring", user: u };
    const next = authStateReducer(state, { type: "REFRESH_FAILURE" });
    expect(next.name).toBe("session_expired");
  });

  it("LOGOUT from authenticated → unauthenticated", () => {
    const u = user();
    const state: AuthFlowState = { name: "authenticated", user: u, accessToken: "at-1" };
    const next = authStateReducer(state, { type: "LOGOUT" });
    expect(next.name).toBe("unauthenticated");
    expect(next).toHaveProperty("reason", "initial");
  });

  it("ACCESS_DENIED from authenticating → access_denied", () => {
    const next = authStateReducer(
      { name: "authenticating" },
      { type: "ACCESS_DENIED", reason: "unknown_role" }
    );
    expect(next.name).toBe("access_denied");
    expect(next).toHaveProperty("reason", "unknown_role");
  });

  it("DEACTIVATED from authenticated → deactivated", () => {
    const u = user();
    const state: AuthFlowState = { name: "authenticated", user: u, accessToken: "at-1" };
    const next = authStateReducer(state, { type: "DEACTIVATED" });
    expect(next.name).toBe("deactivated");
  });

  it("SESSION_EXPIRED is idempotent from session_expired", () => {
    const state: AuthFlowState = { name: "session_expired" };
    const next = authStateReducer(state, { type: "SESSION_EXPIRED" });
    expect(next.name).toBe("session_expired");
  });

  it("throws on an invalid transition (AUTH_INITIATED from session_expired is allowed)", () => {
    expect(() =>
      authStateReducer(
        { name: "session_expired" },
        { type: "AUTH_SUCCESS", user: user(), accessToken: "at-1" }
      )
    ).toThrow(/not allowed from state session_expired/);
  });
});
