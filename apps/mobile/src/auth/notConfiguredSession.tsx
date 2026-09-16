import React, { createContext, useContext, useMemo } from "react";

/**
 * When EXPO_PUBLIC_AUTH_ENABLED=false the app presents a clear, safe screen
 * announcing that authentication is not available.  No fake login, no skip
 * button, no demo token path (Gate 10C §Development Auth).
 */

type NotConfiguredController = {
  isBootstrapping: false;
  isUnauthenticated: true;
  isAuthenticated: false;
  authEnabled: false;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
};

const NotConfiguredContext = createContext<NotConfiguredController>({
  isBootstrapping: false,
  isUnauthenticated: true,
  isAuthenticated: false,
  authEnabled: false,
  signIn: () => Promise.resolve(),
  signOut: () => Promise.resolve(),
});

export function NotConfiguredSessionProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const value = useMemo<NotConfiguredController>(
    () => ({
      isBootstrapping: false,
      isUnauthenticated: true,
      isAuthenticated: false,
      authEnabled: false,
      signIn: async () => {},
      signOut: async () => {},
    }),
    []
  );

  return (
    <NotConfiguredContext.Provider value={value}>
      {children}
    </NotConfiguredContext.Provider>
  );
}

export function useNotConfiguredAuth(): NotConfiguredController {
  return useContext(NotConfiguredContext);
}
