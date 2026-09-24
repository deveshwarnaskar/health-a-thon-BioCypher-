export const doctorPalette = {
  appBackground: "#F5F7FA",
  surface: "#FFFFFF",
  surfaceSoft: "#F8FAFC",
  surfaceBlue: "#EFF6FF",
  surfaceLime: "#D8F872",
  limeSoft: "#EEFCD4",
  limeBorder: "#C7F153",
  primary: "#1E60FF",
  primaryPressed: "#124DD4",
  primaryGradientEnd: "#3B82F6",
  accentAmber: "#F59E0B",
  accentEmerald: "#10B981",
  ink: "#0F172A",
  inkSecondary: "#334155",
  muted: "#64748B",
  quiet: "#94A3B8",
  border: "#E2E8F0",
  borderSubtle: "#EEF2F6",
  warm: "#FFFBEB",
  criticalSoft: "#FEF2F2",
  criticalText: "#EF4444",
} as const;

export const doctorRadii = {
  xs: 8,
  sm: 12,
  md: 18,
  lg: 24,
  xl: 30,
  pill: 999,
} as const;

export const doctorShadow = {
  shadowColor: "#0F172A",
  shadowOffset: { width: 0, height: 10 },
  shadowOpacity: 0.06,
  shadowRadius: 20,
  elevation: 3,
} as const;

export const doctorSoftShadow = {
  shadowColor: "#0F172A",
  shadowOffset: { width: 0, height: 4 },
  shadowOpacity: 0.04,
  shadowRadius: 12,
  elevation: 2,
} as const;

export const doctorPillShadow = {
  shadowColor: "#1E60FF",
  shadowOffset: { width: 0, height: 6 },
  shadowOpacity: 0.22,
  shadowRadius: 14,
  elevation: 4,
} as const;
