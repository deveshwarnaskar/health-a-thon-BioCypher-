import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  DietitianWorkflow,
  DietitianPatientMealDetailScreen,
} from "../../src/features/meals/DietitianWorkflow";
import type { PatientSummaryResponse } from "../../src/services/schemas/patients";
import type { ClinicianMealObservation } from "../../src/features/meals/types";

let mockAuthState: {
  name: string;
  user: {
    role: string;
    actor_id: string;
    tenant_id: string;
    capabilities: string[];
  } | null;
} = {
  name: "authenticated",
  user: {
    role: "Dietitian",
    actor_id: "user-dietitian-01",
    tenant_id: "tenant-01",
    capabilities: [
      "READ_OBSERVATIONS",
      "WRITE_OBSERVATIONS",
      "READ_PATIENT",
      "READ_AI_ARTIFACT",
      "REVIEW_AI_ARTIFACT",
    ],
  },
};

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signOut: jest.fn(),
  }),
}));

const mockPatient: PatientSummaryResponse = {
  patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  uh_id: "UH-998877",
  name: "Pooja Patel",
  facility_id: "fac-01",
  active: true,
  created_at: "2026-09-17T00:00:00Z",
};

let mockPatientsState: {
  patients: PatientSummaryResponse[];
  patientCount: number;
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  refetch: jest.Mock;
} = {
  patients: [mockPatient],
  patientCount: 1,
  isLoading: false,
  isError: false,
  refetch: jest.fn(),
};

jest.mock("../../src/features/doctor/usePatients", () => ({
  usePatients: () => mockPatientsState,
}));

let mockClinicianMealState: {
  meals: ClinicianMealObservation[];
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  refetch: jest.Mock;
} = {
  meals: [],
  isLoading: false,
  isError: false,
  refetch: jest.fn(),
};

jest.mock("../../src/features/meals/useClinicianMeals", () => ({
  useClinicianMeals: () => mockClinicianMealState,
}));

function renderWorkflow(props?: { onHome?: () => void }) {
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
        <DietitianWorkflow {...props} />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

function renderDetail(props: { patient: PatientSummaryResponse; onBack: () => void }) {
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
        <DietitianPatientMealDetailScreen {...props} />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("DietitianWorkflow Component Tests (Gate 10H-M)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuthState = {
      name: "authenticated",
      user: {
        role: "Dietitian",
        actor_id: "user-dietitian-01",
        tenant_id: "tenant-01",
        capabilities: [
          "READ_OBSERVATIONS",
          "WRITE_OBSERVATIONS",
          "READ_PATIENT",
          "READ_AI_ARTIFACT",
          "REVIEW_AI_ARTIFACT",
        ],
      },
    };
    mockPatientsState = {
      patients: [mockPatient],
      patientCount: 1,
      isLoading: false,
      isError: false,
      refetch: jest.fn(),
    };
    mockClinicianMealState = {
      meals: [],
      isLoading: false,
      isError: false,
      refetch: jest.fn(),
    };
  });

  it("10H-M-20: Dietitian can view patient cohort and navigate to patient detail", () => {
    renderWorkflow();
    expect(screen.getByText("Nutrition & Meals")).toBeTruthy();
    expect(screen.getByText("Pooja Patel")).toBeTruthy();
    expect(screen.getByText("UH ID UH-998877")).toBeTruthy();

    // Select patient
    fireEvent.press(screen.getByText("Pooja Patel"));
    expect(screen.getByText("Nutrition Detail")).toBeTruthy();
    expect(screen.getByText("Clinical Nutrition & Meal Observations")).toBeTruthy();
  });

  it("10H-M-19: Clinician detail screen renders permitted nutrition analytics", () => {
    mockClinicianMealState = {
      meals: [
        {
          kind: "meal",
          observation_id: "obs-meal-101",
          description: "Paneer Bhurji with Paratha",
          portion_label: "large",
          quantity: 1.0,
          carbs_grams: 42.5,
          glycemic_index: "medium",
          recorded_at: "2026-09-17T14:30:00Z",
          confirmation: "confirmed",
        },
      ],
      isLoading: false,
      isError: false,
      refetch: jest.fn(),
    };

    renderDetail({ patient: mockPatient, onBack: jest.fn() });

    expect(screen.getByText("Paneer Bhurji with Paratha")).toBeTruthy();
    expect(screen.getByText("Carbohydrates: 42.5 g")).toBeTruthy();
    expect(screen.getByText("Glycemic Index: medium")).toBeTruthy();
    expect(screen.getByText("Confirmed")).toBeTruthy();
  });

  it("10H-M-21: Unauthorized non-clinician role receives Access Restricted banner", () => {
    mockAuthState.user!.role = "Patient";
    renderWorkflow();
    expect(screen.getByText("Access Restricted")).toBeTruthy();
    expect(
      screen.getByText(
        "Nutrition review workflows are only accessible to Dietitians and authorized clinicians."
      )
    ).toBeTruthy();
  });

  it("Access revoked (403) shows Access Revoked empty state without global logout", () => {
    mockClinicianMealState = {
      meals: [],
      isLoading: false,
      isError: true,
      error: { httpStatus: 403, kind: "FORBIDDEN", message: "Access denied" },
      refetch: jest.fn(),
    };

    renderDetail({ patient: mockPatient, onBack: jest.fn() });

    expect(screen.getByText("Access Revoked")).toBeTruthy();
    expect(
      screen.getByText(
        "Your access to this patient's clinical nutrition record was removed or expired."
      )
    ).toBeTruthy();
  });

  it("Patient unavailable (404) shows Patient unavailable without leaking existence", () => {
    mockClinicianMealState = {
      meals: [],
      isLoading: false,
      isError: true,
      error: { httpStatus: 404, kind: "NOT_FOUND", message: "Not found" },
      refetch: jest.fn(),
    };

    renderDetail({ patient: mockPatient, onBack: jest.fn() });

    expect(screen.getByText("Patient unavailable")).toBeTruthy();
    expect(
      screen.getByText("This patient record is no longer available.")
    ).toBeTruthy();
  });
});
