import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FHWWorkflow } from "../../src/features/tasks/FHWWorkflow";
import type { CareTaskResponse, CareTaskListResponse } from "../../src/services/schemas/tasks";

const validUUID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
const validWorkerUUID = "e4a21190-3cb8-47e2-861f-998811223344";

const mockTasks: CareTaskResponse[] = [
  {
    care_task_id: "ct-open-01",
    patient_id: validUUID,
    assigned_to_user_id: validWorkerUUID,
    description: "Check morning fasting glucose",
    status: "open",
    due_at: "2026-09-20T08:00:00Z",
    created_at: "2026-09-17T08:00:00Z",
    completed_at: null,
  },
  {
    care_task_id: "ct-prog-02",
    patient_id: validUUID,
    assigned_to_user_id: validWorkerUUID,
    description: "Observe lunch portion",
    status: "in_progress",
    due_at: "2026-09-20T13:00:00Z",
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
      uh_id: "UH-12345",
      name: "Ramesh Sharma",
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
}));

function renderWorkflow(props?: Partial<React.ComponentProps<typeof FHWWorkflow>>) {
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
        <FHWWorkflow {...props} />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("FHWWorkflow", () => {
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

  it("renders 'My Tasks' heading and tab filters", () => {
    renderWorkflow();

    expect(screen.getByText("My Tasks")).toBeTruthy();
    expect(screen.getByText("All")).toBeTruthy();
    expect(screen.getAllByText("Open").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("In Progress").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Completed")).toBeTruthy();
  });

  it("renders assigned task cards in list", () => {
    renderWorkflow();

    expect(screen.getByText("Check morning fasting glucose")).toBeTruthy();
    expect(screen.getByText("Observe lunch portion")).toBeTruthy();
  });

  it("shows empty state when no tasks match filter", () => {
    mockCareTasksState = {
      data: {
        patient_id: null,
        task_count: 0,
        items: [],
      },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    };

    renderWorkflow();

    expect(screen.getByText("No Tasks Found")).toBeTruthy();
  });

  it("navigates to detail screen on task card press", () => {
    renderWorkflow();

    const taskCard = screen.getByText("Check morning fasting glucose");
    fireEvent.press(taskCard);

    expect(screen.getByText("Task Details")).toBeTruthy();
    expect(screen.getByText("Ramesh Sharma")).toBeTruthy();
  });

  it("navigates back to list view from detail screen", () => {
    renderWorkflow();

    const taskCard = screen.getByText("Check morning fasting glucose");
    fireEvent.press(taskCard);

    expect(screen.getByText("Task Details")).toBeTruthy();

    const backButton = screen.getByRole("button", { name: /back/i });
    fireEvent.press(backButton);

    expect(screen.getByText("My Tasks")).toBeTruthy();
  });

  it("calls onExit callback when exiting workflow from list view", () => {
    const mockExit = jest.fn();
    renderWorkflow({ onExit: mockExit });

    const backButton = screen.getByRole("button", { name: /back/i });
    fireEvent.press(backButton);

    expect(mockExit).toHaveBeenCalledTimes(1);
  });
});
