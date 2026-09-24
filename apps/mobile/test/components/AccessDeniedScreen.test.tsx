import React from "react";
import { fireEvent, render, screen } from "@testing-library/react-native";
import AccessDeniedScreen from "../../app/access-denied";

let mockAuthState: { name: string; reason?: string } = { name: "access_denied", reason: "general" };
let mockSignOut = jest.fn();
const redirectHrefs: string[] = [];

jest.mock("expo-router", () => ({
  Redirect: ({ href }: { href: string }) => {
    redirectHrefs.push(href);
    return null;
  },
}));

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signOut: mockSignOut,
  }),
}));

describe("AccessDeniedScreen (component-level a11y)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    redirectHrefs.length = 0;
    mockAuthState = { name: "access_denied", reason: "general" };
  });

  it("renders the access-limited heading", () => {
    render(<AccessDeniedScreen />);
    expect(screen.getByText(/access is limited/i)).toBeTruthy();
  });

  it("shows the correct denial message for unknown_role", () => {
    mockAuthState = { name: "access_denied", reason: "unknown_role" };
    render(<AccessDeniedScreen />);
    expect(screen.getByText(/recognized role/i)).toBeTruthy();
  });

  it("shows the correct denial message for caregiver_revoked", () => {
    mockAuthState = { name: "access_denied", reason: "caregiver_revoked" };
    render(<AccessDeniedScreen />);
    expect(screen.getByText(/revoked/i)).toBeTruthy();
  });

  it("shows the correct denial message for deactivated", () => {
    mockAuthState = { name: "deactivated" };
    render(<AccessDeniedScreen />);
    expect(screen.getByText(/deactivated/i)).toBeTruthy();
  });

  it("clears the denied session when returning to sign in", () => {
    render(<AccessDeniedScreen />);
    fireEvent.press(screen.getByRole("button", { name: /back to sign in/i }));
    expect(mockSignOut).toHaveBeenCalledTimes(1);
  });

  it("leaves the denial page after sign out", () => {
    mockAuthState = { name: "unauthenticated" };
    render(<AccessDeniedScreen />);
    expect(redirectHrefs).toContain("/(auth)/login");
  });
});
