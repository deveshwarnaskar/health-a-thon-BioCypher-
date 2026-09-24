import React from "react";
import { useRouter } from "expo-router";
import { PatientGlucoseScreen } from "../../src/features/glucose";

/**
 * Dedicated route for the Patient Blood Glucose workflow (Gate 10D).
 * Accessible within the protected (app) layout when authenticated.
 */
export default function GlucoseScreen() {
  const router = useRouter();

  return (
    <PatientGlucoseScreen
      onBack={() => {
        if (router.canGoBack()) {
          router.back();
        } else {
          router.replace("/(app)/shell");
        }
      }}
    />
  );
}
