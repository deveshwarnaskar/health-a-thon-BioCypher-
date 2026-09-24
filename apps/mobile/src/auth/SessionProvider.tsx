import React, { useEffect, useState } from "react";
import { OidcSessionManager } from "./sessionManager";
import { AuthProvider } from "./AuthProvider";
import { apiClient } from "../services/api/client";
import { queryClient } from "../store/query";
import { useUiStore } from "../store/uiStore";
import { readOidcConfig } from "./oidcConfig";
import { discoverOidc, type OidcDiscovery } from "./discovery";
import { readApiConfig } from "../services/api/config";
import { SecureStoreTokenStore } from "./secureTokenStore";
import { createOidcFlow } from "./oidcFlow";
import { globalAuthExpiredSignal } from "./globalAuthSignal";
import { LoadingState } from "../components/primitives/LoadingState";
import { ErrorState } from "../components/primitives/ErrorState";
import { localSessionIsolation } from "../db/isolation";
import { localDatabase } from "../db/database";

/**
 * Composes the real OidcSessionManager, fetches OIDC discovery on mount (or falls back
 * to custom backend JWT auth endpoints), and renders the application shell once the
 * session is ready.
 */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [manager, setManager] = useState<OidcSessionManager | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const oidcConfig = readOidcConfig();
      let discovery: OidcDiscovery;
      try {
        discovery = await discoverOidc(oidcConfig.issuerUrl);
      } catch {
        const baseUrl = readApiConfig().apiBaseUrl || "http://localhost:8000";
        discovery = {
          issuer: baseUrl,
          authorizationEndpoint: `${baseUrl}/api/v2/auth/login`,
          tokenEndpoint: `${baseUrl}/api/v2/auth/refresh`,
        };
      }

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
          if (localDatabase.isOpen()) {
            localSessionIsolation.purgeAllData(localDatabase.getDb()).catch(() => {});
          }
          localSessionIsolation.clearContext();
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