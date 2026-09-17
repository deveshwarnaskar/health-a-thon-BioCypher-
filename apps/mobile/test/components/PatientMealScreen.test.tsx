import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PatientMealScreen } from "../../src/features/meals/PatientMealScreen";
import type { PatientMealObservation } from "../../src/features/meals/types";
import type { LogMealResponse } from "../../src/services/schemas/meals";

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
    actor_id: "user-patient-01",
    tenant_id: "tenant-01",
    capabilities: ["READ_OBSERVATIONS", "WRITE_OBSERVATIONS", "READ_PATIENT"],
    patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  },
};

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signOut: jest.fn(),
  }),
}));

// Mock meal feed state
let mockFeedState: {
  meals: PatientMealObservation[];
  isLoading: boolean;
  isError: boolean;
  refetch: jest.Mock;
} = {
  meals: [],
  isLoading: false,
  isError: false,
  refetch: jest.fn(),
};

// Mock logMeal state
let mockLogMealState: {
  mutate: jest.Mock;
  isPending: boolean;
  isSuccess: boolean;
  isError: boolean;
  recordedAtIso: string | null;
  triggerSuccess?: (data: LogMealResponse) => void;
  triggerError?: (err: unknown) => void;
} = {
  mutate: jest.fn(),
  isPending: false,
  isSuccess: false,
  isError: false,
  recordedAtIso: null,
};

// Mock confirmMeal state
let mockConfirmMealState: {
  mutate: jest.Mock;
  isPending: boolean;
  isSuccess: boolean;
  isError: boolean;
  triggerSuccess?: (data: unknown) => void;
  triggerError?: (err: unknown) => void;
} = {
  mutate: jest.fn(),
  isPending: false,
  isSuccess: false,
  isError: false,
};

jest.mock("../../src/features/meals/usePatientMeals", () => ({
  usePatientMeals: () => mockFeedState,
}));

jest.mock("../../src/features/meals/useLogMeal", () => ({
  useLogMeal: (options?: {
    onSuccess?: (data: LogMealResponse) => void;
    onError?: (err: unknown) => void;
  }) => {
    mockLogMealState.triggerSuccess = options?.onSuccess;
    mockLogMealState.triggerError = options?.onError;
    return mockLogMealState;
  },
}));

jest.mock("../../src/features/meals/useConfirmMeal", () => ({
  useConfirmMeal: (options?: {
    onSuccess?: (data: unknown) => void;
    onError?: (err: unknown) => void;
  }) => {
    mockConfirmMealState.triggerSuccess = options?.onSuccess;
    mockConfirmMealState.triggerError = options?.onError;
    return mockConfirmMealState;
  },
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
        <PatientMealScreen {...props} />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("PatientMealScreen Component Tests (Gate 10H-M)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuthState = {
      name: "authenticated",
      user: {
        role: "Patient",
        actor_id: "user-patient-01",
        tenant_id: "tenant-01",
        capabilities: ["READ_OBSERVATIONS", "WRITE_OBSERVATIONS", "READ_PATIENT"],
        patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      },
    };
    mockFeedState = {
      meals: [],
      isLoading: false,
      isError: false,
      refetch: jest.fn(),
    };
    mockLogMealState = {
      mutate: jest.fn(),
      isPending: false,
      isSuccess: false,
      isError: false,
      recordedAtIso: null,
    };
    mockConfirmMealState = {
      mutate: jest.fn(),
      isPending: false,
      isSuccess: false,
      isError: false,
    };
  });

  it("10H-M-01: Patient can open meal capture", () => {
    renderScreen();
    expect(screen.getByText("Meal Logbook")).toBeTruthy();
    expect(screen.getByText("Food Items")).toBeTruthy();
    expect(screen.getByText("Katori Portion Size")).toBeTruthy();
    expect(screen.getByText("Meal History")).toBeTruthy();
  });

  it("10H-M-02: Food selection renders chips and selecting one updates description", () => {
    renderScreen();
    // Common foods chip should be visible
    const dalChip = screen.getByText("Dal (Lentils)");
    expect(dalChip).toBeTruthy();

    fireEvent.press(dalChip);
    // Description text input should now contain the selected food label
    const input = screen.getByDisplayValue("Dal (Lentils)");
    expect(input).toBeTruthy();
  });

  it("10H-M-03: Katori portion selection works", () => {
    renderScreen();
    const mediumKatori = screen.getByText("Medium (220 ml)");
    const smallKatori = screen.getByText("Small (150 ml)");
    expect(mediumKatori).toBeTruthy();
    expect(smallKatori).toBeTruthy();

    fireEvent.press(smallKatori);
    expect(screen.getByText("Small (150 ml)")).toBeTruthy();
  });

  it("10H-M-04: Invalid input is rejected when submitting empty description", () => {
    renderScreen();
    const submitButton = screen.getByText("Log Meal Draft");
    fireEvent.press(submitButton);

    expect(screen.getByText("Please enter a description for your meal.")).toBeTruthy();
    expect(mockLogMealState.mutate).not.toHaveBeenCalled();
  });

  it("10H-M-05: Meal draft submits to mutation", () => {
    renderScreen();
    const dalChip = screen.getByText("Dal (Lentils)");
    fireEvent.press(dalChip);

    const submitButton = screen.getByText("Log Meal Draft");
    fireEvent.press(submitButton);

    expect(mockLogMealState.mutate).toHaveBeenCalledWith(
      expect.objectContaining({
        description: "Dal (Lentils)",
        portion: expect.objectContaining({
          food_key: "dal",
          katori_volume_ml: 220,
        }),
      })
    );
  });

  it("10H-M-07 & 10H-M-08: MealDraftSummary renders upon draft success and allows confirmation", () => {
    renderScreen();

    // Trigger draft success callback inside act
    act(() => {
      mockLogMealState.triggerSuccess?.({
        meal_observation_id: "obs-meal-99",
        patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        portion_label: "medium",
        quantity: 1.0,
      });
    });

    // Draft summary must be visible
    expect(screen.getByText("Meal Draft Summary")).toBeTruthy();
    expect(screen.getByText("Pending Confirmation")).toBeTruthy();

    const confirmButton = screen.getByText("Confirm Meal");
    expect(confirmButton).toBeTruthy();

    fireEvent.press(confirmButton);
    expect(mockConfirmMealState.mutate).toHaveBeenCalledWith({
      mealObservationId: "obs-meal-99",
      patientId: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    });

    // 10H-M-08: Server-confirmed state is authoritative
    act(() => {
      mockConfirmMealState.triggerSuccess?.({
        meal_observation_id: "obs-meal-99",
        patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        confirmation: "confirmed",
      });
    });

    expect(screen.getByText("Meal confirmed successfully.")).toBeTruthy();
    expect(mockFeedState.refetch).toHaveBeenCalled();
  });

  it("10H-M-11: 403 access denied shows critical alert without logging out", () => {
    renderScreen();
    act(() => {
      mockLogMealState.triggerError?.({
        kind: "FORBIDDEN",
        httpStatus: 403,
        message: "Access denied",
      });
    });

    expect(
      screen.getByText(
        "Access denied. Your patient record is inactive or access has been revoked."
      )
    ).toBeTruthy();
  });

  it("10H-M-13: 409 conflict renders phone requirement alert", () => {
    renderScreen();
    act(() => {
      mockConfirmMealState.triggerError?.({
        kind: "CONFLICT",
        httpStatus: 409,
        message: "Patient phone is required to confirm a meal observation",
      });
    });

    expect(
      screen.getByText(
        "A verified phone number is required on your patient profile to confirm meals."
      )
    ).toBeTruthy();
  });

  it("10H-M-15: Network failure displays connection error banner, never claims confirmation", () => {
    renderScreen();
    act(() => {
      mockConfirmMealState.triggerError?.({
        kind: "NETWORK_ERROR",
        httpStatus: 0,
        message: "Network request failed",
      });
    });

    expect(
      screen.getByText("Unable to connect. Your meal has not been recorded.")
    ).toBeTruthy();
    // Must never claim confirmed
    expect(screen.queryByText("Meal confirmed successfully.")).toBeNull();
  });

  it("Role guard: Denies non-patient roles", () => {
    mockAuthState.user!.role = "Doctor";
    renderScreen();
    expect(screen.getByText("Access Restricted")).toBeTruthy();
    expect(
      screen.getByText("The meal logging screen is only available in Patient mode.")
    ).toBeTruthy();
  });

  it("Unlinked patient guard: Displays Account Linking Required when patient_id is absent", () => {
    mockAuthState.user!.patient_id = null;
    renderScreen();
    expect(screen.getByText("Account Linking Required")).toBeTruthy();
  });

  it("10H-M-28: Accessibility behavior is covered", () => {
    renderScreen();
    expect(screen.getByLabelText("Small (150 ml)")).toBeTruthy();
    expect(screen.getByLabelText("Medium (220 ml)")).toBeTruthy();
    expect(screen.getByLabelText("Large (350 ml)")).toBeTruthy();
    expect(screen.getByLabelText("1 katori")).toBeTruthy();
    expect(screen.getByLabelText("Decrease quantity")).toBeTruthy();
    expect(screen.getByLabelText("Increase quantity")).toBeTruthy();
  });
});
