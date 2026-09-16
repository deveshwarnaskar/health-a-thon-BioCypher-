import React from "react";
import { render } from "@testing-library/react-native";
import { Button } from "../../src/components/primitives/Button";

/**
 * Component-level accessibility verification (jest-expo / RNTL). Renders the
 * real Button and asserts the on-screen accessibility contract (Gate 10A
 * §16): role, label, hint, disabled state, and 48dp minimum target.
 */
describe("Button (component-level a11y)", () => {
  it("exposes button role and an accessible name", () => {
    const { getByRole } = render(<Button label="Discover" onPress={() => {}} />);
    const button = getByRole("button");
    expect(button).toBeOnTheScreen();
    expect(button.props.accessibilityRole).toBe("button");
    expect(button.props.accessibilityLabel).toBe("Discover");
  });

  it("announces the hint and disabled state", () => {
    const { getByRole } = render(
      <Button label="Confirm" disabled onPress={() => {}} accessibilityHint="Confirms the selection" />,
    );
    const button = getByRole("button", { disabled: true });
    expect(button.props.accessibilityHint).toBe("Confirms the selection");
    expect(button.props.accessibilityState.disabled).toBe(true);
  });

  it("is at least 48dp tall", () => {
    const { getByRole } = render(<Button label="Go" onPress={() => {}} />);
    const button = getByRole("button");
    expect(button.props.style).toEqual(expect.arrayContaining([{ minHeight: 48, minWidth: 48 }]));
  });
});