import { describe, it, expect } from "vitest";
import { buildAuthUser } from "../../src/auth/authenticatedUser";
import type { AuthenticatedContext } from "../../src/auth/types";

describe("authenticatedUser", () => {
  it("resolves a known role and its capabilities", () => {
    const ctx: AuthenticatedContext = {
      actor_id: "a-1",
      tenant_id: "t-1",
      facility_id: "f-1",
      roles: ["patient"],
    };
    const user = buildAuthUser(ctx);
    expect(user.role).toBe("Patient");
    expect(user.capabilities.length).toBeGreaterThan(0);
    expect(user.actor_id).toBe("a-1");
    expect(user.tenant_id).toBe("t-1");
    expect(user.facility_id).toBe("f-1");
    expect(user.roles).toEqual(["patient"]);
  });

  it("returns null role and empty capabilities for an unknown role token", () => {
    const ctx: AuthenticatedContext = {
      actor_id: "a-2",
      tenant_id: "t-2",
      facility_id: null,
      roles: ["unknown_role_xyz"],
    };
    const user = buildAuthUser(ctx);
    expect(user.role).toBeNull();
    expect(user.capabilities).toEqual([]);
    expect(user.roles).toEqual(["unknown_role_xyz"]);
  });

  it("sets facility_id to null when the backend omits it", () => {
    const user = buildAuthUser({
      actor_id: "a-3",
      tenant_id: "t-3",
      roles: ["doctor"],
    } as unknown as AuthenticatedContext);
    expect(user.facility_id).toBeNull();
  });
});
