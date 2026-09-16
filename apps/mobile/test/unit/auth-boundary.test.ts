import { describe, expect, it, vi } from "vitest";
import {
  AuthNotConfiguredError,
  NotConfiguredAuthSessionProvider,
} from "../../src/auth/AuthSessionProvider";
import { createAuthExpiredSignal } from "../../src/auth/authSignal";
import { toAuthenticatedContext } from "../../src/auth/types";
import { isAuthExpiredSignal, mapHttpError } from "../../src/services/api/errors";

describe("auth boundary (401 → auth-expired signal, no fake refresh)", () => {
  it("exposes no token before Gate 10C wiring", async () => {
    const provider = new NotConfiguredAuthSessionProvider();
    await expect(provider.getAccessToken()).resolves.toBeNull();
    await expect(provider.clearSession()).resolves.toBeUndefined();
  });

  it("refuses to fake a token refresh (fails loud)", async () => {
    const provider = new NotConfiguredAuthSessionProvider();
    await expect(provider.refreshSession()).rejects.toBeInstanceOf(AuthNotConfiguredError);
  });

  it("derives an anonymous status until authentication exists", async () => {
    const provider = new NotConfiguredAuthSessionProvider();
    await expect(provider.getAuthenticatedContext()).resolves.toEqual({ state: "anonymous" });
  });

  it("emits a single observable auth-expired signal from any 401", () => {
    const signal = createAuthExpiredSignal();
    const listener = vi.fn();
    const unsubscribe = signal.subscribe(listener);

    const error = mapHttpError({ status: 401, body: { error: { code: "AUTHENTICATION_EXPIRED" } } });
    expect(isAuthExpiredSignal(error)).toBe(true);

    signal.emit(error);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(error);

    unsubscribe();
    signal.emit(error);
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("round-trips AuthVerifyResponse into an authenticated context", () => {
    const context = toAuthenticatedContext({
      actor_id: "u-1",
      tenant_id: "t-1",
      roles: ["doctor"],
      facility_id: "f-1",
    });
    expect(context).toEqual({
      actor_id: "u-1",
      tenant_id: "t-1",
      roles: ["doctor"],
      facility_id: "f-1",
    });
  });
});