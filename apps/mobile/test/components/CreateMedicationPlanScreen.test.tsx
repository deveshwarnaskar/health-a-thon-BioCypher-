import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CreateMedicationPlanScreen } from "../../src/features/doctor/CreateMedicationPlanScreen";
import type { PatientSummaryResponse } from "../../src/services/schemas/patients";
import type { ApiErrorDetails } from "../../src/services/api/errors";

let mockAuthState: {
  name: string;
  user: {
    role: string;
    actor_id: string;
    tenant_id: string;
    capabilities: string[];
    patient_id?: string | null;
  } | null;
} = {
  name: "authenticated",
  user: {
    role: "Doctor",
    actor_id: "doc-1",
    tenant_id: "tenant-1",
    capabilities: ["READ_OBSERVATIONS", "CREATE_MEDICATION_PLANS"],
    patient_id: null,
  },
};

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signOut: jest.fn(),
  }),
}));

let mockCreateState: {
  mutate: jest.Mock;
  mutateAsync: jest.Mock;
  isPending: boolean;
  isError: boolean;
  error: unknown;
  reset: jest.Mock;
} = {
  mutate: jest.fn(),
  mutateAsync: jest.fn(),
  isPending: false,
  isError: false,
  error: null,
  reset: jest.fn(),
};

const mockCreateCallbacks: {
  onSuccess?: (data: unknown) => void;
  onError?: (error: unknown) => void;
} = {};

jest.mock("../../src/features/doctor/useCreateMedicationPlan", () => ({
  useCreateMedicationPlan: (options?: {
    onSuccess?: (data: unknown) => void;
    onError?: (error: unknown) => void;
  }) => {
    mockCreateCallbacks.onSuccess = options?.onSuccess;
    mockCreateCallbacks.onError = options?.onError;
    return mockCreateState;
  },
}));

const PATIENT: PatientSummaryResponse = {
  patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  uh_id: "UH-001",
  name: "Aarav Sharma",
  facility_id: "facility-1",
  active: true,
  created_at: "2026-01-02T00:00:00Z",
};

function renderScreen(props?: {
  onCancel?: () => void;
  onCreated?: (data: unknown) => void;
}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <SafeAreaProvider
      initialMetrics={{
        frame: { x: 0, y: 0, width: 390, height: 844 },
        insets: { top: 0, left: 0, right: 0, bottom: 0 },
      }}
    >
      <QueryClientProvider client={queryClient}>
        <CreateMedicationPlanScreen patient={PATIENT} {...props} />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("CreateMedicationPlanScreen Component Tests (Gate 10F-M)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuthState = {
      name: "authenticated",
      user: {
        role: "Doctor",
        actor_id: "doc-1",
        tenant_id: "tenant-1",
        capabilities: ["READ_OBSERVATIONS", "CREATE_MEDICATION_PLANS"],
        patient_id: null,
      },
    };
    mockCreateState = {
      mutate: jest.fn(),
      mutateAsync: jest.fn(),
      isPending: false,
      isError: false,
      error: null,
      reset: jest.fn(),
    };
  });

  // Scenario 1: Doctor sees the clinician-authored plan form
  it("renders the plan form scoped to the selected patient", () => {
    renderScreen();
    expect(screen.getByText("Create Plan")).toBeTruthy();
    expect(screen.getByText("Aarav Sharma")).toBeTruthy();
    expect(screen.getByLabelText("Medication")).toBeTruthy();
    expect(screen.getByLabelText("Instruction")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Create plan/i })).toBeTruthy();
  });

  // Scenario 2: Missing medication blocks submission with a local message
  it("validates that a medication name is required", () => {
    renderScreen();
    fireEvent.press(screen.getByRole("button", { name: /Create plan/i }));

    expect(mockCreateState.mutate).not.toHaveBeenCalled();
    expect(screen.getByText("Medication name is required.")).toBeTruthy();
  });

  // Scenario 3: Valid submission sends ONLY patient_id/medication/instruction
  it("submits a body with no prescriber/facility fields", () => {
    renderScreen();

    fireEvent.changeText(screen.getByLabelText("Medication"), "Metformin");
    fireEvent.changeText(screen.getByLabelText("Instruction"), "500 mg twice daily with food.");
    fireEvent.press(screen.getByRole("button", { name: /Create plan/i }));

    expect(mockCreateState.mutate).toHaveBeenCalledTimes(1);
    const payload = mockCreateState.mutate.mock.calls[0][0] as Record<string, unknown>;
    expect(payload).toEqual({
      patient_id: PATIENT.patient_id,
      medication: "Metformin",
      instruction: "500 mg twice daily with food.",
    });
    expect(payload.prescriber).toBeUndefined();
    expect(payload.actor_id).toBeUndefined();
    expect(payload.tenant_id).toBeUndefined();
    expect(payload.facility_id).toBeUndefined();
  });

  // Scenario 4: Backend confirmation triggers onCreated (never a local fake)
  it("calls onCreated only after backend confirmation", () => {
    const onCreated = jest.fn();
    renderScreen({ onCreated });

    expect(onCreated).not.toHaveBeenCalled();

    act(() => {
      mockCreateCallbacks.onSuccess?.({
        medication_plan_id: "plan-new",
        patient_id: PATIENT.patient_id,
      });
    });

    expect(onCreated).toHaveBeenCalledTimes(1);
    expect(onCreated).toHaveBeenCalledWith({
      medication_plan_id: "plan-new",
      patient_id: PATIENT.patient_id,
    });
  });

  // Scenario 5: 422 field errors render inline on the form
  it("renders backend field errors inline on a 422", () => {
    renderScreen();

    act(() => {
      mockCreateCallbacks.onError?.({
        kind: "VALIDATION_ERROR",
        httpStatus: 422,
        message: "Invalid medication.",
        fieldErrors: { medication: ["Not a known medication."] },
      } as ApiErrorDetails);
    });

    expect(screen.getByText("Plan Creation Failed")).toBeTruthy();
    expect(screen.getByText("Not a known medication.")).toBeTruthy();
  });

  // Scenario 6: Network failure never implies success
  it("shows a non-confirmation banner on network failure", () => {
    const onCreated = jest.fn();
    renderScreen({ onCreated });

    act(() => {
      mockCreateCallbacks.onError?.({
        kind: "NETWORK_ERROR",
        httpStatus: 0,
        message: "Network unreachable",
      } as ApiErrorDetails);
    });

    expect(screen.getByText("Unable to connect. The plan has not been submitted.")).toBeTruthy();
    expect(onCreated).not.toHaveBeenCalled();
  });

  // Scenario 7: 403 during create → revoked safe state (never logout)
  it("shows revoked state when creation is denied with 403", () => {
    mockCreateState.isError = true;
    mockCreateState.error = {
      kind: "FORBIDDEN",
      httpStatus: 403,
      code: "MEDICATION_PLAN_UNAUTHORIZED",
      message: "capability removed",
    } as ApiErrorDetails;
    renderScreen();

    expect(screen.getByText("Access Revoked")).toBeTruthy();
    expect(
      screen.getByText("Your ability to create plans for this patient was removed or expired. Returning to the patient record.")
    ).toBeTruthy();
  });
});