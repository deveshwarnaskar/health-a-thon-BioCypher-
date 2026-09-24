import { describe, expect, it } from "vitest";
import { colors, spacing, radii, typography, touchTarget } from "../../src/theming/tokens";

describe("design tokens (Gate 10A §14)", () => {
  it("exposes the frozen color palette", () => {
    expect(colors.primary).toBe("#0D5C75");
    expect(colors.assistive).toBe("#E67E22");
    expect(colors.leafGreen).toBe("#27AE60");
    expect(colors.critical).toBe("#E74C3C");
    expect(colors.warning).toBe("#F39C12");
    expect(colors.info).toBe("#2980B9");
    expect(colors.background).toBe("#F8F9FA");
    expect(colors.darkSurface).toBe("#1A1A1A");
  });

  it("only allows the 4px-baseline spacing steps", () => {
    expect(new Set(Object.values(spacing))).toEqual(
      new Set([4, 8, 12, 16, 24, 32, 48]),
    );
  });

  it("defines a responsive system-font scale", () => {
    expect(typography.fontSize.display).toBeGreaterThan(typography.fontSize.caption);
    expect(typography.weight.regular).toBeTruthy();
    expect(typography.lineHeight.body).toBeGreaterThan(0);
  });

  it("guarantees the minimum touch target of 48dp", () => {
    expect(touchTarget.min).toBe(48);
    expect(radii.pill).toBeGreaterThan(radii.sm);
  });
});