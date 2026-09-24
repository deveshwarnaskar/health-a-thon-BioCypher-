import React from "react";
import { useRouter } from "expo-router";
import { DietitianWorkflow } from "../../src/features/meals";

/**
 * Dedicated route for the Dietitian Meal & Nutrition workflow (Gate 10H-M).
 * Accessible within the protected (app) layout when authenticated.
 */
export default function DietitianRoute() {
  const router = useRouter();

  return (
    <DietitianWorkflow
      flow="food"
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
