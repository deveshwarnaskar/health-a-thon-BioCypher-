import React from "react";
import { render } from "@testing-library/react-native";
import ProtectedLayout from "../../app/(app)/_layout";

let mockAuthState: { name: string } = { name: "unauthenticated" };

jest.mock("../../src/auth/AuthProvider", () => ({
  useAuth: () => ({ state: mockAuthState }),
}));

const redirectHrefs: string[] = [];
let stackRendered = false;
jest.mock("expo-router", () => ({
  Redirect: ({ href }: { href: string }) => {
    redirectHrefs.push(href);
    return null;
  },
  Stack: () => {
    stackRendered = true;
    return null;
  },
}));

describe("ProtectedLayout guard", () => {
  beforeEach(() => {
    redirectHrefs.length = 0;
    stackRendered = false;
    mockAuthState = { name: "unauthenticated" };
  });

  it("renders protected screens when authenticated", () => {
    mockAuthState = { name: "authenticated" };
    render(<ProtectedLayout />);
    expect(stackRendered).toBe(true);
    expect(redirectHrefs).toHaveLength(0);
  });

  it("redirects to login when unauthenticated", () => {
    mockAuthState = { name: "unauthenticated" };
    render(<ProtectedLayout />);
    expect(redirectHrefs).toContain("/(auth)/login");
  });

  it("redirects to login on session_expired", () => {
    mockAuthState = { name: "session_expired" };
    render(<ProtectedLayout />);
    expect(redirectHrefs).toContain("/(auth)/login");
  });

  it("redirects to access-denied on access_denied", () => {
    mockAuthState = { name: "access_denied" };
    render(<ProtectedLayout />);
    expect(redirectHrefs).toContain("/access-denied");
  });

  it("redirects to access-denied on deactivated", () => {
    mockAuthState = { name: "deactivated" };
    render(<ProtectedLayout />);
    expect(redirectHrefs).toContain("/access-denied");
  });
});