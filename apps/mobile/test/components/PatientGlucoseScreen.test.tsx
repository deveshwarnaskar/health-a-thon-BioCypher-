import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PatientGlucoseScreen } from "../../src/features/glucose/PatientGlucoseScreen";
import { GlucoseEntryForm } from "../../src/features/glucose/GlucoseEntryForm";
import type { PatientGlucoseObservation } from "../../src/features/glucose/types";

// Mock Auth Provider
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
    role: "Patient",
    actor_id: "user-1",
    tenant_id: "tenant-1",
    capabilities: ["view_own_records", "record_observations"],
    patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  },
};

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signOut: jest.fn(),
  }),
}));

// Mock glucose hooks for deterministic component testing
let mockFeedState: {
  readings: PatientGlucoseObservation[];
  isLoading: boolean;
  isError: boolean;
  refetch: jest.Mock;
} = {
  readings: [],
  isLoading: false,
  isError: false,
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

jest.mock("../../src/features/glucose/useGlucoseFeed", () => ({
  useGlucoseFeed: () => mockFeedState,
}));

jest.mock("../../src/features/glucose/useIngestGlucose", () => ({
  useIngestGlucose: (options?: { onSuccess?: (data: unknown) => void }) => ({
    ...mockIngestState,
    _triggerSuccess: (data: unknown) => options?.onSuccess?.(data),
  }),
}));

function renderScreen(props?: { patientId?: string; onBack?: () => void }) {
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
        <PatientGlucoseScreen {...props} />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("PatientGlucoseScreen & GlucoseEntryForm Component Tests (Gate 10D)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuthState = {
      name: "authenticated",
      user: {
        role: "Patient",
        actor_id: "user-1",
        tenant_id: "tenant-1",
        capabilities: ["view_own_records", "record_observations"],
        patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      },
    };
    mockFeedState = {
      readings: [],
      isLoading: false,
      isError: false,
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

  // Scenario 1: PatientGlucoseScreen renders when role === 'Patient' and patient_id is present
  it("renders the glucose logbook screen for authenticated patient with linked profile", () => {
    renderScreen();
    expect(screen.getByText("Glucose Logbook")).toBeTruthy();
    expect(screen.getByText("Record Blood Glucose")).toBeTruthy();
    expect(screen.getByText("Observation Feed")).toBeTruthy();
    expect(screen.getByText("No glucose readings")).toBeTruthy();
  });

  // Scenario 2: GlucoseEntryForm renders input with correct accessibility attributes
  it("renders glucose entry form with proper accessibility attributes and touch targets", () => {
    const handleSubmit = jest.fn();
    render(
      <SafeAreaProvider
        initialMetrics={{
          frame: { x: 0, y: 0, width: 390, height: 844 },
          insets: { top: 0, left: 0, right: 0, bottom: 0 },
        }}
      >
        <GlucoseEntryForm onSubmit={handleSubmit} />
      </SafeAreaProvider>
    );

    const input = screen.getByLabelText("Blood Glucose (mg/dL)");
    expect(input).toBeTruthy();
    expect(screen.getByText("Valid range: 20 – 600 mg/dL")).toBeTruthy();
    expect(screen.getByText("Measurement Context (Optional)")).toBeTruthy();

    // Context chips rendered
    expect(screen.getByText("Fasting")).toBeTruthy();
    expect(screen.getByText("Pre-meal")).toBeTruthy();
    expect(screen.getByText("Post-breakfast")).toBeTruthy();
    expect(screen.getByText("Post-lunch")).toBeTruthy();
    expect(screen.getByText("Post-dinner")).toBeTruthy();
  });

  // Scenario 3: Form input rejects non-numeric input and out-of-range values with validation message
  it("rejects out-of-range values with validation error", () => {
    const handleSubmit = jest.fn();
    render(
      <SafeAreaProvider
        initialMetrics={{
          frame: { x: 0, y: 0, width: 390, height: 844 },
          insets: { top: 0, left: 0, right: 0, bottom: 0 },
        }}
      >
        <GlucoseEntryForm onSubmit={handleSubmit} />
      </SafeAreaProvider>
    );

    const input = screen.getByLabelText("Blood Glucose (mg/dL)");

    // Enter out-of-range value (below 20)
    fireEvent.changeText(input, "15");
    const submitBtn = screen.getByRole("button", { name: /Record Reading/i });
    fireEvent.press(submitBtn);

    expect(screen.getByText("Reading must be a whole number between 20 and 600 mg/dL.")).toBeTruthy();
    expect(handleSubmit).not.toHaveBeenCalled();

    // Enter out-of-range value (above 600)
    fireEvent.changeText(input, "650");
    fireEvent.press(submitBtn);

    expect(screen.getByText("Reading must be a whole number between 20 and 600 mg/dL.")).toBeTruthy();
    expect(handleSubmit).not.toHaveBeenCalled();
  });

  // Scenario 4: Submitting valid reading triggers mutation with correct payload
  it("submits valid glucose reading with selected context tag", () => {
    renderScreen();

    const input = screen.getByLabelText("Blood Glucose (mg/dL)");
    fireEvent.changeText(input, "115");

    // Select Fasting tag chip
    const fastingChip = screen.getByText("Fasting");
    fireEvent.press(fastingChip);

    const submitBtn = screen.getByRole("button", { name: /Record Reading/i });
    fireEvent.press(submitBtn);

    expect(mockIngestState.mutate).toHaveBeenCalledTimes(1);
    const submittedPayload = mockIngestState.mutate.mock.calls[0][0];
    expect(submittedPayload.value_mg_dl).toBe(115);
    expect(submittedPayload.tag).toBe("fasting");
    // taken_at is owned by the capture session (useIngestGlucose), not the form,
    // so a retry of the same submission stays byte-identical (Gate 09).
    expect(submittedPayload.taken_at).toBeUndefined();
  });

  // Scenario 5: Submit button is disabled during submission (isSubmitting = true)
  it("disables the submit button while submission is pending", () => {
    mockIngestState.isPending = true;
    renderScreen();

    expect(screen.getByRole("button", { name: /Recording…/i })).toBeTruthy();
    const button = screen.getByRole("button", { name: /Recording…/i });
    expect(button.props.accessibilityState?.disabled).toBe(true);
  });

  // Scenario 6: Feed renders loading state while query is pending
  it("renders loading state when observations query is pending", () => {
    mockFeedState.isLoading = true;
    renderScreen();

    expect(screen.getByText("Loading glucose history…")).toBeTruthy();
  });

  // Scenario 7: Feed renders empty state when query returns empty array
  it("renders empty state when patient has no recorded readings", () => {
    mockFeedState.readings = [];
    mockFeedState.isLoading = false;
    renderScreen();

    expect(screen.getByText("No glucose readings")).toBeTruthy();
    expect(
      screen.getByText("Your recorded blood glucose observations will appear here in chronological order.")
    ).toBeTruthy();
  });

  // Scenario 8: Feed renders error state with retry button on query failure
  it("renders error state with retry button on query failure and calls refetch on press", () => {
    mockFeedState.isError = true;
    renderScreen();

    expect(screen.getByText("Could not load readings")).toBeTruthy();
    const retryBtn = screen.getByRole("button", { name: /Try again/i });
    expect(retryBtn).toBeTruthy();

    fireEvent.press(retryBtn);
    expect(mockFeedState.refetch).toHaveBeenCalledTimes(1);
  });

  // Scenario 9: Feed renders observation items with value, tag label, and confirmed badge
  it("renders observation cards with value, tag label, and confirmation status", () => {
    mockFeedState.readings = [
      {
        kind: "glucose",
        value_mg_dl: 108,
        tag: "fasting",
        taken_at: "2026-09-17T07:30:00Z",
        confirmed: true,
      },
      {
        kind: "glucose",
        value_mg_dl: 142,
        tag: "postlunch",
        taken_at: "2026-09-16T13:45:00Z",
        confirmed: false,
      },
    ];

    renderScreen();

    expect(screen.getByText("Recent Readings")).toBeTruthy();
    expect(screen.getByText("108")).toBeTruthy();
    expect(screen.getAllByText("Fasting").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Confirmed")).toBeTruthy();

    expect(screen.getByText("142")).toBeTruthy();
    expect(screen.getAllByText("Post-lunch").length).toBeGreaterThanOrEqual(2);
  });

  // Scenario 10: Patient-only route enforcement
  it("renders account linking notice when patient_id is missing", () => {
    mockAuthState = {
      name: "authenticated",
      user: {
        role: "Patient",
        actor_id: "user-1",
        tenant_id: "tenant-1",
        capabilities: ["view_own_records"],
        patient_id: null,
      },
    };

    renderScreen();

    expect(screen.getByText("Account Linking Required")).toBeTruthy();
    expect(
      screen.getByText(/Your account is not yet linked to a patient profile/i)
    ).toBeTruthy();
  });

  it("renders access restricted notice when actor is not a Patient", () => {
    mockAuthState = {
      name: "authenticated",
      user: {
        role: "Doctor",
        actor_id: "doc-1",
        tenant_id: "tenant-1",
        capabilities: ["view_assigned_records"],
        patient_id: null,
      },
    };

    renderScreen();

    expect(screen.getByText("Access Restricted")).toBeTruthy();
    expect(
      screen.getByText("The glucose logging screen is only available in Patient mode.")
    ).toBeTruthy();
  });
});
