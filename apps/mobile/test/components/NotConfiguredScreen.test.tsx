import React from "react";
import { render, screen } from "@testing-library/react-native";
import NotConfiguredScreen from "../../app/(auth)/not-configured";

jest.mock("../../src/auth/notConfiguredSession", () => ({
  useNotConfiguredAuth: () => ({
    isBootstrapping: false,
    isUnauthenticated: true,
    isAuthenticated: false,
    authEnabled: false,
    signIn: jest.fn(),
    signOut: jest.fn(),
  }),
}));

describe("NotConfiguredScreen (component-level a11y)", () => {
  it("renders the authentication-not-configured message", () => {
    render(<NotConfiguredScreen />);
    const title = screen.getByText(/authentication is not configured/i);
    expect(title).toBeTruthy();
  });

  it("explains that no sign-in is available", () => {
    render(<NotConfiguredScreen />);
    expect(screen.getByText(/no sign-in is available/i)).toBeTruthy();
  });

  it("mentions EXPO_PUBLIC_AUTH_ENABLED in the guidance text", () => {
    render(<NotConfiguredScreen />);
    expect(screen.getByText(/EXPO_PUBLIC_AUTH_ENABLED/i)).toBeTruthy();
  });
});