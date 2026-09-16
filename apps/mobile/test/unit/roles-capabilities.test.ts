import { describe, expect, it } from "vitest";
import { roleFromAuthRoles, roleLabel, ROLES } from "../../src/authz/roles";
import { can, capabilitiesForRole } from "../../src/authz/capabilities";
import { destinationsForRole } from "../../src/authz/navigation";

describe("role identity and capability model (ROLE vs CAPABILITY)", () => {
  it("resolves backend role tokens to platform roles", () => {
    expect(roleFromAuthRoles(["doctor"])).toBe("Doctor");
    expect(roleFromAuthRoles(["care_coordinator"])).toBe("CareCoordinator");
    expect(roleFromAuthRoles(["field_health_worker"])).toBe("FieldHealthWorker");
    expect(roleFromAuthRoles(["patient"])).toBe("Patient");
  });

  it("never maps unknown role tokens (no privilege fabrication)", () => {
    expect(roleFromAuthRoles(["superuser"])).toBeNull();
    expect(roleFromAuthRoles([])).toBeNull();
    expect(roleFromAuthRoles(["doctor ", "caregiver"])).toBe("Caregiver");
  });

  it("separates ROLE identity from CAPABILITY grants", () => {
    const patientCapabilities = capabilitiesForRole("Patient");
    expect(patientCapabilities).toContain("WRITE_OBSERVATIONS");
    expect(can("Doctor", "REVIEW_AI_ARTIFACT")).toBe(true);
    expect(can("Patient", "REVIEW_AI_ARTIFACT")).toBe(false);
  });

  it("reflects the Gate 10A surface-mode capability matrix", () => {
    expect(capabilitiesForRole("Caregiver")).toEqual(
      expect.arrayContaining(["READ_GLUCOSE", "READ_MEAL", "CREATE_GLUCOSE", "CREATE_MEAL"]),
    );
    expect(capabilitiesForRole("CareCoordinator")).toContain(
      "MANAGE_CAREGIVER_RELATIONSHIPS",
    );
    expect(capabilitiesForRole("FieldHealthWorker")).not.toContain("WRITE_MEDICATION_PLANS");
  });

  it("declares placeholders for all 7 platform roles", () => {
    expect(ROLES).toEqual([
      "Patient",
      "Caregiver",
      "Doctor",
      "Nurse",
      "CareCoordinator",
      "Dietitian",
      "FieldHealthWorker",
    ]);
    for (const role of ROLES) {
      expect(roleLabel(role)).toBeTruthy();
      expect(destinationsForRole(role).length).toBeGreaterThan(0);
    }
  });
});