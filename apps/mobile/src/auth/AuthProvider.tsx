import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { AuthSessionProvider } from "./AuthSessionProvider";
import { OidcSessionManager, type StateListener } from "./sessionManager";
import type { AuthFlowState } from "./authStateMachine";

export type AuthController = {
  state: AuthFlowState;
  isBootstrapping: boolean;
  isUnauthenticated: boolean;
  isAuthenticated: boolean;
  signIn: (email?: string, password?: string) => Promise<void>;
  signUp?: (data: {
    email: string;
    password: string;
    name?: string;
    phone?: string;
    role?: string;
  }) => Promise<void>;
  signOut: () => Promise<void>;
  recoverPassword?: () => Promise<void>;
  forgotPassword?: (email: string) => Promise<{ status: string; message: string; reset_token?: string | null }>;
  resetPassword?: (token: string, newPassword: string) => Promise<{ status: string; message: string }>;
  sessionProvider: AuthSessionProvider;
};

const AuthContext = createContext<AuthController | null>(null);

export type AuthProviderProps = {
  sessionManager: OidcSessionManager;
  children: React.ReactNode;
};

export function AuthProvider({ sessionManager, children }: AuthProviderProps) {
  const [state, setState] = useState<AuthFlowState>(sessionManager.getState());

  useEffect(() => {
    const listener: StateListener = (next) => setState(next);
    const unsubscribe = sessionManager.subscribe(listener);
    return unsubscribe;
  }, [sessionManager]);

  useEffect(() => {
    void sessionManager.init();
    return () => {
      // No disposal hook on the manager; listeners are cleaned by React.
    };
  }, [sessionManager]);

  const value = useMemo<AuthController>(
    () => ({
      state,
      isBootstrapping:
        state.name === "unknown" || state.name === "bootstrapping",
      isUnauthenticated:
        state.name === "unauthenticated" ||
        state.name === "session_expired" ||
        state.name === "failed",
      isAuthenticated: state.name === "authenticated",
      signIn: (email?: string, password?: string) => sessionManager.signIn(email, password),
      signUp: (data) => sessionManager.signUp(data),
      signOut: () => sessionManager.signOut(),
      recoverPassword: () => sessionManager.recoverPassword(),
      forgotPassword: (email: string) => sessionManager.forgotPassword(email),
      resetPassword: (token: string, newPassword: string) => sessionManager.resetPassword(token, newPassword),
      sessionProvider: sessionManager,
    }),
    [state, sessionManager]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthController {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}