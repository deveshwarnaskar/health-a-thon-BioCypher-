/**
 * Caregiver Design Tokens & Scaled Visual Theme
 * Tailored for modern, high-clarity, professional healthcare companion UI.
 */

export const caregiverPalette = {
  // Backgrounds & Surfaces
  appBackground: "#F8FAFC",
  surface: "#FFFFFF",
  surfaceSoft: "#F1F5F9",
  surfaceMuted: "#F8FAFC",
  surfaceTeal: "#F0FDFA",
  surfaceBlue: "#F0F9FF",
  surfaceAmber: "#FFFBEB",
  surfaceEmerald: "#ECFDF5",
  surfacePurple: "#F5F3FF",
  surfaceRose: "#FFF1F2",

  // Clinical Brand: Deep Teal & Forest Emerald
  primary: "#0D5C75",
  primaryHover: "#094457",
  primaryLight: "#E6F4F8",
  primaryBorder: "#BAE6FD",
  tealAccent: "#0D9488",
  tealDark: "#0F766E",
  tealSoft: "#CCFBF1",

  // Semantics & Status Accents
  emerald: "#059669",
  emeraldSoft: "#D1FAE5",
  emeraldDark: "#047857",
  emeraldBorder: "#A7F3D0",

  amber: "#D97706",
  amberSoft: "#FEF3C7",
  amberDark: "#B45309",
  amberBorder: "#FDE68A",

  rose: "#E11D48",
  roseSoft: "#FFE4E6",
  roseDark: "#BE123C",
  roseBorder: "#FECDD3",

  purple: "#7C3AED",
  purpleSoft: "#EDE9FE",
  purpleDark: "#6D28D9",
  purpleBorder: "#DDD6FE",

  sky: "#0284C7",
  skySoft: "#E0F2FE",
  skyBorder: "#BAE6FD",

  // Typography & Inks
  ink: "#0F172A",
  inkSecondary: "#334155",
  muted: "#64748B",
  subtle: "#94A3B8",
  border: "#E2E8F0",
  borderLight: "#F1F5F9",
  borderHighlight: "#CBD5E1",
} as const;

export const caregiverRadii = {
  xs: 6,
  sm: 10,
  md: 14,
  lg: 18,
  xl: 24,
  pill: 999,
} as const;

export const caregiverShadow = {
  subtle: {
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 3,
    elevation: 1,
  },
  card: {
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  elevated: {
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.08,
    shadowRadius: 16,
    elevation: 4,
  },
  modal: {
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.14,
    shadowRadius: 18,
    elevation: 8,
  },
  button: {
    shadowColor: "#0D5C75",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.22,
    shadowRadius: 6,
    elevation: 3,
  },
} as const;
