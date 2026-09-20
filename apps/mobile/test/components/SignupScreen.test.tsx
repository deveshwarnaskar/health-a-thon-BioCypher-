import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react-native";
import SignupScreen from "../../app/(auth)/signup";

let mockAuthState: { name: string; category?: string } = { name: "unauthenticated" };
let mockSignUp = jest.fn();

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: mockAuthState,
    signUp: mockSignUp,
    isBootstrapping: false,
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

describe("SignupScreen (component-level a11y & workflows)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    redirectHrefs.length = 0;
    mockAuthState = { name: "unauthenticated" };
    mockSignUp = jest.fn().mockResolvedValue({ user_status: "active", role: "patient" });
  });

  it("renders the create account title and subtitle", () => {
    render(<SignupScreen />);
    expect(screen.getByText(/Create Account/i)).toBeTruthy();
    expect(screen.getByText(/Join THALI × P.L.A.T.E./i)).toBeTruthy();
  });

  it("renders exactly the three supported roles", () => {
    render(<SignupScreen />);
    expect(screen.getByText("Patient")).toBeTruthy();
    expect(screen.getByText("Caregiver")).toBeTruthy();
    expect(screen.getByText("Doctor")).toBeTruthy();
  });

  it("shows clinician invite code input only when Doctor is selected", () => {
    render(<SignupScreen />);
    expect(screen.queryByLabelText(/Clinician invite code input/i)).toBeNull();

    const doctorOption = screen.getByText("Doctor");
    fireEvent.press(doctorOption);

    expect(screen.getByLabelText(/Clinician invite code input/i)).toBeTruthy();
  });

  it("validates invalid email before submission", async () => {
    render(<SignupScreen />);
    const emailInput = screen.getByLabelText(/Email address input/i);
    const passwordInput = screen.getByLabelText(/^Password input$/i);
    const confirmInput = screen.getByLabelText(/Confirm password input/i);
    const button = screen.getByRole("button", { name: /Register & Sign In/i });

    fireEvent.changeText(emailInput, "not-an-email");
    fireEvent.changeText(passwordInput, "ValidPassword123!");
    fireEvent.changeText(confirmInput, "ValidPassword123!");
    fireEvent.press(button);

    expect(screen.getByText(/Please enter a valid email address/i)).toBeTruthy();
    expect(mockSignUp).not.toHaveBeenCalled();
  });

  it("validates short password (< 8 chars)", async () => {
    render(<SignupScreen />);
    const emailInput = screen.getByLabelText(/Email address input/i);
    const passwordInput = screen.getByLabelText(/^Password input$/i);
    const confirmInput = screen.getByLabelText(/Confirm password input/i);
    const button = screen.getByRole("button", { name: /Register & Sign In/i });

    fireEvent.changeText(emailInput, "user@thali.dev");
    fireEvent.changeText(passwordInput, "short");
    fireEvent.changeText(confirmInput, "short");
    fireEvent.press(button);

    expect(screen.getByText(/Password must be at least 8 characters long/i)).toBeTruthy();
    expect(mockSignUp).not.toHaveBeenCalled();
  });

  it("validates password confirmation mismatch", async () => {
    render(<SignupScreen />);
    const emailInput = screen.getByLabelText(/Email address input/i);
    const passwordInput = screen.getByLabelText(/^Password input$/i);
    const confirmInput = screen.getByLabelText(/Confirm password input/i);
    const button = screen.getByRole("button", { name: /Register & Sign In/i });

    fireEvent.changeText(emailInput, "user@thali.dev");
    fireEvent.changeText(passwordInput, "ValidPassword123!");
    fireEvent.changeText(confirmInput, "DifferentPassword123!");
    fireEvent.press(button);

    expect(screen.getByText(/Passwords do not match/i)).toBeTruthy();
    expect(mockSignUp).not.toHaveBeenCalled();
  });

  it("submits patient registration with valid details", async () => {
    render(<SignupScreen />);
    const nameInput = screen.getByLabelText(/Full name input/i);
    const emailInput = screen.getByLabelText(/Email address input/i);
    const passwordInput = screen.getByLabelText(/^Password input$/i);
    const confirmInput = screen.getByLabelText(/Confirm password input/i);
    const button = screen.getByRole("button", { name: /Register & Sign In/i });

    fireEvent.changeText(nameInput, "Aarav Patel");
    fireEvent.changeText(emailInput, "aarav@thali.dev");
    fireEvent.changeText(passwordInput, "SecurePass123!");
    fireEvent.changeText(confirmInput, "SecurePass123!");
    fireEvent.press(button);

    await waitFor(() => {
      expect(mockSignUp).toHaveBeenCalledWith({
        name: "Aarav Patel",
        email: "aarav@thali.dev",
        password: "SecurePass123!",
        role: "patient",
      });
    });
  });

  it("submits doctor registration with facility invite code", async () => {
    render(<SignupScreen />);
    fireEvent.press(screen.getByText("Doctor"));

    const nameInput = screen.getByLabelText(/Full name input/i);
    const emailInput = screen.getByLabelText(/Email address input/i);
    const inviteInput = screen.getByLabelText(/Clinician invite code input/i);
    const passwordInput = screen.getByLabelText(/^Password input$/i);
    const confirmInput = screen.getByLabelText(/Confirm password input/i);
    const button = screen.getByRole("button", { name: /Register & Sign In/i });

    fireEvent.changeText(nameInput, "Dr. Priya Roy");
    fireEvent.changeText(emailInput, "priya@clinic.thali.dev");
    fireEvent.changeText(inviteInput, "CLINIC-VERIFIED-2026");
    fireEvent.changeText(passwordInput, "ClinicianPass123!");
    fireEvent.changeText(confirmInput, "ClinicianPass123!");
    fireEvent.press(button);

    await waitFor(() => {
      expect(mockSignUp).toHaveBeenCalledWith({
        name: "Dr. Priya Roy",
        email: "priya@clinic.thali.dev",
        password: "ClinicianPass123!",
        role: "doctor",
        invite_code: "CLINIC-VERIFIED-2026",
      });
    });
  });

  it("displays pending verification notice when doctor registers without code", async () => {
    mockSignUp = jest.fn().mockResolvedValue({ user_status: "pending_verification", role: "doctor" });

    render(<SignupScreen />);
    fireEvent.press(screen.getByText("Doctor"));

    const emailInput = screen.getByLabelText(/Email address input/i);
    const passwordInput = screen.getByLabelText(/^Password input$/i);
    const confirmInput = screen.getByLabelText(/Confirm password input/i);
    const button = screen.getByRole("button", { name: /Register & Sign In/i });

    fireEvent.changeText(emailInput, "unverified@clinic.thali.dev");
    fireEvent.changeText(passwordInput, "ClinicianPass123!");
    fireEvent.changeText(confirmInput, "ClinicianPass123!");
    fireEvent.press(button);

    await waitFor(() => {
      expect(screen.getByText(/Verification Pending/i)).toBeTruthy();
      expect(screen.getByText(/Clinician verification is required/i)).toBeTruthy();
    });

    const continueButton = screen.getByRole("button", { name: /Continue to Clinician Portal/i });
    fireEvent.press(continueButton);
    expect(mockRouterReplace).toHaveBeenCalledWith("/(app)/shell");
  });

  it("displays error banner when signUp throws an error", async () => {
    mockSignUp = jest.fn().mockRejectedValue(new Error("Email already registered"));

    render(<SignupScreen />);
    const emailInput = screen.getByLabelText(/Email address input/i);
    const passwordInput = screen.getByLabelText(/^Password input$/i);
    const confirmInput = screen.getByLabelText(/Confirm password input/i);
    const button = screen.getByRole("button", { name: /Register & Sign In/i });

    fireEvent.changeText(emailInput, "existing@thali.dev");
    fireEvent.changeText(passwordInput, "ValidPassword123!");
    fireEvent.changeText(confirmInput, "ValidPassword123!");
    fireEvent.press(button);

    await waitFor(() => {
      expect(screen.getByText(/Email already registered/i)).toBeTruthy();
    });
  });

  it("navigates back to login when Sign In link is pressed", () => {
    render(<SignupScreen />);
    const signInButton = screen.getByRole("button", { name: /Already have an account\? Sign In/i });
    fireEvent.press(signInButton);
    expect(mockRouterPush).toHaveBeenCalledWith("/(auth)/login");
  });
});
