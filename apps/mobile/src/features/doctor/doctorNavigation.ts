export type DoctorTab = "dashboard" | "patients" | "review" | "tasks" | "workspace";

export type DoctorSubWorkspaceKey =
  | "monitoring"
  | "reports"
  | "plans"
  | "documents"
  | "messages"
  | "audit";

export type DoctorTabItem = {
  key: DoctorTab;
  label: string;
  iconActive: string;
  iconInactive: string;
  accessibilityLabel: string;
};

export const DOCTOR_TABS_CONFIG: DoctorTabItem[] = [
  {
    key: "dashboard",
    label: "Dashboard",
    iconActive: "speedometer",
    iconInactive: "speedometer-outline",
    accessibilityLabel: "Dashboard overview tab",
  },
  {
    key: "patients",
    label: "Patients",
    iconActive: "people",
    iconInactive: "people-outline",
    accessibilityLabel: "Patient directory tab",
  },
  {
    key: "review",
    label: "AI Review",
    iconActive: "flash",
    iconInactive: "flash-outline",
    accessibilityLabel: "Clinical AI review queue",
  },
  {
    key: "tasks",
    label: "Tasks",
    iconActive: "checkbox",
    iconInactive: "checkbox-outline",
    accessibilityLabel: "Care tasks tab",
  },
  {
    key: "workspace",
    label: "Workspace",
    iconActive: "grid",
    iconInactive: "grid-outline",
    accessibilityLabel: "Clinical workspace utilities hub",
  },
];

export function resolveInitialDoctorState(initialFlow?: string | null): {
  tab: DoctorTab;
  sub: DoctorSubWorkspaceKey | null;
} {
  if (!initialFlow || initialFlow === "overview") {
    return { tab: "dashboard", sub: null };
  }
  if (initialFlow === "cohort" || initialFlow === "patients") {
    return { tab: "patients", sub: null };
  }
  if (initialFlow === "review") {
    return { tab: "review", sub: null };
  }
  if (initialFlow === "tasks") {
    return { tab: "tasks", sub: null };
  }
  if (initialFlow === "monitoring") {
    return { tab: "workspace", sub: "monitoring" };
  }
  if (initialFlow === "reports") {
    return { tab: "workspace", sub: "reports" };
  }
  if (initialFlow === "plans") {
    return { tab: "workspace", sub: "plans" };
  }
  if (initialFlow === "documents") {
    return { tab: "workspace", sub: "documents" };
  }
  if (initialFlow === "messages") {
    return { tab: "workspace", sub: "messages" };
  }
  if (initialFlow === "audit") {
    return { tab: "workspace", sub: "audit" };
  }
  return { tab: "dashboard", sub: null };
}

export function getSubWorkspaceTitle(key: DoctorSubWorkspaceKey): string {
  switch (key) {
    case "monitoring":
      return "Longitudinal Monitoring";
    case "reports":
      return "Clinical Reports";
    case "plans":
      return "Medication Plans";
    case "documents":
      return "Document Vault";
    case "messages":
      return "Patient Communications";
    case "audit":
      return "Security & Audit";
  }
}

export function getTabTitle(tab: DoctorTab): string {
  switch (tab) {
    case "dashboard":
      return "Clinical Overview";
    case "patients":
      return "Patient Directory";
    case "review":
      return "AI Review Queue";
    case "tasks":
      return "Care Tasks";
    case "workspace":
      return "Clinical Hub";
  }
}
