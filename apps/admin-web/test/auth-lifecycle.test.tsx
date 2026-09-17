import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "./setup";
import { tokenStorage } from "../src/auth/tokenStorage";
import { AuthProvider } from "../src/auth/context";
import { AdminRoute } from "../src/auth/AdminRoute";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { createPkcePair, PKCE_RFC7636_TEST_VECTOR } from "../src/auth/pkce";
import { buildAuthorizeUrl, buildLogoutUrl } from "../src/auth/oidc";

describe("Authentication & Authorization Lifecycle", () => {
  beforeEach(() => {
    tokenStorage.clearTokens();
  });

  describe("PKCE RFC 7636 & OIDC URL Builder", () => {
    it("generates 43-character base64url PKCE verifier and challenge", async () => {
      const pair = await createPkcePair();
      expect(pair.codeVerifier.length).toBe(43);
      expect(pair.codeChallenge.length).toBe(43);
      expect(pair.codeVerifier).toMatch(/^[A-Za-z0-9\-_]+$/);
      expect(pair.codeChallenge).toMatch(/^[A-Za-z0-9\-_]+$/);
    });

    it("matches RFC 7636 test vector constants", () => {
      expect(PKCE_RFC7636_TEST_VECTOR.verifier).toBe(
        "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
      );
      expect(PKCE_RFC7636_TEST_VECTOR.challenge).toBe(
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
      );
    });

    it("builds valid authorization URL containing PKCE challenge and state", async () => {
      const urlString = await buildAuthorizeUrl();
      const url = new URL(urlString);
      expect(url.pathname).toContain("/protocol/openid-connect/auth");
      expect(url.searchParams.get("client_id")).toBe("thali-admin-web");
      expect(url.searchParams.get("response_type")).toBe("code");
      expect(url.searchParams.get("code_challenge_method")).toBe("S256");
      expect(url.searchParams.get("code_challenge")).toBeTruthy();
      expect(url.searchParams.get("state")).toBeTruthy();
    });

    it("builds valid logout URL pointing to post_logout_redirect_uri", () => {
      const urlString = buildLogoutUrl();
      const url = new URL(urlString);
      expect(url.pathname).toContain("/protocol/openid-connect/logout");
      expect(url.searchParams.get("client_id")).toBe("thali-admin-web");
      expect(url.searchParams.get("post_logout_redirect_uri")).toContain("/login");
    });
  });

  describe("Token Storage Lifecycle", () => {
    it("manages access and refresh tokens correctly", () => {
      expect(tokenStorage.hasTokens()).toBe(false);
      expect(tokenStorage.getAccessToken()).toBeNull();

      const futureTime = Date.now() + 60_000;
      tokenStorage.setTokens({
        accessToken: "access-123",
        refreshToken: "refresh-456",
        expiresAt: futureTime,
      });

      expect(tokenStorage.hasTokens()).toBe(true);
      expect(tokenStorage.getAccessToken()).toBe("access-123");
      expect(tokenStorage.getRefreshToken()).toBe("refresh-456");
      expect(tokenStorage.getExpiresAt()).toBe(futureTime);
      expect(tokenStorage.isExpired()).toBe(false);

      // Expired token test
      tokenStorage.setTokens({
        accessToken: "expired-access",
        expiresAt: Date.now() - 1000,
      });
      expect(tokenStorage.isExpired()).toBe(true);

      tokenStorage.clearTokens();
      expect(tokenStorage.hasTokens()).toBe(false);
      expect(tokenStorage.getAccessToken()).toBeNull();
    });
  });

  describe("Route Guards & Role Scoping", () => {
    it("redirects unauthenticated users to /login", async () => {
      render(
        <MemoryRouter initialEntries={["/dashboard"]}>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<div>Login Screen</div>} />
              <Route
                path="/dashboard"
                element={
                  <AdminRoute>
                    <div>Admin Protected Content</div>
                  </AdminRoute>
                }
              />
            </Routes>
          </AuthProvider>
        </MemoryRouter>,
      );

      await waitFor(() => {
        expect(screen.getByText("Login Screen")).toBeInTheDocument();
      });
      expect(screen.queryByText("Admin Protected Content")).not.toBeInTheDocument();
    });

    it("denies access to non-admin roles (e.g. doctor, nurse, patient) with Operation Denied alert", async () => {
      tokenStorage.setTokens({ accessToken: "clinician-token" });

      server.use(
        http.get("*/api/v2/auth/verify", () => {
          return HttpResponse.json({
            actor_id: "550e8400-e29b-41d4-a716-446655440000",
            tenant_id: "550e8400-e29b-41d4-a716-446655440099",
            roles: ["doctor", "nurse"], // Non-admin!
            facility_id: null,
          });
        }),
      );

      render(
        <MemoryRouter initialEntries={["/dashboard"]}>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<div>Login Screen</div>} />
              <Route
                path="/dashboard"
                element={
                  <AdminRoute>
                    <div>Admin Protected Content</div>
                  </AdminRoute>
                }
              />
            </Routes>
          </AuthProvider>
        </MemoryRouter>,
      );

      await waitFor(() => {
        expect(screen.getByText("Operation Denied")).toBeInTheDocument();
      });

      expect(
        screen.getByText(/strictly restricted to operators holding the/),
      ).toBeInTheDocument();
      expect(screen.queryByText("Admin Protected Content")).not.toBeInTheDocument();
    });

    it("allows access to authenticated admin and binds tenant automatically", async () => {
      tokenStorage.setTokens({ accessToken: "admin-token" });

      server.use(
        http.get("*/api/v2/auth/verify", () => {
          return HttpResponse.json({
            actor_id: "550e8400-e29b-41d4-a716-446655440001",
            tenant_id: "550e8400-e29b-41d4-a716-446655440099",
            roles: ["admin"],
            facility_id: null,
          });
        }),
      );

      render(
        <MemoryRouter initialEntries={["/dashboard"]}>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<div>Login Screen</div>} />
              <Route
                path="/dashboard"
                element={
                  <AdminRoute>
                    <div>Admin Protected Content</div>
                  </AdminRoute>
                }
              />
            </Routes>
          </AuthProvider>
        </MemoryRouter>,
      );

      await waitFor(() => {
        expect(screen.getByText("Admin Protected Content")).toBeInTheDocument();
      });
    });
  });
});
