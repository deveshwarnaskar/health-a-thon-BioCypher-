import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import LoginScreen from "../../app/(auth)/login";

let mockAuthState: { name: string; category?: string } = { name: "unauthenticated" };
let mockSignIn = jest.fn();
let mockSignOut = jest.fn();

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signIn: mockSignIn,
    signOut: mockSignOut,
    isBootstrapping: false,
    isUnauthenticated: mockAuthState.name === "unauthenticated" || mockAuthState.name === "session_expired",
    isAuthenticated: mockAuthState.name === "authenticated",
  }),
}));

describe("LoginScreen (component-level a11y)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuthState = { name: "unauthenticated" };
  });

  it("renders the clinic sign-in button with accessible name", () => {
    render(<LoginScreen />);
    const button = screen.getByRole("button");
    expect(button).toBeTruthy();
    expect(button.props.accessibilityLabel).toMatch(/clinic sign-in/i);
  });

  it("disables the button and shows busy label while authenticating", () => {
    mockAuthState = { name: "authenticating" };
    render(<LoginScreen />);
    const button = screen.getByRole("button");
    expect(button.props.accessibilityState.disabled).toBe(true);
    expect(button.props.accessibilityLabel).toMatch(/secure sign-in/i);
  });

  it("shows an error alert on failed state", () => {
    mockAuthState = { name: "failed", category: "network" };
    render(<LoginScreen />);
    const alert = screen.getByRole("alert");
    expect(alert).toBeTruthy();
    expect(alert.props.accessibilityLabel).toMatch(/identity service/i);
  });

  it("shows session expired alert on session_expired state", () => {
    mockAuthState = { name: "session_expired" };
    render(<LoginScreen />);
    const alert = screen.getByRole("alert");
    expect(alert).toBeTruthy();
    expect(alert.props.accessibilityLabel).toMatch(/session expired/i);
  });

  it("calls signIn when the button is pressed", () => {
    render(<LoginScreen />);
    const button = screen.getByRole("button");
    fireEvent.press(button);
    expect(mockSignIn).toHaveBeenCalledTimes(1);
  });
});