/**
 * Design tokens — single source of truth for the mobile design system.
 *
 * Frozen across the THALI x P.L.A.T.E. production program (Gate 10A §14).
 * Components consume these tokens and NEVER hard-code colors, spacing, or
 * type measures.
 */

export const colors = {
  /** Primary Clinical — Deep Teal */
  primary: "#0D5C75",
  /** Assistive — Warm Saffron */
  assistive: "#E67E22",
  /** Assistive complement — Leaf Green */
  leafGreen: "#27AE60",
  /** Semantic — Critical Red */
  critical: "#E74C3C",
  /** Semantic — Warning Amber */
  warning: "#F39C12",
  /** Semantic — Info Blue */
  info: "#2980B9",
  /** Backgrounds — Clean Off-White */
  background: "#F8F9FA",
  /** Backgrounds — Dark Surface */
  darkSurface: "#1A1A1A",

  surface: "#FFFFFF",
  surfaceSoft: "#F7FEFF",
  primaryInk: "#101832",
  textPrimary: "#1A1A1A",
  textSecondary: "#5B6B73",
  textOnPrimary: "#FFFFFF",
  textOnAssistive: "#FFFFFF",
  textOnDark: "#FFFFFF",
  border: "#DCE3E6",
  overlay: "#00000088",
  disabled: "#C3CDD1",
  backgroundRaised: "#F7FAFC",
  tileBlue: "#3B82F6",
  tileYellow: "#FFF8D8",
  tileGreen: "#EAFBF1",
  tilePink: "#FFF0F1",
  tileLavender: "#F7F0FF",
  tileAqua: "#DDF8F6",
  tileCream: "#FFF8E7",
  error: "#E74C3C",
} as const;

export type ColorTokens = typeof colors;

/**
 * 4px baseline grid. Components must use these steps only.
 */
export const spacing = {
  xxs: 4,
  xs: 8,
  sm: 12,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

export type SpacingTokens = typeof spacing;

/**
 * Responsive system-font scale (San Francisco on iOS, Roboto on Android).
 * All text renders with allowFontScaling enabled to honour OS text size.
 */
export const typography = {
  fontSize: {
    caption: 12,
    body: 16,
    bodySmall: 14,
    title: 20,
    headline: 24,
    display: 32,
  },
  lineHeight: {
    caption: 16,
    body: 22,
    bodySmall: 20,
    title: 26,
    headline: 30,
    display: 38,
  },
  weight: {
    regular: "400",
    medium: "500",
    semibold: "600",
    bold: "700",
  },
  caption: {
    fontSize: 12,
    lineHeight: 16,
    fontWeight: "400" as const,
  },
  bodySmall: {
    fontSize: 14,
    lineHeight: 20,
    fontWeight: "400" as const,
  },
  body: {
    fontSize: 16,
    lineHeight: 22,
    fontWeight: "400" as const,
  },
  bodyMedium: {
    fontSize: 16,
    lineHeight: 22,
    fontWeight: "500" as const,
  },
  titleMedium: {
    fontSize: 20,
    lineHeight: 26,
    fontWeight: "600" as const,
  },
  titleLarge: {
    fontSize: 24,
    lineHeight: 30,
    fontWeight: "700" as const,
  },
} as const;

export type TypographyTokens = typeof typography;

export const radii = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 20,
  pill: 999,
} as const;

export const touchTarget = {
  /** Minimum interactive target size (WCAG 2.5.5 / Gate 10A §16.1). */
  min: 48,
  hitSlop: 8,
} as const;

export const tokens = {
  colors,
  spacing,
  typography,
  radii,
  touchTarget,
} as const;

export type AppTokens = typeof tokens;