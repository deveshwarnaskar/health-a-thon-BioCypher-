import { describe, expect, it } from "vitest";
import {
  resolveButtonAccessibilityProps,
  touchTargetStyle,
} from "../../src/components/primitives/button.accessibility";
import { touchTarget } from "../../src/theming/tokens";

describe("button accessibility contract (Gate 10A §16)", () => {
  it("declares button role, label and hint", () => {
    const props = resolveButtonAccessibilityProps({
      label: "Save progress",
      hint: "Saves the current readings",
      disabled: false,
    });
    expect(props.accessibilityRole).toBe("button");
    expect(props.accessibilityLabel).toBe("Save progress");
    expect(props.accessibilityHint).toBe("Saves the current readings");
    expect(props.accessible).toBe(true);
  });

  it("announces disabled and busy states", () => {
    const props = resolveButtonAccessibilityProps({
      label: "Confirm",
      disabled: true,
      busy: true,
    });
    expect(props.accessibilityState).toEqual({ disabled: true, busy: true });
  });

  it("enforces a minimum 48x48dp interactive target", () => {
    expect(touchTargetStyle()).toEqual({ minHeight: 48, minWidth: 48 });
    expect(touchTarget.min).toBe(48);
  });

  it("supports custom minimum sizing", () => {
    expect(touchTargetStyle(56)).toEqual({ minHeight: 56, minWidth: 56 });
  });
});