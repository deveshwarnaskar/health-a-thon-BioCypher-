import React from "react";
import { Redirect, Stack } from "expo-router";
import { useAuth } from "../../src/auth/AuthProvider";

/**
 * Routes in the (auth) group are reached when a session has not been
 * established. When an authenticated session is active, redirects to
 * the protected application shell.
 */
export default function AuthLayout() {
  const { state } = useAuth();

  if (state.name === "authenticated") {
    return <Redirect href="/(app)/shell" />;
  }

  if (state.name === "access_denied" || state.name === "deactivated") {
    return <Redirect href="/(app)/access-denied" />;
  }

  return <Stack screenOptions={{ headerShown: false }} />;
}