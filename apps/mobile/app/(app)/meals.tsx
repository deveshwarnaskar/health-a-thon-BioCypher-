import React from "react";
import { useRouter } from "expo-router";
import { PatientMealScreen } from "../../src/features/meals";

/**
 * Dedicated route for the Patient Meal & Nutrition workflow (Gate 10H-M).
 * Accessible within the protected (app) layout when authenticated.
 */
export default function MealsRoute() {
  const router = useRouter();

  return (
    <PatientMealScreen
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
