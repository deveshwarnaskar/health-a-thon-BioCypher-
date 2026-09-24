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
  /** Optional element rendered inside the field's trailing edge (e.g. a mic button). */
  trailing?: React.ReactNode;
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
  trailing,
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
      <View
        style={[
          styles.field,
          error ? styles.fieldError : null,
          disabled ? styles.fieldDisabled : null,
        ]}
      >
        <RNTextInput
          value={value}
          onChangeText={onChangeText}
          style={[styles.input, disabled ? styles.inputDisabled : null]}
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
        {trailing ? <View style={styles.trailing}>{trailing}</View> : null}
      </View>
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
    fontWeight: "800",
    color: colors.textPrimary,
  },
  field: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.06,
    shadowRadius: 14,
    elevation: 2,
  },
  fieldError: {
    borderColor: colors.critical,
  },
  fieldDisabled: {
    backgroundColor: colors.background,
  },
  input: {
    flex: 1,
    minHeight: 48,
    paddingHorizontal: spacing.md,
    color: colors.textPrimary,
    fontSize: typography.fontSize.body,
  },
  inputDisabled: {
    color: colors.disabled,
  },
  trailing: {
    paddingRight: spacing.xs,
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