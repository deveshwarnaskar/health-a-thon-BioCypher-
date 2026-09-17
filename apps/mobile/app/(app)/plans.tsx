import React from "react";
import { useRouter } from "expo-router";
import { DoctorWorkflow } from "../../src/features/doctor";

/**
 * Dedicated route for the Doctor medication-plan views (Gate 10F-M).
 * Accessible within the protected (app) layout when authenticated; the
 * DoctorWorkflow screens re-check the Doctor role and reject non-Doctor
 * principals.
 */
export default function DoctorPlansScreen() {
  const router = useRouter();

  return (
    <DoctorWorkflow
      flow="plans"
      onHome={() => {
        if (router.canGoBack()) {
          router.back();
        } else {
          router.replace("/(app)/shell");
        }
      }}
    />
  );
}