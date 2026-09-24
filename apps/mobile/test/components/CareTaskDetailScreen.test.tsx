import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CareTaskDetailScreen } from "../../src/features/tasks/CareTaskDetailScreen";
import type { CareTaskResponse } from "../../src/services/schemas/tasks";
import type { PatientSummaryResponse } from "../../src/services/schemas/patients";

const validUUID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
const validWorkerUUID = "e4a21190-3cb8-47e2-861f-998811223344";

const mockTask: CareTaskResponse = {
  care_task_id: "ct-001",
  patient_id: validUUID,
  assigned_to_user_id: validWorkerUUID,
  description: "Check fasting glucose and confirm morning meal portion.",
  status: "open",
  due_at: "2026-09-20T10:00:00Z",
  created_at: "2026-09-17T08:00:00Z",
  completed_at: null,
};

const mockPatient: PatientSummaryResponse = {
  patient_id: validUUID,
  uh_id: "UH-998877",
  name: "Sunita Verma",
  facility_id: "fac-city-east",
  active: true,
  created_at: "2026-09-17T00:00:00Z",
};

let mockTaskState = {
  data: mockTask as CareTaskResponse | undefined,
  isLoading: false,
  error: null as unknown,
};

let mockPatientState = {
  data: mockPatient as PatientSummaryResponse | undefined,
  isLoading: false,
  error: null as unknown,
};

const mockStartMutate = jest.fn();
const mockCompleteMutate = jest.fn();

jest.mock("../../src/features/tasks/useCareTasks", () => ({
  useCareTaskDetail: () => mockTaskState,
  useTaskPatient: () => mockPatientState,
  useStartCareTask: () => ({
    mutate: mockStartMutate,
    isPending: false,
    error: null,
  }),
  useCompleteCareTask: () => ({
    mutate: mockCompleteMutate,
    isPending: false,
    error: null,
  }),
}));

function renderDetail(props?: Partial<React.ComponentProps<typeof CareTaskDetailScreen>>) {
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
        <CareTaskDetailScreen
          taskId="ct-001"
          {...props}
        />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("CareTaskDetailScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockTaskState = {
      data: { ...mockTask },
      isLoading: false,
      error: null,
    };
    mockPatientState = {
      data: { ...mockPatient },
      isLoading: false,
      error: null,
    };
  });

  it("renders task details and resolved patient context", () => {
    renderDetail({ isFhw: true });

    expect(screen.getByText("Task Details")).toBeTruthy();
    expect(
      screen.getByText("Check fasting glucose and confirm morning meal portion.")
    ).toBeTruthy();
    expect(screen.getByText("Sunita Verma")).toBeTruthy();
    expect(screen.getByText(/UH-998877/)).toBeTruthy();
  });

  it("shows warning and disables actions when patient is inactive", () => {
    mockPatientState = {
      data: { ...mockPatient, active: false },
      isLoading: false,
      error: null,
    };

    renderDetail({ isFhw: true });

    expect(screen.getByText("Inactive Patient")).toBeTruthy();
    expect(
      screen.getByText("This patient record is deactivated. Task actions are locked.")
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /start task/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /complete task/i })).toBeNull();
  });

  it("calls startCareTask mutation when Start Task is pressed", () => {
    renderDetail({ isFhw: true });

    const startBtn = screen.getByRole("button", { name: /start task/i });
    fireEvent.press(startBtn);

    expect(mockStartMutate).toHaveBeenCalledWith("ct-001");
  });

  it("calls completeCareTask mutation when Complete Task is pressed", () => {
    renderDetail({ isFhw: true });

    const completeBtn = screen.getByRole("button", { name: /complete task/i });
    fireEvent.press(completeBtn);

    expect(mockCompleteMutate).toHaveBeenCalledWith("ct-001");
  });

  it("shows Coordinator reassign button when isCoordinator is true", () => {
    const mockOnReassign = jest.fn();
    renderDetail({ isCoordinator: true, onReassign: mockOnReassign });

    const reassignBtn = screen.getByRole("button", { name: /reassign task/i });
    expect(reassignBtn).toBeTruthy();

    fireEvent.press(reassignBtn);
    expect(mockOnReassign).toHaveBeenCalledWith("ct-001");
  });

  it("shows FHW field actions when isFhw is true and triggers callbacks", () => {
    const mockRecordGlucose = jest.fn();
    const mockLogMeal = jest.fn();

    renderDetail({
      isFhw: true,
      onRecordGlucose: mockRecordGlucose,
      onLogMeal: mockLogMeal,
    });

    const glucoseBtn = screen.getByRole("button", { name: /record blood glucose/i });
    expect(glucoseBtn).toBeTruthy();
    fireEvent.press(glucoseBtn);
    expect(mockRecordGlucose).toHaveBeenCalledWith(validUUID);

    const mealBtn = screen.getByRole("button", { name: /log meal observation/i });
    expect(mealBtn).toBeTruthy();
    fireEvent.press(mealBtn);
    expect(mockLogMeal).toHaveBeenCalledWith(validUUID);
  });
});
