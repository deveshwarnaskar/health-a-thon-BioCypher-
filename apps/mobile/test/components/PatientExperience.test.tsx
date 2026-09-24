import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PatientExperience } from "../../src/features/patient/PatientExperience";

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
    actor_id: "patient-user-1",
    tenant_id: "tenant-1",
    capabilities: ["view_own_records", "record_observations"],
    patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  },
};

const mockSignOut = jest.fn().mockResolvedValue(undefined);

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signOut: mockSignOut,
  }),
}));

jest.mock("../../src/features/glucose", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Text } = require("react-native");
  return {
    PatientGlucoseScreen: () => <Text>Mocked PatientGlucoseScreen</Text>,
    useGlucoseFeed: () => ({
      readings: [
        {
          kind: "glucose",
          value_mg_dl: 112,
          tag: "fasting",
          taken_at: "2026-09-20T08:00:00Z",
          confirmed: true,
        },
      ],
      isLoading: false,
      isError: false,
      error: null,
      refetch: jest.fn().mockResolvedValue({}),
    }),
  };
});

jest.mock("../../src/features/meals", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Text } = require("react-native");
  return {
    PatientMealScreen: () => <Text>Mocked PatientMealScreen</Text>,
    usePatientMeals: () => ({
      meals: [
        {
          kind: "meal",
          description: "Oats with almonds",
          portion_label: "1 bowl",
          recorded_at: "2026-09-20T08:30:00Z",
          confirmed: true,
        },
      ],
      isLoading: false,
      isError: false,
      error: null,
      refetch: jest.fn().mockResolvedValue({}),
    }),
  };
});

jest.mock("../../src/features/tasks/useCareTasks", () => ({
  useCareTasks: () => ({
    data: {
      total: 2,
      items: [
        {
          care_task_id: "task-1",
          patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
          description: "Log post-dinner glucose",
          status: "open",
          due_at: "2026-09-20T21:00:00Z",
          created_at: "2026-09-20T07:00:00Z",
        },
      ],
    },
    isLoading: false,
    isError: false,
    refetch: jest.fn().mockResolvedValue({}),
  }),
  useUpdateCareTaskStatus: () => ({
    mutateAsync: jest.fn().mockResolvedValue({}),
    isPending: false,
  }),
  useCompleteCareTask: () => ({
    mutateAsync: jest.fn().mockResolvedValue({}),
    isPending: false,
  }),
}));

jest.mock("../../src/features/patient/api", () => {
  const actual = jest.requireActual("../../src/features/patient/api");
  return {
    ...actual,
    usePatientMedications: () => ({
      data: [
        {
          medication_plan_id: "plan-1",
          patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
          medication: "Metformin 500mg",
          dosage: "1 tablet",
          frequency: "Twice daily",
          instruction: "Take with food",
          prescribed_at: "2026-09-01T10:00:00Z",
        },
      ],
      isLoading: false,
      isError: false,
      refetch: jest.fn().mockResolvedValue({}),
    }),
    usePatientNotifications: () => ({
      data: [
        {
          notification_id: "notif-1",
          patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
          notification_type: "reminder",
          template_name: "medication_reminder",
          status: "sent",
          content: "Time to take Metformin",
          created_at: "2026-09-20T08:00:00Z",
        },
      ],
      isLoading: false,
      isError: false,
      refetch: jest.fn().mockResolvedValue({}),
    }),
    useUnifiedTimeline: () => ({
      data: [
        {
          id: "glucose-1",
          type: "glucose",
          title: "112 mg/dL",
          subtitle: "Blood Glucose · Fasting",
          timestamp: "2026-09-20T08:00:00Z",
          status: "SYNCED",
        },
        {
          id: "meal-1",
          type: "meal",
          title: "Oats with almonds",
          subtitle: "Meal logged · 1 bowl",
          timestamp: "2026-09-20T08:30:00Z",
          status: "SYNCED",
        },
      ],
      isLoading: false,
      isError: false,
      refetch: jest.fn().mockResolvedValue({}),
    }),
    usePatientDocuments: () => ({
      data: [
        {
          id: "doc-1",
          patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
          kind: "summary",
          filename: "clinical_summary_sep2026.pdf",
          mime_type: "application/pdf",
          file_size_bytes: 142000,
          created_at: "2026-09-15T12:00:00Z",
          download_url: "https://clinic.local/doc-1.pdf",
        },
      ],
      isLoading: false,
      isError: false,
      refetch: jest.fn().mockResolvedValue({}),
    }),
    useAdministerMedication: () => ({
      mutateAsync: jest.fn().mockResolvedValue({}),
      isPending: false,
    }),
  };
});

function renderPatientExperience() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <SafeAreaProvider
      initialMetrics={{
        frame: { x: 0, y: 0, width: 390, height: 844 },
        insets: { top: 0, left: 0, right: 0, bottom: 0 },
      }}
    >
      <QueryClientProvider client={queryClient}>
        <PatientExperience
          patientId="3fa85f64-5717-4562-b3fc-2c963f66afa6"
          patientName="Rajesh Kumar"
          onSignOut={mockSignOut}
        />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("PatientExperience (Master Patient Product Architecture)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the 5 bottom navigation destinations", () => {
    renderPatientExperience();

    expect(screen.getByRole("tab", { name: /^home tab$/i })).toBeTruthy();
    expect(screen.getByRole("tab", { name: /^record health data$/i })).toBeTruthy();
    expect(screen.getByRole("tab", { name: /^care timeline history$/i })).toBeTruthy();
    expect(screen.getByRole("tab", { name: /^care tasks$/i })).toBeTruthy();
    expect(screen.getByRole("tab", { name: /^account and profile$/i })).toBeTruthy();
  });

  it("renders Home tab with patient header, greeting, role tag, and today summary", () => {
    renderPatientExperience();

    expect(screen.getByText("THALI CARE")).toBeTruthy();
    expect(screen.getByText(/Rajesh Kumar/i)).toBeTruthy();
    expect(screen.getByText("Daily Care")).toBeTruthy();
    expect(screen.getByText("Metformin 500mg")).toBeTruthy();
  });

  it("navigates to Record Hub tab and renders the 4 clinical record cards", () => {
    renderPatientExperience();

    const recordTab = screen.getByRole("tab", { name: /^record health data$/i });
    fireEvent.press(recordTab);

    expect(screen.getByText("Record Health Data")).toBeTruthy();
    expect(screen.getByText("Blood Glucose")).toBeTruthy();
    expect(screen.getByText("Meal & Nutrition")).toBeTruthy();
    expect(screen.getByText("Medication Dose")).toBeTruthy();
    expect(screen.getByText("Care Task")).toBeTruthy();
  });

  it("navigates to Timeline tab and renders category filter chips", () => {
    renderPatientExperience();

    const timelineTab = screen.getByRole("tab", { name: /^care timeline history$/i });
    fireEvent.press(timelineTab);

    expect(screen.getByText("Care Timeline")).toBeTruthy();
    expect(screen.getByText("All")).toBeTruthy();
    expect(screen.getByText("Glucose")).toBeTruthy();
    expect(screen.getByText("Meals")).toBeTruthy();
    expect(screen.getByText("Medication")).toBeTruthy();
  });

  it("navigates to Tasks tab and renders segments", () => {
    renderPatientExperience();

    const tasksTab = screen.getByRole("tab", { name: /^care tasks$/i });
    fireEvent.press(tasksTab);

    expect(screen.getByText("Care Tasks")).toBeTruthy();
    expect(screen.getByText(/Today/i)).toBeTruthy();
    expect(screen.getByText(/Upcoming/i)).toBeTruthy();
    expect(screen.getByText(/Completed/i)).toBeTruthy();
  });

  it("navigates to You tab and renders profile, UHID, and menu items", () => {
    renderPatientExperience();

    const youTab = screen.getByRole("tab", { name: /^account and profile$/i });
    fireEvent.press(youTab);

    expect(screen.getByText("Rajesh Kumar")).toBeTruthy();
    expect(screen.getByText(/UHID-/i)).toBeTruthy();
    expect(screen.getByText("Prescribed Medications")).toBeTruthy();
    expect(screen.getByText("Documents & Reports")).toBeTruthy();
    expect(screen.getByText("Language")).toBeTruthy();
  });

  it("opens THALI Assist modal and presents the patient-safe care guide disclaimer", () => {
    renderPatientExperience();

    const assistButton = screen.getByLabelText(/THALI Assist AI care guide/i);
    fireEvent.press(assistButton);

    expect(screen.getByText("THALI Assist")).toBeTruthy();
    expect(screen.getByText("Patient-Safe Care Guide")).toBeTruthy();
    expect(
      screen.getByText(/does not provide medical diagnoses, prescribe treatments, or alter your clinician-authored plan/i)
    ).toBeTruthy();
  });

  it("does not render sign out button in header banner per streamlined design", () => {
    renderPatientExperience();

    const signOutHeaderButton = screen.queryByRole("button", { name: /^sign out$/i });
    expect(signOutHeaderButton).toBeNull();
  });

  it("triggers sign out confirmation modal from You tab", async () => {
    renderPatientExperience();

    const youTab = screen.getByRole("tab", { name: /^account and profile$/i });
    fireEvent.press(youTab);

    const signOutTabButton = screen.getByRole("button", { name: /^sign out$/i });
    fireEvent.press(signOutTabButton);

    expect(screen.getByText("Sign out of THALI?")).toBeTruthy();

    const confirmButton = screen.getByRole("button", { name: /confirm sign out/i });
    fireEvent.press(confirmButton);

    await act(async () => {});
    expect(mockSignOut).toHaveBeenCalledTimes(1);
  });
});
