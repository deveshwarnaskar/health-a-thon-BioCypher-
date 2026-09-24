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

  it("asks for an email instead of starting browser sign-in on an empty form", () => {
    render(<LoginScreen />);
    const button = screen.getByRole("button");
    fireEvent.press(button);
    expect(mockSignIn).not.toHaveBeenCalled();
    expect(screen.getByText(/please enter your email address/i)).toBeTruthy();
  });

  it("does not render clinic enrollment guidance", () => {
    render(<LoginScreen />);
    expect(screen.queryByText(/Clinic Enrollment & Access/i)).toBeNull();
  });

  it("does not render the extra reset credentials button below sign in", () => {
    const fn = jest.fn();
    mockRecoverPassword = fn;
    render(<LoginScreen />);
    expect(
      screen.queryByRole("button", { name: /Forgot password \/ Reset credentials/i })
    ).toBeNull();
    expect(screen.getByLabelText(/Forgot password recovery link/i)).toBeTruthy();
    expect(fn).not.toHaveBeenCalled();
  });

  it("redirects when authenticated", () => {
    mockAuthState = { name: "authenticated" };
    render(<LoginScreen />);
    expect(redirectHrefs).toContain("/(app)/shell");
  });

  it("submits direct credentials when email and password are provided", () => {
    render(<LoginScreen />);
    const emailInput = screen.getByLabelText(/Email address input/i);
    const passwordInput = screen.getByLabelText(/Password input/i);
    const button = screen.getByRole("button");

    fireEvent.changeText(emailInput, "patient@thali.dev");
    fireEvent.changeText(passwordInput, "SecretPass123!");
    fireEvent.press(button);

    expect(mockSignIn).toHaveBeenCalledWith("patient@thali.dev", "SecretPass123!");
  });

  it("shows validation error when email is missing but password is provided", () => {
    render(<LoginScreen />);
    const passwordInput = screen.getByLabelText(/Password input/i);
    const button = screen.getByRole("button");

    fireEvent.changeText(passwordInput, "SecretPass123!");
    fireEvent.press(button);

    expect(screen.getByText(/Please enter your email address/i)).toBeTruthy();
    expect(mockSignIn).not.toHaveBeenCalled();
  });

  it("shows validation error when email is invalid", () => {
    render(<LoginScreen />);
    const emailInput = screen.getByLabelText(/Email address input/i);
    const passwordInput = screen.getByLabelText(/Password input/i);
    const button = screen.getByRole("button");

    fireEvent.changeText(emailInput, "invalid-email-no-at");
    fireEvent.changeText(passwordInput, "SecretPass123!");
    fireEvent.press(button);

    expect(screen.getByText(/Please enter a valid email address/i)).toBeTruthy();
    expect(mockSignIn).not.toHaveBeenCalled();
  });

  it("navigates to forgot-password screen when forgot link is tapped", () => {
    render(<LoginScreen />);
    const forgotLink = screen.getByLabelText(/Forgot password recovery link/i);
    fireEvent.press(forgotLink);
    expect(mockRouterReplace).toHaveBeenCalledWith("/(auth)/forgot-password");
    expect(mockRouterPush).not.toHaveBeenCalled();
  });

  it("navigates to signup screen when signup link is tapped", () => {
    render(<LoginScreen />);
    const signupLink = screen.getByLabelText(/Create account sign up link/i);
    fireEvent.press(signupLink);
    expect(mockRouterReplace).toHaveBeenCalledWith("/(auth)/signup");
    expect(mockRouterPush).not.toHaveBeenCalled();
  });

  it("displays backend error details like account locked", () => {
    mockAuthState = {
      name: "failed",
      category: "unknown",
      error: "Account is locked due to too many failed attempts. Try again later.",
    } as any;
    render(<LoginScreen />);
    expect(screen.getByText(/Account is locked due to too many failed attempts/i)).toBeTruthy();
  });
});
