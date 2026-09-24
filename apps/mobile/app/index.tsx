import React from "react";
import { Redirect } from "expo-router";
import { LoadingState } from "../src/components/primitives/LoadingState";
import { useAuth } from "../src/auth/AuthProvider";
import { readApiConfig } from "../src/services/api/config";

const apiConfig = readApiConfig();

/**
 * Root route.  Redirects to the appropriate area based on the current
 * authentication state, or holds a loading screen during bootstrap to
 * prevent unauthenticated protected views from flashing.
 */
export default function RootIndex() {
  if (!apiConfig.authEnabled) {
    return <Redirect href="/(auth)/not-configured" />;
  }

  return <AuthDrivenIndex />;
}

function AuthDrivenIndex() {
  const { state } = useAuth();

  switch (state.name) {
    case "unknown":
    case "bootstrapping":
      return <LoadingState label="Preparing application…" />;

    case "authenticating":
      return <LoadingState label="Signing in…" />;

    case "authenticated":
      return <Redirect href="/(app)/shell" />;

    case "session_expired":
    case "failed":
    case "unauthenticated":
      return <Redirect href="/(auth)/login" />;

    case "access_denied":
    case "deactivated":
      return <Redirect href="/access-denied" />;

    case "session_expiring":
    case "refreshing":
      return <LoadingState label="Restoring session…" />;

    default:
      return <LoadingState label="Preparing application…" />;
  }
}