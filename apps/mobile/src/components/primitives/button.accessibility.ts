import { touchTarget } from "../../theming/tokens";

export type ButtonAccessibilityOptions = {
  label: string;
  hint?: string;
  disabled: boolean;
  busy?: boolean;
};

export type A11yButtonProps = {
  accessible: true;
  accessibilityRole: "button";
  accessibilityLabel: string;
  accessibilityHint?: string;
  accessibilityState: {
    disabled: boolean;
    busy: boolean;
  };
};

/**
 * Resolves the accessibility contract for pressable controls.
 *
 * Kept free of react-native imports so it can be unit-tested in a plain
 * Node environment (Gate 10B a11y contract tests) while remaining the exact
 * props consumed by the component implementations.
 */
export function resolveButtonAccessibilityProps(
  options: ButtonAccessibilityOptions,
): A11yButtonProps {
  return {
    accessible: true,
    accessibilityRole: "button",
    accessibilityLabel: options.label,
    accessibilityHint: options.hint,
    accessibilityState: {
      disabled: options.disabled || Boolean(options.busy),
      busy: options.busy ?? false,
    },
  };
}

/**
 * Guarantees every interactive target meets the minimum 48 x 48 dp touch
 * size (Gate 10A §16.1). Components apply this as their baseline style.
 */
export function touchTargetStyle(minSize: number = touchTarget.min) {
  return { minHeight: minSize, minWidth: minSize };
}