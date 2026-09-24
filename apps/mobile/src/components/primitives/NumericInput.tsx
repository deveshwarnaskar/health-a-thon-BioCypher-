import React from "react";
import { TextInput, TextInputProps } from "./TextInput";

export type NumericInputProps = {
  label?: string;
  value: string;
  onChangeText: (value: string) => void;
  error?: string | null;
  hint?: string;
  disabled?: boolean;
  /** Strip non-numeric characters before forwarding the value. */
  numericOnly?: boolean;
  /** Optional element rendered inside the field's trailing edge (e.g. a mic button). */
  trailing?: React.ReactNode;
  accessibilityHint?: string;
};

const NON_NUMERIC = /[^0-9]/g;

export function NumericInput({
  numericOnly = true,
  onChangeText,
  trailing,
  ...rest
}: NumericInputProps) {
  const handleChange = (raw: string) => {
    if (numericOnly) {
      onChangeText(raw.replace(NON_NUMERIC, ""));
      return;
    }
    onChangeText(raw);
  };

  return (
    <TextInput
      {...rest}
      trailing={trailing}
      onChangeText={handleChange}
      keyboardType="number-pad"
      textContentType="none"
    />
  );
}

export type { TextInputProps };