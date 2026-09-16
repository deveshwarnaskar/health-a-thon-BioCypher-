import React, { useEffect } from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { setBackgroundColorAsync } from "expo-system-ui";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "../src/store/query";
import { colors } from "../src/theming/tokens";

SplashScreen.preventAutoHideAsync().catch(() => {
  // Splash hide is deferred until the shell mounts (below).
});

export default function RootLayout() {
  useEffect(() => {
    void setBackgroundColorAsync(colors.background).finally(() => {
      SplashScreen.hideAsync().catch(() => {
        // Non-fatal; the app is usable even if the splash stays visible.
      });
    });
  }, []);

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <Stack screenOptions={{ headerShown: false }} />
        <StatusBar style="dark" />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}