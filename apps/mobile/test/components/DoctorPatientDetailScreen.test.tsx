import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PatientDetailScreen } from "../../src/features/doctor/PatientDetailScreen";
import type { PatientSummaryResponse } from "../../src/services/schemas/patients";
import type { ClinicianObservationFeedResponse } from "../../src/services/schemas/clinical";
import type { MedicationPlanResponse } from "../../src/services/schemas/medication";

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
    capabilities: ["READ_OBSERVATIONS"],
    patient_id: null,
  },
};

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signOut: jest.fn(),
  }),
}));

let mockDetailState: {
  patient: PatientSummaryResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: jest.Mock;
} = {
  patient: null,
  isLoading: false,
  isError: false,
  error: undefined,
  refetch: jest.fn(),
};

jest.mock("../../src/features/doctor/usePatientDetail", () => ({
  usePatientDetail: () => mockDetailState,
}));

let mockFeedState: {
  feed: ClinicianObservationFeedResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: jest.Mock;
} = {
  feed: null,
  isLoading: false,
  isError: false,
  error: undefined,
  refetch: jest.fn(),
};

jest.mock("../../src/features/doctor/useClinicianFeed", () => ({
  useClinicianFeed: () => mockFeedState,
}));

let mockPlansState: {
  plans: MedicationPlanResponse[];
  planCount: number;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: jest.Mock;
} = {
  plans: [],
  planCount: 0,
  isLoading: false,
  isError: false,
  error: undefined,
  refetch: jest.fn(),
};

jest.mock("../../src/features/doctor/useMedicationPlans", () => ({
  useMedicationPlans: () => mockPlansState,
}));

const PATIENT: PatientSummaryResponse = {
  patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  uh_id: "UH-001",
  name: "Aarav Sharma",
  facility_id: "facility-1",
  active: true,
  created_at: "2026-01-02T00:00:00Z",
};

const PLATINUM_FEED: ClinicianObservationFeedResponse = {
  patient_id: PATIENT.patient_id,
  items: [
    {
      kind: "glucose",
      observation_id: "obs-1",
      value_mg_dl: 118,
      tag: "fasting",
      taken_at: "2026-09-17T08:00:00Z",
      confirmation: "confirmed",
    },
    {
      kind: "meal",
      observation_id: "obs-2",
      description: "Rice and dal",
      portion_label: "plate",
      quantity: 1,
      carbs_grams: 55,
      glycemic_index: "medium",
      recorded_at: "2026-09-17T09:00:00Z",
      confirmation: "confirmed",
    },
  ],
};

const PLAN: MedicationPlanResponse = {
  medication_plan_id: "plan-1",
  patient_id: PATIENT.patient_id,
  medication: "Metformin",
  instruction: "500 mg twice daily with food.",
  active: true,
  prescribed_by_role: "doctor",
  created_at: "2026-09-17T09:30:00Z",
};

function renderScreen(props?: {
  onBack?: () => void;
  onCreatePlan?: (patient: PatientSummaryResponse) => void;
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
        <PatientDetailScreen patient={PATIENT} onCreatePlan={props?.onCreatePlan ?? jest.fn()} onBack={props?.onBack} />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("Doctor PatientDetailScreen Component Tests (Gate 10F-M)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuthState = {
      name: "authenticated",
      user: {
        role: "Doctor",
        actor_id: "doc-1",
        tenant_id: "tenant-1",
        capabilities: ["READ_OBSERVATIONS"],
        patient_id: null,
      },
    };
    mockDetailState = {
      patient: null,
      isLoading: false,
      isError: false,
      error: undefined,
      refetch: jest.fn(),
    };
    mockFeedState = {
      feed: null,
      isLoading: false,
      isError: false,
      error: undefined,
      refetch: jest.fn(),
    };
    mockPlansState = {
      plans: [],
      planCount: 0,
      isLoading: false,
      isError: false,
      error: undefined,
      refetch: jest.fn(),
    };
  });

  // Scenario 1: Doctor sees identity facts + clinician feed (carbs/GI) + plans
  it("renders the clinician view with carbs and glycemic index", () => {
    mockFeedState.feed = PLATINUM_FEED;
    mockPlansState.plans = [PLAN];
    renderScreen();

    expect(screen.getByText("Aarav Sharma")).toBeTruthy();
    expect(screen.getByText("UH ID UH-001")).toBeTruthy();
    expect(screen.getByLabelText("Glucose reading 118 mg/dL")).toBeTruthy();
    expect(screen.getByText("Carbs 55 g · Glycemic index medium")).toBeTruthy();
    expect(screen.getByText("Metformin")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Create Medication Plan/i })).toBeTruthy();
  });

  // Scenario 2: Empty feed renders the empty observation state
  it("renders the empty observation state when the clinician feed is empty", () => {
    mockFeedState.feed = { patient_id: PATIENT.patient_id, items: [] };
    renderScreen();
    expect(screen.getByText("No observations yet")).toBeTruthy();
  });

  // Scenario 3: Empty plans render the empty plan state
  it("renders the empty medication-plan state when there are no plans", () => {
    mockFeedState.feed = PLATINUM_FEED;
    renderScreen();
    expect(screen.getByText("No medication plans")).toBeTruthy();
  });

  // Scenario 4: 403 on the clinician feed → access revoked (never logout)
  it("shows access-revoked state on a 403 feed error and returns to the list", () => {
    mockFeedState.isError = true;
    mockFeedState.error = { kind: "FORBIDDEN", httpStatus: 403, code: "AUTHORIZATION_DENIED" };
    const onBack = jest.fn();
    renderScreen({ onBack });

    expect(screen.getByText("Access Revoked")).toBeTruthy();
    const backBtn = screen.getByRole("button", { name: /Return to Patient List/i });
    fireEvent.press(backBtn);
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  // Scenario 5: 404 patient detail → unavailable (never reveals existence)
  it("shows unavailable state on a 404 patient detail", () => {
    mockDetailState.isError = true;
    mockDetailState.error = { kind: "NOT_FOUND", httpStatus: 404, message: "missing" };
    renderScreen();
    expect(screen.getByText("Patient unavailable")).toBeTruthy();
  });

  // Scenario 6: Create Plan forwards the selected patient DTO
  it("opens the plan form with the selected patient", () => {
    mockFeedState.feed = PLATINUM_FEED;
    const onCreatePlan = jest.fn();
    renderScreen({ onCreatePlan });

    fireEvent.press(screen.getByRole("button", { name: /Create Medication Plan/i }));
    expect(onCreatePlan).toHaveBeenCalledTimes(1);
    expect(onCreatePlan).toHaveBeenCalledWith(PATIENT);
  });

  // Scenario 7: Non-Doctor principals are blocked at the screen boundary
  it("renders access restricted notice when the actor is not a Doctor", () => {
    mockAuthState = {
      name: "authenticated",
      user: {
        role: "Patient",
        actor_id: "p-1",
        tenant_id: "tenant-1",
        capabilities: [],
        patient_id: PATIENT.patient_id,
      },
    };
    renderScreen();
    expect(screen.getByText("Access Restricted")).toBeTruthy();
    expect(
      screen.getByText("Patient clinical detail is only available in Doctor mode.")
    ).toBeTruthy();
  });
});