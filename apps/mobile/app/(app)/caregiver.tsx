import React from "react";
import { useRouter } from "expo-router";
import { CaregiverWorkflow } from "../../src/features/caregiver";

/**
 * Dedicated route for the Caregiver mobile vertical slice (Gate 10E-M).
 * Accessible within the protected (app) layout when authenticated.
 */
export default function CaregiverScreen() {
  const router = useRouter();

  return (
    <CaregiverWorkflow
      onExit={() => {
        if (router.canGoBack()) {
          router.back();
        } else {
          router.replace("/(app)/shell");
        }
      }}
    />
  );
}