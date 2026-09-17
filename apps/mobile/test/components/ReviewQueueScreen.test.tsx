import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReviewQueueScreen } from "../../src/features/doctor/ReviewQueueScreen";
import type { AIArtifactResponse } from "../../src/services/schemas/ai";

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
    capabilities: ["READ_OBSERVATIONS", "REVIEW_AI_ARTIFACTS"],
    patient_id: null,
  },
};

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signOut: jest.fn(),
  }),
}));

let mockQueueState: {
  queue: AIArtifactResponse[];
  artifactCount: number;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: jest.Mock;
} = {
  queue: [],
  artifactCount: 0,
  isLoading: false,
  isError: false,
  error: undefined,
  refetch: jest.fn(),
};

jest.mock("../../src/features/doctor/useReviewQueue", () => ({
  useReviewQueue: () => mockQueueState,
}));

const ARTIFACT: AIArtifactResponse = {
  artifact_id: "art-1",
  patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  artifact_kind: "meal_review",
  state: "PENDING_REVIEW",
  summary: "AI proposed a meal-plan revision for this patient.",
  created_at: "2026-09-17T10:00:00Z",
};

function renderScreen(props?: {
  onSelect?: (artifact: AIArtifactResponse) => void;
  onBack?: () => void;
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
        <ReviewQueueScreen {...props} />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("ReviewQueueScreen Component Tests (Gate 10F-M)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuthState = {
      name: "authenticated",
      user: {
        role: "Doctor",
        actor_id: "doc-1",
        tenant_id: "tenant-1",
        capabilities: ["READ_OBSERVATIONS", "REVIEW_AI_ARTIFACTS"],
        patient_id: null,
      },
    };
    mockQueueState = {
      queue: [],
      artifactCount: 0,
      isLoading: false,
      isError: false,
      error: undefined,
      refetch: jest.fn(),
    };
  });

  // Scenario 1: Doctor sees the PENDING_REVIEW queue in backend order
  it("renders the review queue for a Doctor", () => {
    mockQueueState.queue = [ARTIFACT];
    renderScreen();
    expect(screen.getByText("Review")).toBeTruthy();
    expect(screen.getByText("meal_review")).toBeTruthy();
    expect(screen.getByText("AI proposed a meal-plan revision for this patient.")).toBeTruthy();
    expect(screen.getAllByText("PENDING_REVIEW").length).toBeGreaterThan(0);
  });

  // Scenario 2: Loading state while the queue query is pending
  it("renders loading state while the queue is pending", () => {
    mockQueueState.isLoading = true;
    renderScreen();
    expect(screen.getByText("Loading review queue…")).toBeTruthy();
  });

  // Scenario 3: Empty state when the backend has no pending reviews
  it("renders empty state when the queue is empty", () => {
    renderScreen();
    expect(screen.getByText("No pending reviews")).toBeTruthy();
  });

  // Scenario 4: Transient error surfaces a retryable state that refetches
  it("renders error state and refetches on retry", () => {
    mockQueueState.isError = true;
    mockQueueState.error = { kind: "NETWORK_ERROR", httpStatus: 0, message: "Network unreachable" };
    renderScreen();
    expect(screen.getByText("Could not load review queue")).toBeTruthy();
    const retryBtn = screen.getByRole("button", { name: /Try again/i });
    fireEvent.press(retryBtn);
    expect(mockQueueState.refetch).toHaveBeenCalledTimes(1);
  });

  // Scenario 5: 403 is per-resource revocation → safe state + back, never logout
  it("shows access-revoked state on 403 and returns to main menu", () => {
    mockQueueState.isError = true;
    mockQueueState.error = { kind: "FORBIDDEN", httpStatus: 403, code: "REVIEW_UNAUTHORIZED" };
    const onBack = jest.fn();
    renderScreen({ onBack });

    expect(screen.getByText("Access Revoked")).toBeTruthy();
    const backBtn = screen.getByRole("button", { name: /Return to Main Menu/i });
    fireEvent.press(backBtn);
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  // Scenario 6: Selecting a queue card returns the full artifact DTO
  it("selects a queue item and returns the full artifact DTO", () => {
    mockQueueState.queue = [ARTIFACT];
    const onSelect = jest.fn();
    renderScreen({ onSelect });

    fireEvent.press(screen.getByLabelText(`Review artifact for patient ${ARTIFACT.patient_id}`));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(ARTIFACT);
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
        patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      },
    };
    renderScreen();
    expect(screen.getByText("Access Restricted")).toBeTruthy();
    expect(
      screen.getByText("The AI review queue is only available in Doctor mode.")
    ).toBeTruthy();
  });
});