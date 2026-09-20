import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import WelcomeScreen from "../../app/(auth)/welcome";

const mockRouterPush = jest.fn();

jest.mock("expo-router", () => ({
  useRouter: () => ({
    push: mockRouterPush,
  }),
}));

describe("WelcomeScreen (component-level UX & navigation)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders THALI brand mark, tagline, and clinical pillars", () => {
    render(<WelcomeScreen />);
    expect(screen.getByText(/^THALI × P\.L\.A\.T\.E\.$/i)).toBeTruthy();
    expect(screen.getByText("Care, connected.")).toBeTruthy();
    expect(screen.getByText(/Unified healthcare platform/i)).toBeTruthy();
    expect(screen.getByText(/Patient self-service glycemic and meal logging/i)).toBeTruthy();
    expect(screen.getByText(/Caregiver delegated monitoring/i)).toBeTruthy();
    expect(screen.getByText(/Verified clinician review/i)).toBeTruthy();
  });

  it("navigates to Sign In screen when Sign in button is pressed", () => {
    render(<WelcomeScreen />);
    const signInButton = screen.getByRole("button", { name: /Sign in/i });
    fireEvent.press(signInButton);
    expect(mockRouterPush).toHaveBeenCalledWith("/(auth)/login");
  });

  it("navigates to Sign Up screen when Create account button is pressed", () => {
    render(<WelcomeScreen />);
    const createAccountButton = screen.getByRole("button", { name: /Create account/i });
    fireEvent.press(createAccountButton);
    expect(mockRouterPush).toHaveBeenCalledWith("/(auth)/signup");
  });

  it("renders the THALI security controls footer", () => {
    render(<WelcomeScreen />);
    expect(screen.getByText(/Your information is protected by THALI × P\.L\.A\.T\.E\. security controls/i)).toBeTruthy();
  });
});
