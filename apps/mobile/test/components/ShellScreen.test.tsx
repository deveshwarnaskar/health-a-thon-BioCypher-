import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ShellScreen from "../../app/(app)/shell";
import type { Role } from "../../src/authz/roles";

let mockAuthState: { name: string; user?: { role: string; actor_id: string; capabilities: string[] } } = {
  name: "authenticated",
  user: { role: "Patient", actor_id: "a-1", capabilities: ["view_own_records"] },
};
let mockSignIn = jest.fn();
let mockSignOut = jest.fn();

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signIn: mockSignIn,
    signOut: mockSignOut,
  }),
}));

jest.mock("../../src/features/meals", () => {
  const { Text } = require("react-native");
  return {
    PatientMealScreen: () => <Text>Mocked PatientMealScreen</Text>,
    DietitianWorkflow: () => <Text>Mocked DietitianWorkflow</Text>,
  };
});

jest.mock("../../src/features/tasks", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Text } = require("react-native");
  return {
    FHWWorkflow: () => <Text>Mocked FHWWorkflow</Text>,
    CoordinatorWorkflow: () => <Text>Mocked CoordinatorWorkflow</Text>,
  };
});

jest.mock("../../src/features/patient", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Text, TouchableOpacity, View } = require("react-native");
  return {
    PatientExperience: ({ onSignOut }: { onSignOut?: () => void }) => (
      <View>
        <Text>Patient</Text>
        <TouchableOpacity
          onPress={onSignOut}
          accessibilityRole="button"
          accessibilityLabel="Sign out"
        >
          <Text>Sign out</Text>
        </TouchableOpacity>
      </View>
    ),
  };
});

jest.mock("../../src/features/doctor", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Text } = require("react-native");
  return {
    DoctorWorkstation: () => <Text>Doctor</Text>,
  };
});

const ALL_ROLES: Role[] = [
  "Patient",
  "Caregiver",
  "Doctor",
  "Nurse",
  "CareCoordinator",
  "Dietitian",
  "FieldHealthWorker",
];

function renderShell() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <SafeAreaProvider initialMetrics={{ frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 0, left: 0, right: 0, bottom: 0 } }}>
      <QueryClientProvider client={queryClient}>
        <ShellScreen />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

describe("ShellScreen (per-role × 7)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  for (const role of ALL_ROLES) {
    it(`renders the ${role} shell with the role label`, () => {
      mockAuthState = {
        name: "authenticated",
        user: { role, actor_id: "a-1", capabilities: ["view_own_records"] },
      };
      renderShell();
      const roleLabel = screen.getByText(
        role === "CareCoordinator"
          ? "Care Coordinator"
          : role === "FieldHealthWorker"
            ? "Field Health Worker"
            : role
      );
      expect(roleLabel).toBeTruthy();
    });
  }

  it("renders the sign-out button", () => {
    mockAuthState = {
      name: "authenticated",
      user: { role: "Patient", actor_id: "a-1", capabilities: ["view_own_records"] },
    };
    renderShell();
    expect(screen.getByRole("button", { name: /sign out/i })).toBeTruthy();
  });

  it("calls signOut when the sign-out button is pressed", async () => {
    mockAuthState = {
      name: "authenticated",
      user: { role: "Patient", actor_id: "a-1", capabilities: ["view_own_records"] },
    };
    renderShell();
    const signOutButton = screen.getByRole("button", { name: /sign out/i });
    fireEvent.press(signOutButton);
    await act(async () => {});
    expect(mockSignOut).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state while not authenticated", () => {
    mockAuthState = { name: "bootstrapping" };
    renderShell();
    expect(screen.getByText(/restoring session/i)).toBeTruthy();
  });

  it("mounts PatientExperience when Patient is authenticated", () => {
    mockAuthState = {
      name: "authenticated",
      user: { role: "Patient", actor_id: "a-1", capabilities: ["view_own_records"] },
    };
    renderShell();
    expect(screen.getByText("Patient")).toBeTruthy();
  });

  it("mounts DietitianWorkflow when Dietitian selects Food destination", () => {
    mockAuthState = {
      name: "authenticated",
      user: { role: "Dietitian", actor_id: "a-1", capabilities: ["READ_OBSERVATIONS"] },
    };
    renderShell();
    const foodCard = screen.getByLabelText("Food (placeholder)");
    fireEvent.press(foodCard);
    expect(screen.getByText("Mocked DietitianWorkflow")).toBeTruthy();
  });

  it("mounts FHWWorkflow when FieldHealthWorker selects Tasks destination", () => {
    mockAuthState = {
      name: "authenticated",
      user: { role: "FieldHealthWorker", actor_id: "a-1", capabilities: ["READ_CARE_TASKS"] },
    };
    renderShell();
    const tasksCard = screen.getByLabelText("Tasks (placeholder)");
    fireEvent.press(tasksCard);
    expect(screen.getByText("Mocked FHWWorkflow")).toBeTruthy();
  });

  it("mounts CoordinatorWorkflow when CareCoordinator selects Queue destination", () => {
    mockAuthState = {
      name: "authenticated",
      user: { role: "CareCoordinator", actor_id: "a-1", capabilities: ["READ_CARE_TASKS"] },
    };
    renderShell();
    const queueCard = screen.getByLabelText("Queue (placeholder)");
    fireEvent.press(queueCard);
    expect(screen.getByText("Mocked CoordinatorWorkflow")).toBeTruthy();
  });
});