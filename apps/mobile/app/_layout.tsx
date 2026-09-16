import React from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { setBackgroundColorAsync } from "expo-system-ui";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "../src/store/query";
import { colors } from "../src/theming/tokens";
import { SessionProvider } from "../src/auth/SessionProvider";
import { readApiConfig } from "../src/services/api/config";
import { NotConfiguredSessionProvider } from "../src/auth/notConfiguredSession";

SplashScreen.preventAutoHideAsync().catch(() => {});

const apiConfig = readApiConfig();

export default function RootLayout() {
  void setBackgroundColorAsync(colors.background)
    .catch(() => {})
    .finally(() => {
      SplashScreen.hideAsync().catch(() => {});
    });

  const shell = <Stack screenOptions={{ headerShown: false }} />;

  if (!apiConfig.authEnabled) {
    return (
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <NotConfiguredSessionProvider>{shell}</NotConfiguredSessionProvider>
          <StatusBar style="dark" />
        </QueryClientProvider>
      </SafeAreaProvider>
    );
  }

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <SessionProvider>{shell}</SessionProvider>
        <StatusBar style="dark" />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}