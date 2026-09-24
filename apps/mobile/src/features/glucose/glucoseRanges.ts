import type { ReadingTag } from "./types";

export type GlycemicCategory = "low" | "target" | "elevated" | "high";

export type GlycemicStatus = {
  label: string;
  category: GlycemicCategory;
  color: string;
  bgColor: string;
  borderColor: string;
  description: string;
};

/**
 * Standard clinical glycemic status evaluation based on ADA & RSSDI guidelines:
 * - Fasting / Pre-meal target: 70–100 mg/dL (or up to 130 for relaxed clinical targets)
 * - Post-meal target: < 140 mg/dL (or up to 180 for clinical diabetes targets)
 * - Hypoglycemia: < 70 mg/dL
 * - Severe Hyperglycemia: >= 200 mg/dL
 */
export function evaluateGlucose(
  value: number | null | undefined,
  tag?: ReadingTag | string | null
): GlycemicStatus {
  if (value === null || value === undefined || isNaN(value)) {
    return {
      label: "Unrecorded",
      category: "target",
      color: "#64748B",
      bgColor: "#F1F5F9",
      borderColor: "#E2E8F0",
      description: "No reading recorded",
    };
  }

  // Hypoglycemia threshold (< 70 mg/dL)
  if (value < 70) {
    return {
      label: "Low",
      category: "low",
      color: "#D97706",
      bgColor: "#FEF3C7",
      borderColor: "#FDE68A",
      description: "Below target range (< 70 mg/dL)",
    };
  }

  const isFastingOrPremeal = tag === "fasting" || tag === "premeal";

  if (isFastingOrPremeal) {
    if (value <= 100) {
      return {
        label: "In Target",
        category: "target",
        color: "#059669",
        bgColor: "#ECFDF5",
        borderColor: "#A7F3D0",
        description: "Optimal fasting reading (70–100 mg/dL)",
      };
    }
    if (value <= 130) {
      return {
        label: "In Target",
        category: "target",
        color: "#059669",
        bgColor: "#ECFDF5",
        borderColor: "#A7F3D0",
        description: "Acceptable fasting target (101–130 mg/dL)",
      };
    }
    if (value < 180) {
      return {
        label: "Elevated",
        category: "elevated",
        color: "#D97706",
        bgColor: "#FFFBEB",
        borderColor: "#FDE68A",
        description: "Above fasting target (131–179 mg/dL)",
      };
    }
    return {
      label: "High",
      category: "high",
      color: "#DC2626",
      bgColor: "#FEF2F2",
      borderColor: "#FECACA",
      description: "Significantly high (≥ 180 mg/dL)",
    };
  }

  // Post-meal or unassigned context
  if (value <= 140) {
    return {
      label: "In Target",
      category: "target",
      color: "#059669",
      bgColor: "#ECFDF5",
      borderColor: "#A7F3D0",
      description: "Within optimal post-meal target (< 140 mg/dL)",
    };
  }
  if (value < 200) {
    return {
      label: "Elevated",
      category: "elevated",
      color: "#D97706",
      bgColor: "#FFFBEB",
      borderColor: "#FDE68A",
      description: "Elevated post-meal reading (141–199 mg/dL)",
    };
  }
  return {
    label: "High",
    category: "high",
    color: "#DC2626",
    bgColor: "#FEF2F2",
    borderColor: "#FECACA",
    description: "High glycemic reading (≥ 200 mg/dL)",
  };
}
