import { describe, it, expect, beforeEach } from "vitest";
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "./setup";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { tokenStorage } from "../src/auth/tokenStorage";
import { AuthContext } from "../src/auth/authContext";
import { MemoryRouter } from "react-router-dom";
import { DashboardPage } from "../src/dashboard/DashboardPage";
import { FacilitiesPage } from "../src/facilities/FacilitiesPage";
import { CareTeamPage } from "../src/care-team/CareTeamPage";
import { PatientsPage } from "../src/patients/PatientsPage";
import { IdentityMappingsPage } from "../src/identity-mappings/IdentityMappingsPage";
import { AuditPage } from "../src/audit/AuditPage";

const mockAdminUser = {
  actor_id: "550e8400-e29b-41d4-a716-446655440001",
  tenant_id: "550e8400-e29b-41d4-a716-446655440099",
  roles: ["admin"],
  facility_id: null,
};

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider
        value={{
          user: mockAdminUser,
          isAuthenticated: true,
          isAdmin: true,
          isLoading: false,
          error: null,
          login: async () => {},
          logout: () => {},
          verifySession: async () => {},
          handleOidcCallback: async () => {},
        }}
      >
        <MemoryRouter>{ui}</MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("Operational Admin Workflows", () => {
  beforeEach(() => {
    tokenStorage.setTokens({ accessToken: "mock-admin-token" });
  });

  describe("Dashboard Workflow", () => {
    it("renders operational counts and control plane readiness", async () => {
      server.use(
        http.get("*/api/v2/admin/facilities", () =>
          HttpResponse.json({
            total: 3,
            items: [
              { facility_id: "f-1", name: "Facility Alpha", active: true, created_at: "2026-09-17" },
              { facility_id: "f-2", name: "Facility Beta", active: true, created_at: "2026-09-17" },
              { facility_id: "f-3", name: "Facility Gamma", active: false, created_at: "2026-09-17" },
            ],
          }),
        ),
        http.get("*/api/v2/admin/care-team-members", () =>
          HttpResponse.json({
            total: 4,
            items: [
              { member_id: "m-1", user_id: "u-1", role: "doctor", display_name: "Dr. A", active: true },
              { member_id: "m-2", user_id: "u-2", role: "nurse", display_name: "Nurse B", active: true },
            ],
          }),
        ),
        http.get("*/api/v2/admin/patients", () =>
          HttpResponse.json({
            total: 2,
            items: [
              {
                patient_id: "p-1",
                uh_id: "UHID-1",
                name: "Patient One",
                active: true,
                has_active_mapping: true,
                created_at: "2026-09-17",
              },
            ],
          }),
        ),
        http.get("*/api/v2/admin/identity-mappings", () =>
          HttpResponse.json([
            {
              mapping_id: "map-1",
              user_id: "u-1",
              patient_id: "p-1",
              active: true,
              created_at: "2026-09-17",
            },
          ]),
        ),
      );

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText("Operational Dashboard")).toBeInTheDocument();
        expect(screen.getByText("Control Plane & Security Readiness")).toBeInTheDocument();
      });

      expect(screen.getByText("PostgreSQL RLS")).toBeInTheDocument();
      expect(screen.getByText("Mutation Idempotency")).toBeInTheDocument();
      expect(screen.getByText("Clinical Boundary")).toBeInTheDocument();
    });
  });

  describe("Facilities Workflow", () => {
    it("lists facilities and supports creation with Idempotency-Key", async () => {
      let createdWithKey: string | null = null;

      server.use(
        http.get("*/api/v2/admin/facilities", () =>
          HttpResponse.json({
            total: 1,
            items: [
              { facility_id: "f-1", name: "City Hospital", active: true, created_at: "2026-09-17" },
            ],
          }),
        ),
        http.post("*/api/v2/admin/facilities", ({ request }) => {
          createdWithKey = request.headers.get("Idempotency-Key");
          return HttpResponse.json({
            facility_id: "f-new",
            name: "Community Clinic",
            active: true,
            created_at: "2026-09-17",
          });
        }),
      );

      renderWithProviders(<FacilitiesPage />);

      await waitFor(() => {
        expect(screen.getByText("City Hospital")).toBeInTheDocument();
      });

      // Open create modal
      fireEvent.click(screen.getByRole("button", { name: /Create Facility/i }));
      await waitFor(() => {
        expect(screen.getByText("Register a new operational facility for this tenant. Tenant assignment is automatic.")).toBeInTheDocument();
      });

      // Enter facility name
      const input = screen.getByPlaceholderText("e.g. City Health Clinic");
      fireEvent.change(input, { target: { value: "Community Clinic" } });

      // Submit form
      fireEvent.submit(input.closest("form")!);

      await waitFor(() => {
        expect(createdWithKey).toBeTruthy();
      });
      expect(createdWithKey).toMatch(/^[0-9a-f-]{36}$/);
    });
  });

  describe("Care Team Workflow", () => {
    it("provisions a care-team member with canonical role and Idempotency-Key", async () => {
      let capturedRole: string | null = null;
      let capturedKey: string | null = null;

      server.use(
        http.get("*/api/v2/admin/care-team-members", () =>
          HttpResponse.json({
            total: 0,
            items: [],
          }),
        ),
        http.get("*/api/v2/admin/facilities", () =>
          HttpResponse.json({
            total: 1,
            items: [{ facility_id: "550e8400-e29b-41d4-a716-446655440099", name: "North Wing", active: true, created_at: "2026-09-17" }],
          }),
        ),
        http.post("*/api/v2/admin/care-team-members", async ({ request }) => {
          capturedKey = request.headers.get("Idempotency-Key");
          const body = (await request.json()) as { role: string };
          capturedRole = body.role;
          return HttpResponse.json({
            member_id: "m-new",
            user_id: "550e8400-e29b-41d4-a716-446655440010",
            role: "doctor",
            display_name: "Dr. Arvind",
            facility_id: "550e8400-e29b-41d4-a716-446655440099",
            active: true,
          });
        }),
      );

      renderWithProviders(<CareTeamPage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Provision Member/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: /Provision Member/i }));

      // Fill in user id, name, and select facility
      const userIdInput = screen.getByPlaceholderText("e.g. 550e8400-e29b-41d4-a716-446655440000");
      fireEvent.change(userIdInput, {
        target: { value: "550e8400-e29b-41d4-a716-446655440010" },
      });
      fireEvent.change(screen.getByPlaceholderText("e.g. Dr. Jane Doe"), {
        target: { value: "Dr. Arvind" },
      });
      fireEvent.change(screen.getByLabelText(/Assigned Facility/i), {
        target: { value: "550e8400-e29b-41d4-a716-446655440099" },
      });

      // Submit form
      fireEvent.submit(userIdInput.closest("form")!);

      await waitFor(() => {
        expect(capturedKey).toBeTruthy();
        expect(capturedRole).toBe("doctor");
      });
    });
  });

  describe("Patient Directory Workflow", () => {
    it("provisions a patient and inspects PHI-minimized details", async () => {
      server.use(
        http.get("*/api/v2/admin/facilities", () =>
          HttpResponse.json({ total: 0, items: [] }),
        ),
        http.get("*/api/v2/admin/patients", () =>
          HttpResponse.json({
            total: 1,
            items: [
              {
                patient_id: "p-100",
                uh_id: "UHID-7788",
                name: "Anita Devi",
                facility_id: null,
                phone: "+919876543299",
                active: true,
                has_active_mapping: false,
                created_at: "2026-09-17T09:00:00Z",
              },
            ],
          }),
        ),
      );

      renderWithProviders(<PatientsPage />);

      await waitFor(() => {
        expect(screen.getByText("Anita Devi")).toBeInTheDocument();
        expect(screen.getByText("UHID-7788")).toBeInTheDocument();
      });

      // Click details button
      fireEvent.click(screen.getByLabelText("View details for Anita Devi"));

      await waitFor(() => {
        expect(screen.getByText("Patient Record: Anita Devi")).toBeInTheDocument();
        expect(
          screen.getByText(/Clinical observations and health telemetry are strictly restricted/),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Identity Mappings Workflow", () => {
    it("binds an identity to a patient with Idempotency-Key", async () => {
      let capturedKey: string | null = null;

      server.use(
        http.get("*/api/v2/admin/patients", () =>
          HttpResponse.json({
            total: 1,
            items: [
              {
                patient_id: "550e8400-e29b-41d4-a716-446655440050",
                uh_id: "UHID-50",
                name: "Suresh",
                active: true,
                has_active_mapping: false,
                created_at: "2026-09-17",
              },
            ],
          }),
        ),
        http.get("*/api/v2/admin/identity-mappings", () =>
          HttpResponse.json([]),
        ),
        http.post("*/api/v2/admin/identity-mappings", ({ request }) => {
          capturedKey = request.headers.get("Idempotency-Key");
          return HttpResponse.json({
            mapping_id: "map-50",
            user_id: "550e8400-e29b-41d4-a716-446655440060",
            patient_id: "550e8400-e29b-41d4-a716-446655440050",
            active: true,
            created_at: "2026-09-17",
          });
        }),
      );

      renderWithProviders(<IdentityMappingsPage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Bind Identity/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: /Bind Identity/i }));

      const userInput = screen.getByPlaceholderText("e.g. 550e8400-e29b-41d4-a716-446655440000");
      fireEvent.change(userInput, {
        target: { value: "550e8400-e29b-41d4-a716-446655440060" },
      });
      fireEvent.change(screen.getByLabelText(/Target Patient/i), {
        target: { value: "550e8400-e29b-41d4-a716-446655440050" },
      });

      fireEvent.submit(userInput.closest("form")!);

      await waitFor(() => {
        expect(capturedKey).toBeTruthy();
      });
    });
  });

  describe("Audit Trail Workflow", () => {
    it("renders read-only audit log and filters without mutation capability", async () => {
      server.use(
        http.get("*/api/v2/admin/audit-events", () =>
          HttpResponse.json([
            {
              audit_event_id: "aud-1",
              tenant_id: "t-1",
              actor_id: "a-1",
              actor_type: "user",
              action: "CREATE",
              resource_type: "facility",
              resource_id: "f-1",
              occurred_at: "2026-09-17T12:00:00Z",
              correlation_id: "corr-1",
              source_ip: "10.0.0.1",
              outcome: "SUCCESS",
              reason: null,
            },
          ]),
        ),
      );

      renderWithProviders(<AuditPage />);

      await waitFor(() => {
        expect(screen.getByText("Audit Trail")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /View audit event aud-1/i })).toBeInTheDocument();
      });

      // Check that there is NO create/delete button on audit page
      expect(screen.queryByText("Create Event")).not.toBeInTheDocument();
      expect(screen.queryByText("Delete")).not.toBeInTheDocument();

      // Inspect details
      fireEvent.click(screen.getByRole("button", { name: /View audit event/i }));

      await waitFor(() => {
        expect(screen.getByText("Audit Event Inspection")).toBeInTheDocument();
        expect(screen.getByText("Read-only immutable audit record details.")).toBeInTheDocument();
      });
    });
  });
});
