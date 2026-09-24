import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CaregiverPatientsScreen } from "../../src/features/caregiver/CaregiverPatientsScreen";
import type { CaregiverPatientListItem } from "../../src/services/schemas/caregiver";

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

let mockListState: {
  patients: CaregiverPatientListItem[];
  patientCount: number;
  isLoading: boolean;
  isError: boolean;
  refetch: jest.Mock;
} = {
  patients: [],
  patientCount: 0,
  isLoading: false,
  isError: false,
  refetch: jest.fn(),
};

jest.mock("../../src/features/caregiver/useCaregiverPatients", () => ({
  useCaregiverPatients: () => mockListState,
  caregiverKeys: {
    all: ["caregivers"],
    me: () => ["caregivers", "me"],
    patients: () => ["caregivers", "me", "patients"],
  },
}));

const PATIENT: CaregiverPatientListItem = {
  relationship_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  relationship_label: "Son",
  status: "verified",
  capabilities: ["read_glucose", "read_meal"],
  expires_at: null,
  name: "Aarav Sharma",
};

function renderScreen(props?: { onSelect?: (p: CaregiverPatientListItem) => void; onBack?: () => void }) {
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
        <CaregiverPatientsScreen {...props} />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("CaregiverPatientsScreen Component Tests (Gate 10E-M)", () => {
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
    mockListState = {
      patients: [],
      patientCount: 0,
      isLoading: false,
      isError: false,
      refetch: jest.fn(),
    };
  });

  // Scenario 1: Renders the discovery screen for an authenticated caregiver
  it("renders the patient discovery screen for caregiver role", () => {
    mockListState.patients = [PATIENT];
    renderScreen();
    expect(screen.getByText("My Patients")).toBeTruthy();
    expect(screen.getByText("Aarav Sharma")).toBeTruthy();
    expect(screen.getByText("Son")).toBeTruthy();
    expect(screen.getByText("Glucose view")).toBeTruthy();
  });

  // Scenario 2: Loading state while the patient list query is pending
  it("renders loading state while the patient list is pending", () => {
    mockListState.isLoading = true;
    renderScreen();
    expect(screen.getByText("Loading your patients…")).toBeTruthy();
  });

  // Scenario 3: Empty state when the caregiver has no authorized patients
  it("renders empty state when no patients are authorized", () => {
    renderScreen();
    expect(screen.getByText("No authorized patients")).toBeTruthy();
  });

  // Scenario 4: Error state with retry that refetches
  it("renders error state and refetches on retry", () => {
    mockListState.isError = true;
    renderScreen();
    expect(screen.getByText("Could not load patients")).toBeTruthy();
    const retryBtn = screen.getByRole("button", { name: /Try again/i });
    fireEvent.press(retryBtn);
    expect(mockListState.refetch).toHaveBeenCalledTimes(1);
  });

  // Scenario 5: Selecting a patient card calls onSelect with that patient
  it("selects a patient card and returns the full DTO", () => {
    mockListState.patients = [PATIENT];
    const onSelect = jest.fn();
    renderScreen({ onSelect });

    fireEvent.press(screen.getByLabelText("View glucose for Aarav Sharma"));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(PATIENT);
  });

  // Scenario 6: Non-caregiver roles are blocked at the screen boundary
  it("renders access restricted notice when actor is not a Caregiver", () => {
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
    renderScreen();
    expect(screen.getByText("Access Restricted")).toBeTruthy();
    expect(
      screen.getByText("The patient discovery screen is only available in Caregiver mode.")
    ).toBeTruthy();
  });
});