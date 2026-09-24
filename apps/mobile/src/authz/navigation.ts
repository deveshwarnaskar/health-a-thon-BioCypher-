import type { Role } from "./roles";

/**
 * Role-aware navigation shell composition (Gate 10A §8 mobile surface modes).
 * Destinations are placeholders in Gate 10B; real workflows mount in 10D-10G.
 */
export type RoleDestination = {
  key: string;
  label: string;
};

/** Placeholder destination sets frozen from the Gate 10A surface-mode matrix. */
export const ROLE_DESTINATIONS: Record<Role, readonly RoleDestination[]> = {
  Patient: [
    { key: "home", label: "Home" },
    { key: "glucose", label: "Glucose" },
    { key: "food", label: "Food" },
    { key: "care", label: "Care" },
    { key: "more", label: "More" },
  ],
  Caregiver: [
    { key: "home", label: "Home" },
    { key: "patients", label: "Patients" },
    { key: "verify", label: "Verify" },
    { key: "messages", label: "Messages" },
    { key: "more", label: "More" },
  ],
  Doctor: [
    { key: "home", label: "Home" },
    { key: "review", label: "Review" },
    { key: "patients", label: "Patients" },
    { key: "tasks", label: "Tasks" },
    { key: "more", label: "More" },
  ],
  Nurse: [
    { key: "home", label: "Home" },
    { key: "patients", label: "Patients" },
    { key: "capture", label: "Capture" },
    { key: "tasks", label: "Tasks" },
    { key: "more", label: "More" },
  ],
  CareCoordinator: [
    { key: "queue", label: "Queue" },
    { key: "patients", label: "Patients" },
    { key: "tasks", label: "Tasks" },
    { key: "more", label: "More" },
  ],
  Dietitian: [
    { key: "patients", label: "Patients" },
    { key: "food", label: "Food" },
    { key: "tasks", label: "Tasks" },
    { key: "more", label: "More" },
  ],
  FieldHealthWorker: [
    { key: "visits", label: "Visits" },
    { key: "capture", label: "Capture" },
    { key: "tasks", label: "Tasks" },
    { key: "more", label: "More" },
  ],
};

export function destinationsForRole(role: Role): readonly RoleDestination[] {
  return ROLE_DESTINATIONS[role];
}