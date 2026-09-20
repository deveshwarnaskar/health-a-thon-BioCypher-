import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import LoginScreen from "../../app/(auth)/login";

let mockAuthState: { name: string; category?: string } = { name: "unauthenticated" };
let mockSignIn = jest.fn();
let mockSignOut = jest.fn();
let mockRecoverPassword: jest.Mock | undefined = undefined;

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signIn: mockSignIn,
    signOut: mockSignOut,
    recoverPassword: mockRecoverPassword,
    isBootstrapping: false,
    isUnauthenticated: mockAuthState.name === "unauthenticated" || mockAuthState.name === "session_expired",
    isAuthenticated: mockAuthState.name === "authenticated",
  }),
}));

const redirectHrefs: string[] = [];
const mockRouterPush = jest.fn();
const mockRouterReplace = jest.fn();

jest.mock("expo-router", () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: mockRouterReplace,
    back: jest.fn(),
  }),
  Redirect: ({ href }: { href: string }) => {
    redirectHrefs.push(href);
    return null;
  },
}));

describe("LoginScreen (component-level a11y)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    redirectHrefs.length = 0;
    mockAuthState = { name: "unauthenticated" };
    mockRecoverPassword = undefined;
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

  it("renders clinic enrollment guidance", () => {
    render(<LoginScreen />);
    expect(screen.getByText(/Clinic Enrollment & Access/i)).toBeTruthy();
  });

  it("calls recoverPassword when the reset password button is pressed", () => {
    const fn = jest.fn();
    mockRecoverPassword = fn;
    render(<LoginScreen />);
    const buttons = screen.getAllByRole("button");
    const recoverButton = buttons.find((b) =>
      b.props.accessibilityLabel?.match(/reset|credential/i)
    );
    expect(recoverButton).toBeTruthy();
    if (recoverButton) {
      fireEvent.press(recoverButton);
      expect(fn).toHaveBeenCalledTimes(1);
    }
  });

  it("redirects when authenticated", () => {
    mockAuthState = { name: "authenticated" };
    render(<LoginScreen />);
    expect(redirectHrefs).toContain("/(app)/shell");
  });
});