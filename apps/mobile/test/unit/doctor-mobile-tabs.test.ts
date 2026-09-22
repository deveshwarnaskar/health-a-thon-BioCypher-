import { describe, expect, it } from "vitest";
import {
  resolveInitialDoctorState,
  getSubWorkspaceTitle,
  getTabTitle,
  DOCTOR_TABS_CONFIG,
  type DoctorTab,
} from "../../src/features/doctor/doctorNavigation";

describe("Doctor Mobile Experience Navigation & Tab Architecture", () => {
  describe("DOCTOR_TABS contract", () => {
    it("defines exactly 5 canonical mobile destinations matching patient architecture", () => {
      expect(DOCTOR_TABS_CONFIG.length).toBe(5);
      const keys = DOCTOR_TABS_CONFIG.map((t) => t.key);
      expect(keys).toEqual(["dashboard", "patients", "review", "tasks", "workspace"]);
    });

    it("assigns distinct accessibility labels and icons to all tabs", () => {
      for (const tab of DOCTOR_TABS_CONFIG) {
        expect(tab.label.length).toBeGreaterThan(0);
        expect(tab.accessibilityLabel.length).toBeGreaterThan(0);
        expect(tab.iconActive).toBeDefined();
        expect(tab.iconInactive).toBeDefined();
        expect(tab.iconActive).not.toEqual(tab.iconInactive);
      }
    });
  });

  describe("resolveInitialDoctorState", () => {
    it("resolves undefined or null flow to dashboard", () => {
      expect(resolveInitialDoctorState(undefined)).toEqual({ tab: "dashboard", sub: null });
      expect(resolveInitialDoctorState(null)).toEqual({ tab: "dashboard", sub: null });
      expect(resolveInitialDoctorState("overview")).toEqual({ tab: "dashboard", sub: null });
    });

    it("resolves cohort and patients flow to patients tab", () => {
      expect(resolveInitialDoctorState("cohort")).toEqual({ tab: "patients", sub: null });
      expect(resolveInitialDoctorState("patients")).toEqual({ tab: "patients", sub: null });
    });

    it("resolves review flow to review tab", () => {
      expect(resolveInitialDoctorState("review")).toEqual({ tab: "review", sub: null });
    });

    it("resolves tasks flow to tasks tab", () => {
      expect(resolveInitialDoctorState("tasks")).toEqual({ tab: "tasks", sub: null });
    });

    it("resolves specialized workstations to workspace tab with active sub-workspace", () => {
      expect(resolveInitialDoctorState("monitoring")).toEqual({
        tab: "workspace",
        sub: "monitoring",
      });
      expect(resolveInitialDoctorState("reports")).toEqual({
        tab: "workspace",
        sub: "reports",
      });
      expect(resolveInitialDoctorState("plans")).toEqual({
        tab: "workspace",
        sub: "plans",
      });
      expect(resolveInitialDoctorState("documents")).toEqual({
        tab: "workspace",
        sub: "documents",
      });
      expect(resolveInitialDoctorState("messages")).toEqual({
        tab: "workspace",
        sub: "messages",
      });
      expect(resolveInitialDoctorState("audit")).toEqual({
        tab: "workspace",
        sub: "audit",
      });
    });
  });

  describe("Title Resolution", () => {
    it("provides human-readable titles for all primary tabs", () => {
      expect(getTabTitle("dashboard")).toBe("Clinical Overview");
      expect(getTabTitle("patients")).toBe("Patient Directory");
      expect(getTabTitle("review")).toBe("AI Review Queue");
      expect(getTabTitle("tasks")).toBe("Care Tasks");
      expect(getTabTitle("workspace")).toBe("Clinical Hub");
    });

    it("provides human-readable titles for all specialized sub-workspaces", () => {
      expect(getSubWorkspaceTitle("monitoring")).toBe("Longitudinal Monitoring");
      expect(getSubWorkspaceTitle("reports")).toBe("Clinical Reports");
      expect(getSubWorkspaceTitle("plans")).toBe("Medication Plans");
      expect(getSubWorkspaceTitle("documents")).toBe("Document Vault");
      expect(getSubWorkspaceTitle("messages")).toBe("Patient Communications");
      expect(getSubWorkspaceTitle("audit")).toBe("Security & Audit");
    });
  });
});
