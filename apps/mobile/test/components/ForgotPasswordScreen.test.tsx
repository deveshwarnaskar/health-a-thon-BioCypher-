import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react-native";
import ForgotPasswordScreen from "../../app/(auth)/forgot-password";

let mockForgotPassword = jest.fn();
let mockResetPassword = jest.fn();

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    forgotPassword: mockForgotPassword,
    resetPassword: mockResetPassword,
    isBootstrapping: false,
  }),
}));

const mockRouterPush = jest.fn();

jest.mock("expo-router", () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: jest.fn(),
    back: jest.fn(),
  }),
}));

describe("ForgotPasswordScreen (component-level a11y & workflows)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockForgotPassword = jest.fn().mockResolvedValue({
      status: "ok",
      message: "Reset token dispatched.",
      reset_token: "mock-reset-token-xyz",
    });
    mockResetPassword = jest.fn().mockResolvedValue({
      status: "ok",
      message: "Password updated.",
    });
  });

  it("renders Step 1 with request form elements and step badge", () => {
    render(<ForgotPasswordScreen />);
    expect(screen.getByText(/STEP 1 OF 2/i)).toBeTruthy();
    expect(screen.getByText(/Password Recovery/i)).toBeTruthy();
    expect(screen.getByLabelText(/Email address for password recovery/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Request Reset Token/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /I already have a reset token/i })).toBeTruthy();
  });

  it("validates email before requesting reset token", () => {
    render(<ForgotPasswordScreen />);
    const emailInput = screen.getByLabelText(/Email address for password recovery/i);
    const button = screen.getByRole("button", { name: /Request Reset Token/i });

    fireEvent.changeText(emailInput, "not-valid-email");
    fireEvent.press(button);

    expect(screen.getByText(/Please enter a valid email address/i)).toBeTruthy();
    expect(mockForgotPassword).not.toHaveBeenCalled();
  });

  it("requests reset token and advances to step 2 with auto-populated token", async () => {
    render(<ForgotPasswordScreen />);
    const emailInput = screen.getByLabelText(/Email address for password recovery/i);
    const button = screen.getByRole("button", { name: /Request Reset Token/i });

    fireEvent.changeText(emailInput, "patient@thali.dev");
    fireEvent.press(button);

    await waitFor(() => {
      expect(mockForgotPassword).toHaveBeenCalledWith("patient@thali.dev");
      expect(screen.getByText(/STEP 2 OF 2/i)).toBeTruthy();
      expect(screen.getByDisplayValue("mock-reset-token-xyz")).toBeTruthy();
    });
  });

  it("allows skipping to step 2 with existing token", () => {
    render(<ForgotPasswordScreen />);
    const haveTokenButton = screen.getByRole("button", { name: /I already have a reset token/i });
    fireEvent.press(haveTokenButton);

    expect(screen.getByText(/STEP 2 OF 2/i)).toBeTruthy();
    expect(screen.getByLabelText(/Reset token input/i)).toBeTruthy();
    expect(screen.getByLabelText(/^New password input$/i)).toBeTruthy();
  });

  it("validates passwords on step 2", () => {
    render(<ForgotPasswordScreen />);
    fireEvent.press(screen.getByRole("button", { name: /I already have a reset token/i }));

    const tokenInput = screen.getByLabelText(/Reset token input/i);
    const newPassInput = screen.getByLabelText(/^New password input$/i);
    const confirmPassInput = screen.getByLabelText(/Confirm new password input/i);
    const updateButton = screen.getByRole("button", { name: /Update Password/i });

    // Short password
    fireEvent.changeText(tokenInput, "my-token");
    fireEvent.changeText(newPassInput, "short");
    fireEvent.changeText(confirmPassInput, "short");
    fireEvent.press(updateButton);
    expect(screen.getByText(/New password must be at least 8 characters long/i)).toBeTruthy();

    // Mismatch
    fireEvent.changeText(newPassInput, "ValidPassword123!");
    fireEvent.changeText(confirmPassInput, "DifferentPass123!");
    fireEvent.press(updateButton);
    expect(screen.getByText(/Passwords do not match/i)).toBeTruthy();
  });

  it("submits valid reset password and advances to complete step", async () => {
    render(<ForgotPasswordScreen />);
    fireEvent.press(screen.getByRole("button", { name: /I already have a reset token/i }));

    const tokenInput = screen.getByLabelText(/Reset token input/i);
    const newPassInput = screen.getByLabelText(/^New password input$/i);
    const confirmPassInput = screen.getByLabelText(/Confirm new password input/i);
    const updateButton = screen.getByRole("button", { name: /Update Password/i });

    fireEvent.changeText(tokenInput, "valid-token-123");
    fireEvent.changeText(newPassInput, "NewSecurePassword123!");
    fireEvent.changeText(confirmPassInput, "NewSecurePassword123!");
    fireEvent.press(updateButton);

    await waitFor(() => {
      expect(mockResetPassword).toHaveBeenCalledWith("valid-token-123", "NewSecurePassword123!");
      expect(screen.getByText(/^SUCCESS$/)).toBeTruthy();
      expect(screen.getByText(/Your account password has been updated successfully/i)).toBeTruthy();
    });

    const proceedButton = screen.getByRole("button", { name: /Proceed to Sign In/i });
    fireEvent.press(proceedButton);
    expect(mockRouterPush).toHaveBeenCalledWith("/(auth)/login");
  });

  it("displays error banner when reset fails", async () => {
    mockResetPassword = jest.fn().mockRejectedValue(new Error("Password reset failed. Token may be expired or invalid."));

    render(<ForgotPasswordScreen />);
    fireEvent.press(screen.getByRole("button", { name: /I already have a reset token/i }));

    const tokenInput = screen.getByLabelText(/Reset token input/i);
    const newPassInput = screen.getByLabelText(/^New password input$/i);
    const confirmPassInput = screen.getByLabelText(/Confirm new password input/i);
    const updateButton = screen.getByRole("button", { name: /Update Password/i });

    fireEvent.changeText(tokenInput, "expired-token");
    fireEvent.changeText(newPassInput, "NewSecurePassword123!");
    fireEvent.changeText(confirmPassInput, "NewSecurePassword123!");
    fireEvent.press(updateButton);

    await waitFor(() => {
      expect(screen.getByText(/Token may be expired or invalid/i)).toBeTruthy();
    });
  });

  it("navigates back to sign in when return button is pressed", () => {
    render(<ForgotPasswordScreen />);
    const returnButton = screen.getByRole("button", { name: /Return to Sign In/i });
    fireEvent.press(returnButton);
    expect(mockRouterPush).toHaveBeenCalledWith("/(auth)/login");
  });
});
