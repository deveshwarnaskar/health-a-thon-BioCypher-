import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CaregiverPatientGlucoseScreen } from "../../src/features/caregiver/CaregiverPatientGlucoseScreen";
import type { CaregiverPatientListItem } from "../../src/services/schemas/caregiver";
import type { PatientGlucoseObservation } from "../../src/features/glucose/types";

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
    role: "Caregiver",
    actor_id: "cg-1",
    tenant_id: "tenant-1",
    capabilities: ["READ_GLUCOSE", "READ_MEAL", "CREATE_GLUCOSE", "CREATE_MEAL"],
    patient_id: null,
  },
};

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signOut: jest.fn(),
  }),
}));

let mockFeedState: {
  readings: PatientGlucoseObservation[];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: jest.Mock;
} = {
  readings: [],
  isLoading: false,
  isError: false,
  error: undefined,
  refetch: jest.fn(),
};

let mockIngestState: {
  mutate: jest.Mock;
  isPending: boolean;
  isSuccess: boolean;
  isError: boolean;
  idempotencyKey: string;
} = {
  mutate: jest.fn(),
  isPending: false,
  isSuccess: false,
  isError: false,
  idempotencyKey: "mock-idempotency-key",
};

const mockIngestCallbacks: {
  onSuccess?: (data: unknown) => void;
  onError?: (error: unknown) => void;
} = {};

jest.mock("../../src/features/glucose/useGlucoseFeed", () => ({
  useGlucoseFeed: () => mockFeedState,
}));

jest.mock("../../src/features/glucose/useIngestGlucose", () => ({
  useIngestGlucose: (options?: {
    onSuccess?: (data: unknown) => void;
    onError?: (error: unknown) => void;
  }) => {
    mockIngestCallbacks.onSuccess = options?.onSuccess;
    mockIngestCallbacks.onError = options?.onError;
    return mockIngestState;
  },
}));

const PATIENT_FULL: CaregiverPatientListItem = {
  relationship_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  relationship_label: "Son",
  status: "verified",
  capabilities: ["read_glucose", "read_meal", "create_glucose"],
  expires_at: null,
  name: "Aarav Sharma",
};

function renderScreen(props?: {
  patient?: CaregiverPatientListItem;
  onBack?: () => void;
  onAccessLost?: () => void;
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
        <CaregiverPatientGlucoseScreen patient={PATIENT_FULL} {...props} />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("CaregiverPatientGlucoseScreen Component Tests (Gate 10E-M)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuthState = {
      name: "authenticated",
      user: {
        role: "Caregiver",
        actor_id: "cg-1",
        tenant_id: "tenant-1",
        capabilities: ["READ_GLUCOSE", "READ_MEAL", "CREATE_GLUCOSE", "CREATE_MEAL"],
        patient_id: null,
      },
    };
    mockFeedState = {
      readings: [],
      isLoading: false,
      isError: false,
      error: undefined,
      refetch: jest.fn(),
    };
    mockIngestState = {
      mutate: jest.fn(),
      isPending: false,
      isSuccess: false,
      isError: false,
      idempotencyKey: "mock-idempotency-key",
    };
  });

  // Scenario 1: Full-capability caregiver sees entry form + feed
  it("renders entry form and observation feed when relationship grants read + write", () => {
    mockFeedState.readings = [
      {
        kind: "glucose",
        value_mg_dl: 108,
        tag: "fasting",
        taken_at: "2026-09-17T07:30:00Z",
        confirmed: true,
      },
    ];
    renderScreen();

    expect(screen.getByText("Patient Glucose")).toBeTruthy();
    expect(screen.getByText("Aarav Sharma")).toBeTruthy();
    expect(screen.getByText("Record Blood Glucose")).toBeTruthy();
    expect(screen.getByText("108")).toBeTruthy();
    expect(screen.getByText("Confirmed")).toBeTruthy();
  });

  // Scenario 2: Read-only relationship hides the entry form
  it("shows view-only access when the relationship lacks create_glucose", () => {
    renderScreen({
      patient: { ...PATIENT_FULL, capabilities: ["read_glucose", "read_meal"] },
    });

    expect(screen.getByText("View-only access")).toBeTruthy();
    expect(screen.queryByText("Record Blood Glucose")).toBeNull();
    expect(screen.getByText("Observation Feed")).toBeTruthy();
  });

  // Scenario 3: Write-only relationship renders form but no feed
  it("renders the entry form without the feed when read capability pair is absent", () => {
    renderScreen({
      patient: { ...PATIENT_FULL, capabilities: ["create_glucose"] },
    });

    expect(screen.getByText("Record Blood Glucose")).toBeTruthy();
    expect(screen.queryByText("Observation Feed")).toBeNull();
  });

  // Scenario 4: No glucose capabilities → no clinical surface at all
  it("renders no clinical surface when relationship has no glucose capabilities", () => {
    renderScreen({ patient: { ...PATIENT_FULL, capabilities: ["read_care_tasks"] } });

    expect(screen.queryByText("Record Blood Glucose")).toBeNull();
    expect(screen.queryByText("Observation Feed")).toBeNull();
  });

  // Scenario 5: 403 on the feed is per-patient revocation, not a logout
  it("shows access-revoked state and returns to patient list on 403 feed error", () => {
    mockFeedState.isError = true;
    mockFeedState.error = {
      kind: "FORBIDDEN",
      httpStatus: 403,
      code: "AUTHORIZATION_DENIED",
      message: "Patient inactive",
    };
    const onAccessLost = jest.fn();
    renderScreen({ onAccessLost });

    expect(screen.getByText("Access Revoked")).toBeTruthy();
    const backBtn = screen.getByRole("button", { name: /Back to Patient List/i });
    fireEvent.press(backBtn);
    expect(onAccessLost).toHaveBeenCalledTimes(1);
  });

  // Scenario 6: Non-403 feed errors surface the retryable error state
  it("renders retryable error state for transient feed failures", () => {
    mockFeedState.isError = true;
    mockFeedState.error = { kind: "NETWORK_ERROR", httpStatus: 0, message: "Network unreachable" };
    renderScreen();

    expect(screen.getByText("Could not load readings")).toBeTruthy();
    const retryBtn = screen.getByRole("button", { name: /Try again/i });
    fireEvent.press(retryBtn);
    expect(mockFeedState.refetch).toHaveBeenCalledTimes(1);
  });

  // Scenario 7: Valid submission is forwarded to the ingest mutation without
  // a client-computed taken_at (capture session owns the timestamp).
  it("submits a valid reading scoped to the selected patient", () => {
    renderScreen();

    const input = screen.getByLabelText("Blood Glucose (mg/dL)");
    fireEvent.changeText(input, "115");
    const submitBtn = screen.getByRole("button", { name: /Record Reading/i });
    fireEvent.press(submitBtn);

    expect(mockIngestState.mutate).toHaveBeenCalledTimes(1);
    const payload = mockIngestState.mutate.mock.calls[0][0];
    expect(payload.value_mg_dl).toBe(115);
    expect(payload.taken_at).toBeUndefined();
  });

  // Scenario 8: Success callback renders a confirmation banner
  it("renders a success banner when the reading is recorded", () => {
    renderScreen();
    act(() => {
      mockIngestCallbacks.onSuccess?.({
        observation_id: "obs-1",
        patient_id: PATIENT_FULL.patient_id,
        value_mg_dl: 115,
        taken_at: "2026-09-17T08:00:00Z",
      });
    });

    expect(screen.getByText(/recorded successfully/i)).toBeTruthy();
  });

  // Scenario 9: Non-caregiver roles are blocked at the screen boundary
  it("renders access restricted notice when actor is not a Caregiver", () => {
    mockAuthState = {
      name: "authenticated",
      user: {
        role: "Nurse",
        actor_id: "nurse-1",
        tenant_id: "tenant-1",
        capabilities: ["READ_OBSERVATIONS"],
        patient_id: null,
      },
    };
    renderScreen();
    expect(screen.getByText("Access Restricted")).toBeTruthy();
    expect(
      screen.getByText("Patient glucose is only available in Caregiver mode.")
    ).toBeTruthy();
  });
});