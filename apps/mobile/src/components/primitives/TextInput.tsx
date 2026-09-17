import React from "react";
import {
  StyleSheet,
  Text,
  TextInput as RNTextInput,
  TextInputProps as RNTextInputProps,
  View,
} from "react-native";
import { colors, radii, spacing, typography } from "../../theming/tokens";

export type TextInputProps = {
  label?: string;
  value: string;
  onChangeText: (value: string) => void;
  error?: string | null;
  hint?: string;
  secureTextEntry?: boolean;
  disabled?: boolean;
  textContentType?: RNTextInputProps["textContentType"];
  keyboardType?: RNTextInputProps["keyboardType"];
  autoCapitalize?: RNTextInputProps["autoCapitalize"];
  placeholder?: string;
  multiline?: boolean;
  numberOfLines?: number;
  testID?: string;
  accessibilityLabel?: string;
  accessibilityHint?: string;
};

export function TextInput({
  label,
  value,
  onChangeText,
  error,
  hint,
  secureTextEntry = false,
  disabled = false,
  textContentType,
  keyboardType,
  autoCapitalize,
  placeholder,
  multiline,
  numberOfLines,
  testID,
  accessibilityLabel,
  accessibilityHint,
}: TextInputProps) {
  return (
    <View style={styles.container}>
      {label ? (
        <Text style={styles.label} allowFontScaling>
          {label}
        </Text>
      ) : null}
      <RNTextInput
        value={value}
        onChangeText={onChangeText}
        style={[styles.input, error ? styles.inputError : null, disabled ? styles.inputDisabled : null]}
        editable={!disabled}
        secureTextEntry={secureTextEntry}
        textContentType={textContentType}
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize}
        placeholder={placeholder}
        placeholderTextColor={colors.disabled}
        multiline={multiline}
        numberOfLines={numberOfLines}
        testID={testID}
        allowFontScaling
        accessibilityLabel={accessibilityLabel ?? label}
        accessibilityHint={accessibilityHint}
        accessibilityState={{ disabled }}
      />
      {error ? (
        <Text style={styles.error} allowFontScaling accessibilityLiveRegion="polite">
          {error}
        </Text>
      ) : hint ? (
        <Text style={styles.hint} allowFontScaling>
          {hint}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.xs,
  },
  label: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "500",
    color: colors.textPrimary,
  },
  input: {
    minHeight: 48,
    paddingHorizontal: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    color: colors.textPrimary,
    fontSize: typography.fontSize.body,
  },
  inputError: {
    borderColor: colors.critical,
  },
  inputDisabled: {
    backgroundColor: colors.background,
    color: colors.disabled,
  },
  error: {
    color: colors.critical,
    fontSize: typography.fontSize.bodySmall,
  },
  hint: {
    color: colors.textSecondary,
    fontSize: typography.fontSize.bodySmall,
  },
});