import type {
  ConfirmMealRequest,
  ConfirmMealResponse,
  KatoriVolumeMl,
  LogMealRequest,
  LogMealResponse,
  MealPortionRequest,
} from "../../services/schemas/meals";
import type {
  ClinicianMealObservation,
  PatientMealObservation,
} from "../../services/schemas/clinical";

export type {
  ConfirmMealRequest,
  ConfirmMealResponse,
  KatoriVolumeMl,
  LogMealRequest,
  LogMealResponse,
  MealPortionRequest,
  ClinicianMealObservation,
  PatientMealObservation,
};

export type FoodItem = {
  key: string;
  label: string;
  category?: "grain" | "pulse" | "vegetable" | "dairy" | "breakfast" | "other";
};

export const COMMON_FOODS: readonly FoodItem[] = [
  { key: "rice", label: "Rice (Chawal)", category: "grain" },
  { key: "roti", label: "Roti / Chapati", category: "grain" },
  { key: "dal", label: "Dal (Lentils)", category: "pulse" },
  { key: "sabzi", label: "Cooked Vegetables (Sabzi)", category: "vegetable" },
  { key: "khichdi", label: "Khichdi", category: "grain" },
  { key: "curd", label: "Curd / Dahi", category: "dairy" },
  { key: "idli", label: "Idli", category: "breakfast" },
  { key: "dosa", label: "Dosa", category: "breakfast" },
  { key: "poha", label: "Poha", category: "breakfast" },
  { key: "upma", label: "Upma", category: "breakfast" },
  { key: "salad", label: "Fresh Salad", category: "vegetable" },
  { key: "paneer", label: "Paneer Dish", category: "dairy" },
] as const;

export const mealKeys = {
  all: ["meals"] as const,
  feed: (patientId: string) => ["meals", "feed", patientId] as const,
  clinicianFeed: (patientId: string) => ["meals", "clinicianFeed", patientId] as const,
};
