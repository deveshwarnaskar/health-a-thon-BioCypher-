import React from "react";
import { render, screen } from "@testing-library/react-native";
import AccessDeniedScreen from "../../app/(app)/access-denied";

let mockAuthState: { name: string; reason?: string } = { name: "access_denied", reason: "general" };
let mockSignIn = jest.fn();
let mockSignOut = jest.fn();

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signIn: mockSignIn,
    signOut: mockSignOut,
  }),
}));

describe("AccessDeniedScreen (component-level a11y)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
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

  it("renders retry and sign-out buttons", () => {
    render(<AccessDeniedScreen />);
    const retryButton = screen.getByRole("button", { name: /try signing in again/i });
    const signOutButton = screen.getByRole("button", { name: /sign out/i });
    expect(retryButton).toBeTruthy();
    expect(signOutButton).toBeTruthy();
  });
});