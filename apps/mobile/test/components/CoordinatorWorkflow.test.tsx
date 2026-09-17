import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CoordinatorWorkflow } from "../../src/features/tasks/CoordinatorWorkflow";
import type { CareTaskResponse, CareTaskListResponse } from "../../src/services/schemas/tasks";

const validUUID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
const validWorkerUUID = "e4a21190-3cb8-47e2-861f-998811223344";

const mockTasks: CareTaskResponse[] = [
  {
    care_task_id: "ct-coord-01",
    patient_id: validUUID,
    assigned_to_user_id: validWorkerUUID,
    description: "Facility intake assessment",
    status: "open",
    due_at: "2026-09-21T10:00:00Z",
    created_at: "2026-09-17T08:00:00Z",
    completed_at: null,
  },
];

let mockCareTasksState = {
  data: {
    patient_id: null,
    task_count: mockTasks.length,
    items: mockTasks,
  } as CareTaskListResponse | undefined,
  isLoading: false,
  error: null as unknown,
  refetch: jest.fn(),
};

const mockCreateMutate = jest.fn();
const mockReassignMutate = jest.fn();

jest.mock("../../src/features/doctor/usePatients", () => ({
  usePatients: () => ({
    patients: [],
    patientCount: 0,
    isLoading: false,
    isError: false,
    refetch: jest.fn(),
  }),
}));

jest.mock("../../src/features/tasks/useCareTasks", () => ({
  useCareTasks: () => mockCareTasksState,
  useCareTaskDetail: (id: string) => ({
    data: mockTasks.find((t) => t.care_task_id === id) ?? mockTasks[0],
    isLoading: false,
    error: null,
  }),
  useTaskPatient: () => ({
    data: {
      patient_id: validUUID,
      uh_id: "UH-998811",
      name: "Amit Kumar",
      facility_id: "fac-1",
      active: true,
      created_at: "2026-09-17T00:00:00Z",
    },
    isLoading: false,
    error: null,
  }),
  useStartCareTask: () => ({
    mutate: jest.fn(),
    isPending: false,
    error: null,
  }),
  useCompleteCareTask: () => ({
    mutate: jest.fn(),
    isPending: false,
    error: null,
  }),
  useCreateCareTask: (opts?: { onSuccess?: () => void }) => ({
    mutate: (req: unknown) => {
      mockCreateMutate(req);
      opts?.onSuccess?.();
    },
    isPending: false,
    error: null,
  }),
  useReassignCareTask: (opts?: { onSuccess?: () => void }) => ({
    mutate: (req: unknown) => {
      mockReassignMutate(req);
      opts?.onSuccess?.();
    },
    isPending: false,
    error: null,
  }),
}));

function renderWorkflow(props?: Partial<React.ComponentProps<typeof CoordinatorWorkflow>>) {
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
        <CoordinatorWorkflow {...props} />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("CoordinatorWorkflow", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCareTasksState = {
      data: {
        patient_id: null,
        task_count: mockTasks.length,
        items: [...mockTasks],
      },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    };
  });

  it("renders 'Facility Task Queue' heading, tabs, and action button", () => {
    renderWorkflow();

    expect(screen.getByText("Facility Task Queue")).toBeTruthy();
    expect(screen.getByText("All")).toBeTruthy();
    expect(screen.getAllByText("Open").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Create Task")).toBeTruthy();
    expect(screen.getByText("Facility intake assessment")).toBeTruthy();
  });

  it("opens CreateCareTaskModal when 'Create Task' is pressed", () => {
    renderWorkflow();

    const newTaskBtn = screen.getByText("Create Task");
    fireEvent.press(newTaskBtn);

    expect(screen.getByText("Create Care Task")).toBeTruthy();
    expect(screen.getByLabelText("Patient UUID input")).toBeTruthy();
    expect(screen.getByLabelText("Assigned Worker User UUID input")).toBeTruthy();
  });

  it("creates a care task via modal and submits payload", async () => {
    mockCreateMutate.mockImplementationOnce(() => {});

    renderWorkflow();

    // Open modal
    fireEvent.press(screen.getByText("Create Task"));

    // Fill inputs
    fireEvent.changeText(
      screen.getByLabelText("Patient UUID input"),
      validUUID
    );
    fireEvent.changeText(
      screen.getByLabelText("Assigned Worker User UUID input"),
      validWorkerUUID
    );
    fireEvent.changeText(
      screen.getByLabelText("Task description input"),
      "Verify home compliance"
    );

    // Submit
    const submitBtn = screen.getByTestId("submit-create-task-button");
    fireEvent.press(submitBtn);

    await waitFor(() => {
      expect(mockCreateMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          patient_id: validUUID,
          assigned_to_user_id: validWorkerUUID,
          description: "Verify home compliance",
        })
      );
    });
  });

  it("navigates to detail view and opens ReassignCareTaskModal", async () => {
    mockReassignMutate.mockImplementationOnce(() => {});

    renderWorkflow();

    // Tap task card to go to detail
    fireEvent.press(screen.getByText("Facility intake assessment"));

    expect(screen.getByText("Task Details")).toBeTruthy();
    expect(screen.getByText("Amit Kumar")).toBeTruthy();

    // Tap Reassign button
    const reassignBtn = screen.getByRole("button", { name: /reassign task/i });
    fireEvent.press(reassignBtn);

    // Reassign modal should open
    expect(screen.getByText("Reassign Care Task")).toBeTruthy();
    const workerInput = screen.getByLabelText("Replacement worker UUID input");
    expect(workerInput).toBeTruthy();

    fireEvent.changeText(workerInput, "99887766-5544-3322-1100-aabbccddeeff");

    const confirmReassignBtn = screen.getByRole("button", { name: /confirm reassignment/i });
    fireEvent.press(confirmReassignBtn);

    await waitFor(() => {
      expect(mockReassignMutate).toHaveBeenCalledWith({
        taskId: "ct-coord-01",
        body: { new_user_id: "99887766-5544-3322-1100-aabbccddeeff" },
      });
    });
  });

  it("calls onExit callback when back button is pressed from queue view", () => {
    const mockExit = jest.fn();
    renderWorkflow({ onExit: mockExit });

    const backBtn = screen.getByRole("button", { name: /back/i });
    fireEvent.press(backBtn);

    expect(mockExit).toHaveBeenCalledTimes(1);
  });
});
