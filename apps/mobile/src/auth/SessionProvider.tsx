import React, { useEffect, useState } from "react";
import { OidcSessionManager } from "./sessionManager";
import { AuthProvider } from "./AuthProvider";
import { apiClient } from "../services/api/client";
import { queryClient } from "../store/query";
import { useUiStore } from "../store/uiStore";
import { readOidcConfig } from "./oidcConfig";
import { discoverOidc } from "./discovery";
import { SecureStoreTokenStore } from "./secureTokenStore";
import { createOidcFlow } from "./oidcFlow";
import { globalAuthExpiredSignal } from "./globalAuthSignal";
import { LoadingState } from "../components/primitives/LoadingState";
import { ErrorState } from "../components/primitives/ErrorState";

/**
 * Composes the real OidcSessionManager, fetches OIDC discovery on mount, and
 * renders the application shell once the session is ready.  While the session
 * is restoring the user sees a loading screen — never an unauthenticated
 * protected route.  Discovery/configuration failures surface a clear safe
 * error instead of an indefinite spinner.
 */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [manager, setManager] = useState<OidcSessionManager | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const oidcConfig = readOidcConfig();
      const discovery = await discoverOidc(oidcConfig.issuerUrl);

      const newManager = new OidcSessionManager({
        config: oidcConfig,
        discovery,
        tokenStore: new SecureStoreTokenStore(),
        oidcFlow: createOidcFlow(),
        apiClient,
        onAuthExpiredSignal: globalAuthExpiredSignal,
        onProtectedStateInvalidated: () => {
          queryClient.clear();
          useUiStore.getState().reset();
        },
      });

      apiClient.setAuthProvider(newManager);

      if (!cancelled) setManager(newManager);
    })().catch((err) => {
      console.warn("[session] Discovery failed:", err);
      if (!cancelled) setFailure("Authentication is unavailable right now.");
    });

    return () => {
      cancelled = true;
    };
  }, []);

  if (failure) {
    return <ErrorState title="Unable to complete sign-in" message={failure} />;
  }

  if (!manager) {
    return <LoadingState label="Establishing session…" />;
  }

  return <AuthProvider sessionManager={manager}>{children}</AuthProvider>;
}