/**
 * Permission System Types & Metadata (Gate 10P / WhatsApp & Facebook-grade onboarding)
 *
 * Defines canonical permission types, statuses, and user-facing rationale
 * for Notifications, Microphone, and Camera.
 */

export type PermissionType = "notifications" | "microphone" | "camera";

export type PermissionStatus = "granted" | "denied" | "blocked" | "undetermined";

export type PermissionState = Record<PermissionType, PermissionStatus>;

export interface PermissionMetadata {
  type: PermissionType;
  title: string;
  shortDescription: string;
  detailedRationale: string;
  iconName: string;
  iconColor: string;
  iconBgColor: string;
  darkBgColor: string;
  darkIconColor: string;
}

export const PERMISSION_METADATA: Record<PermissionType, PermissionMetadata> = {
  notifications: {
    type: "notifications",
    title: "Notifications",
    shortDescription: "Medication alerts, glucose warnings, and care plan updates",
    detailedRationale:
      "Stay alerted on vital medication schedules, clinical updates, and urgent glucose readings.",
    iconName: "notifications-outline",
    iconColor: "#0D5C75",
    iconBgColor: "#E0F2FE",
    darkBgColor: "#0F2942",
    darkIconColor: "#38BDF8",
  },
  microphone: {
    type: "microphone",
    title: "Microphone",
    shortDescription: "Voice symptom check-ins and hands-free Thali Assist",
    detailedRationale:
      "Record hands-free symptom check-ins, describe how you feel, and speak with Thali Assist.",
    iconName: "mic-outline",
    iconColor: "#E67E22",
    iconBgColor: "#FEF3C7",
    darkBgColor: "#2D1B0E",
    darkIconColor: "#FB923C",
  },
  camera: {
    type: "camera",
    title: "Camera",
    shortDescription: "Meal plate nutrition analysis and medical document scans",
    detailedRationale:
      "Scan your food plate for automated nutritional analysis and upload medical documents.",
    iconName: "camera-outline",
    iconColor: "#27AE60",
    iconBgColor: "#DCFCE7",
    darkBgColor: "#0D2E1C",
    darkIconColor: "#4ADE80",
  },
};

export const INITIAL_PERMISSION_STATE: PermissionState = {
  notifications: "undetermined",
  microphone: "undetermined",
  camera: "undetermined",
};
