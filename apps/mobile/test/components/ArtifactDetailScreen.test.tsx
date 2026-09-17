import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ArtifactDetailScreen } from "../../src/features/doctor/ArtifactDetailScreen";
import type { AIArtifactResponse } from "../../src/services/schemas/ai";
import type { ApiErrorDetails } from "../../src/services/api/errors";

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

let mockDetailState: {
  artifact: AIArtifactResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: jest.Mock;
} = {
  artifact: null,
  isLoading: false,
  isError: false,
  error: undefined,
  refetch: jest.fn(),
};

jest.mock("../../src/features/doctor/useArtifactDetail", () => ({
  useArtifactDetail: () => mockDetailState,
}));

let mockReviewState: {
  mutate: jest.Mock;
  mutateAsync: jest.Mock;
  isPending: boolean;
  isError: boolean;
  error: unknown;
  reset: jest.Mock;
} = {
  mutate: jest.fn(),
  mutateAsync: jest.fn(),
  isPending: false,
  isError: false,
  error: null,
  reset: jest.fn(),
};

const mockReviewCallbacks: {
  onSuccess?: (data: unknown) => void;
  onError?: (error: unknown) => void;
} = {};

jest.mock("../../src/features/doctor/useReviewArtifact", () => ({
  useReviewArtifact: (options?: {
    onSuccess?: (data: unknown) => void;
    onError?: (error: unknown) => void;
  }) => {
    mockReviewCallbacks.onSuccess = options?.onSuccess;
    mockReviewCallbacks.onError = options?.onError;
    return mockReviewState;
  },
}));

const ARTIFACT: AIArtifactResponse = {
  artifact_id: "art-1",
  patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  artifact_kind: "meal_review",
  state: "PENDING_REVIEW",
  summary: "AI proposed a meal-plan revision for this patient.",
  created_at: "2026-09-17T10:00:00Z",
};

function renderScreen(props?: { artifactId?: string; onBack?: () => void }) {
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
        <ArtifactDetailScreen artifactId={props?.artifactId ?? "art-1"} onBack={props?.onBack} />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("ArtifactDetailScreen Component Tests (Gate 10F-M)", () => {
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
    mockDetailState = {
      artifact: null,
      isLoading: false,
      isError: false,
      error: undefined,
      refetch: jest.fn(),
    };
    mockReviewState = {
      mutate: jest.fn(),
      mutateAsync: jest.fn(),
      isPending: false,
      isError: false,
      error: null,
      reset: jest.fn(),
    };
  });

  // Scenario 1: Doctor sees the artifact review facts + decision controls
  it("renders artifact detail with review decision form", () => {
    mockDetailState.artifact = ARTIFACT;
    renderScreen();

    expect(screen.getByText("meal_review")).toBeTruthy();
    expect(screen.getByText("AI proposed a meal-plan revision for this patient.")).toBeTruthy();
    expect(screen.getByText("Review Decision")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Submit review/i })).toBeTruthy();
  });

  // Scenario 2: Loading state while the detail query is pending
  it("renders loading state while the artifact is pending", () => {
    mockDetailState.isLoading = true;
    renderScreen();
    expect(screen.getByText("Loading artifact…")).toBeTruthy();
  });

  // Scenario 3: 403 detail → access revoked (never logout)
  it("shows access-revoked state on 403 detail and returns to queue", () => {
    mockDetailState.isError = true;
    mockDetailState.error = { kind: "FORBIDDEN", httpStatus: 403, code: "REVIEW_UNAUTHORIZED" };
    const onBack = jest.fn();
    renderScreen({ onBack });

    expect(screen.getByText("Access Revoked")).toBeTruthy();
    const backBtn = screen.getByRole("button", { name: /Return to Review Queue/i });
    fireEvent.press(backBtn);
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  // Scenario 4: 404 detail → unavailable (never reveals existence)
  it("shows unavailable state on 404 detail", () => {
    mockDetailState.isError = true;
    mockDetailState.error = { kind: "NOT_FOUND", httpStatus: 404, message: "missing" };
    renderScreen();
    expect(screen.getByText("Artifact unavailable")).toBeTruthy();
  });

  // Scenario 5: Approve decision submits the sealed request shape
  it("submits an APPROVE decision without an edited summary", () => {
    mockDetailState.artifact = ARTIFACT;
    renderScreen();

    fireEvent.press(screen.getByRole("button", { name: /Submit review/i }));

    expect(mockReviewState.mutate).toHaveBeenCalledTimes(1);
    expect(mockReviewState.mutate).toHaveBeenCalledWith({
      decision: "approve",
      edited_summary: null,
    });
  });

  // Scenario 6: EDIT requires a corrected summary before submission
  it("validates that EDIT carries a corrected summary", () => {
    mockDetailState.artifact = ARTIFACT;
    renderScreen();

    fireEvent.press(screen.getByRole("radio", { name: /Edit/i }));
    fireEvent.press(screen.getByRole("button", { name: /Submit review/i }));

    expect(mockReviewState.mutate).not.toHaveBeenCalled();
    expect(screen.getByText("Enter a corrected summary to submit an Edit review.")).toBeTruthy();

    fireEvent.changeText(screen.getByLabelText("Corrected summary"), "Revised AI summary.");
    fireEvent.press(screen.getByRole("button", { name: /Submit review/i }));

    expect(mockReviewState.mutate).toHaveBeenCalledTimes(1);
    expect(mockReviewState.mutate).toHaveBeenCalledWith({
      decision: "edit",
      edited_summary: "Revised AI summary.",
    });
  });

  // Scenario 7: Backend confirmation renders the success state (no local fake)
  it("renders a confirmation banner only after backend success", () => {
    mockDetailState.artifact = ARTIFACT;
    renderScreen();

    expect(screen.queryByText(/Review recorded/i)).toBeNull();

    act(() => {
      mockReviewCallbacks.onSuccess?.({
        artifact_id: "art-1",
        state: "APPROVED",
        reviewed_by_user_id: "doc-1",
      });
    });

    expect(screen.getByText("Review recorded")).toBeTruthy();
    expect(screen.getByText(/meal_review marked APPROVED/i)).toBeTruthy();
  });

  // Scenario 8: 403 during submit → revoked state, not a fake success or logout
  it("shows revoked state when a submit is denied with 403", () => {
    mockDetailState.artifact = ARTIFACT;
    const onBack = jest.fn();
    renderScreen({ onBack });

    act(() => {
      mockReviewCallbacks.onError?.({
        kind: "FORBIDDEN",
        httpStatus: 403,
        code: "REVIEW_UNAUTHORIZED",
        message: "capability removed",
      } as ApiErrorDetails);
    });

    expect(screen.getByText("Access Revoked")).toBeTruthy();
    expect(screen.queryByText(/Review recorded/i)).toBeNull();
  });

  // Scenario 9: Network failure never implies success
  it("shows a non-confirmation banner on network failure", () => {
    mockDetailState.artifact = ARTIFACT;
    renderScreen();

    act(() => {
      mockReviewCallbacks.onError?.({
        kind: "NETWORK_ERROR",
        httpStatus: 0,
        message: "Network unreachable",
      } as ApiErrorDetails);
    });

    expect(screen.getByText("Review Failed")).toBeTruthy();
    expect(screen.getByText("Unable to connect. Your review has not been submitted.")).toBeTruthy();
    expect(screen.queryByText(/Review recorded/i)).toBeNull();
  });

  // Scenario 10: Non-Doctor principals are blocked at the screen boundary
  it("renders access restricted notice when the actor is not a Doctor", () => {
    mockAuthState = {
      name: "authenticated",
      user: {
        role: "Caregiver",
        actor_id: "cg-1",
        tenant_id: "tenant-1",
        capabilities: ["READ_GLUCOSE"],
        patient_id: null,
      },
    };
    renderScreen();
    expect(screen.getByText("Access Restricted")).toBeTruthy();
    expect(
      screen.getByText("AI artifact review is only available in Doctor mode.")
    ).toBeTruthy();
  });
});