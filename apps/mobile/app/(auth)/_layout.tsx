import React from "react";
import { Stack } from "expo-router";

/**
 * Routes in the (auth) group are reached when a session has not been
 * established.  Root routing (app/index.tsx) decides which group renders;
 * guards here only protect against direct deep links into the group.
 */
export default function AuthLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}