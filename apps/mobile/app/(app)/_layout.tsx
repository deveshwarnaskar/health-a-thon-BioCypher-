import React from "react";
import { Redirect, Stack } from "expo-router";
import { useAuth } from "../../src/auth/AuthProvider";
import { LoadingState } from "../../src/components/primitives/LoadingState";

/**
 * Guard for the protected (app) group. Direct deep links into protected
 * routes are redirected to login until an authenticated session exists.
 * Root routing (app/index.tsx) handles the initial session decision.
 */
export default function ProtectedLayout() {
  const { state } = useAuth();

  switch (state.name) {
    case "authenticated":
      return <Stack screenOptions={{ headerShown: false }} />;

    case "access_denied":
    case "deactivated":
      return <Redirect href="/access-denied" />;

    case "unknown":
    case "bootstrapping":
    case "authenticating":
    case "session_expiring":
    case "refreshing":
      return <LoadingState label="Restoring session…" />;

    case "session_expired":
    case "failed":
    case "unauthenticated":
      return <Redirect href="/(auth)/login" />;
  }
}