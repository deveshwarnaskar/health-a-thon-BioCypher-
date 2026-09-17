import React, { useEffect, useState, useCallback } from "react";
import { api, setSessionExpiryHandler } from "../api/client";
import { AuthVerifyResponseSchema, AuthVerifyResponse } from "../contracts";
import { buildAuthorizeUrl, buildLogoutUrl, exchangeCodeForTokens } from "./oidc";
import { tokenStorage } from "./tokenStorage";
import { AuthContext } from "./authContext";

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthVerifyResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const verifySession = useCallback(async () => {
    if (!tokenStorage.hasTokens()) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const data = await api.get("/api/v2/auth/verify", AuthVerifyResponseSchema);
      setUser(data);
    } catch (err) {
      tokenStorage.clearTokens();
      setUser(null);
      setError(err instanceof Error ? err.message : "Authentication verification failed");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async () => {
    try {
      const url = await buildAuthorizeUrl();
      window.location.href = url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to initiate login");
    }
  }, []);

  const logout = useCallback(() => {
    tokenStorage.clearTokens();
    setUser(null);
    try {
      window.location.href = buildLogoutUrl();
    } catch {
      window.location.href = "/login";
    }
  }, []);

  const handleOidcCallback = useCallback(
    async (code: string, state: string) => {
      setIsLoading(true);
      setError(null);
      try {
        const tokens = await exchangeCodeForTokens(code, state);
        tokenStorage.setTokens({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          expiresAt: Date.now() + tokens.expires_in * 1000,
        });
        await verifySession();
      } catch (err) {
        tokenStorage.clearTokens();
        setUser(null);
        setError(err instanceof Error ? err.message : "OIDC code exchange failed");
        setIsLoading(false);
      }
    },
    [verifySession],
  );

  useEffect(() => {
    setSessionExpiryHandler(() => {
      setUser(null);
      setError("Your session has expired. Please log in again.");
    });
    verifySession();
  }, [verifySession]);

  const isAdmin = !!user?.roles.includes("admin");
  const isAuthenticated = !!user;

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isAdmin,
        isLoading,
        error,
        login,
        logout,
        verifySession,
        handleOidcCallback,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
