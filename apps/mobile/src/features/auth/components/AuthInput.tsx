import React, { useRef, useState } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput as RNTextInput,
  type TextInput as RNTextInputRef,
  type TextInputProps as RNTextInputProps,
  View,
} from "react-native";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";

export type AuthInputProps = {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  error?: string | null;
  hint?: string;
  disabled?: boolean;
  keyboardType?: RNTextInputProps["keyboardType"];
  autoCapitalize?: RNTextInputProps["autoCapitalize"];
  autoComplete?: RNTextInputProps["autoComplete"];
  autoCorrect?: boolean;
  spellCheck?: boolean;
  textContentType?: RNTextInputProps["textContentType"];
  returnKeyType?: RNTextInputProps["returnKeyType"];
  onSubmitEditing?: RNTextInputProps["onSubmitEditing"];
  blurOnSubmit?: boolean;
  inputRef?: React.RefObject<RNTextInputRef | null>;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  testID?: string;
};

export function AuthInput({
  label,
  value,
  onChangeText,
  placeholder,
  error,
  hint,
  disabled = false,
  keyboardType = "default",
  autoCapitalize = "none",
  autoComplete,
  autoCorrect = false,
  spellCheck = false,
  textContentType,
  returnKeyType,
  onSubmitEditing,
  blurOnSubmit,
  inputRef,
  accessibilityLabel,
  accessibilityHint,
  testID,
}: AuthInputProps) {
  const [isFocused, setIsFocused] = useState(false);
  const internalRef = useRef<RNTextInputRef>(null);
  const resolvedRef = inputRef ?? internalRef;

  const focusInput = () => {
    if (!disabled) {
      resolvedRef.current?.focus();
    }
  };

  return (
    <View style={styles.fieldContainer}>
      <Text style={styles.label} allowFontScaling>
        {label}
      </Text>
      <Pressable
        style={[
          styles.inputContainer,
          isFocused && styles.inputFocused,
          Boolean(error) && styles.inputError,
          disabled && styles.inputDisabled,
        ]}
        onPress={focusInput}
        accessible={false}
      >
        <RNTextInput
          ref={resolvedRef}
          value={value}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor={colors.disabled}
          editable={!disabled}
          keyboardType={keyboardType}
          autoCapitalize={autoCapitalize}
          autoCorrect={autoCorrect}
          spellCheck={spellCheck}
          autoComplete={autoComplete}
          textContentType={textContentType}
          returnKeyType={returnKeyType}
          onSubmitEditing={onSubmitEditing}
          blurOnSubmit={blurOnSubmit}
          selectionColor={colors.primary}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          style={styles.textInput}
          allowFontScaling
          accessibilityLabel={accessibilityLabel ?? label}
          accessibilityHint={accessibilityHint}
          accessibilityState={{ disabled }}
          testID={testID}
        />
      </Pressable>
      {error ? (
        <Text style={styles.errorText} allowFontScaling accessibilityLiveRegion="polite">
          {error}
        </Text>
      ) : hint ? (
        <Text style={styles.hintText} allowFontScaling>
          {hint}
        </Text>
      ) : null}
    </View>
  );
}

export type PasswordInputProps = Omit<AuthInputProps, "keyboardType" | "autoCapitalize"> & {
  showPasswordToggle?: boolean;
};

export function PasswordInput({
  label,
  value,
  onChangeText,
  placeholder = "••••••••",
  error,
  hint,
  disabled = false,
  textContentType = "password",
  returnKeyType,
  onSubmitEditing,
  blurOnSubmit,
  inputRef,
  accessibilityLabel,
  accessibilityHint,
  testID,
}: PasswordInputProps) {
  const [isFocused, setIsFocused] = useState(false);
  const [visible, setVisible] = useState(false);
  const internalRef = useRef<RNTextInputRef>(null);
  const resolvedRef = inputRef ?? internalRef;

  const focusInput = () => {
    if (!disabled) {
      resolvedRef.current?.focus();
    }
  };

  return (
    <View style={styles.fieldContainer}>
      <Text style={styles.label} allowFontScaling>
        {label}
      </Text>
      <Pressable
        style={[
          styles.inputContainer,
          isFocused && styles.inputFocused,
          Boolean(error) && styles.inputError,
          disabled && styles.inputDisabled,
        ]}
        onPress={focusInput}
        accessible={false}
      >
        <RNTextInput
          ref={resolvedRef}
          value={value}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor={colors.disabled}
          editable={!disabled}
          secureTextEntry={!visible}
          autoCapitalize="none"
          autoCorrect={false}
          spellCheck={false}
          autoComplete="password"
          textContentType={textContentType}
          returnKeyType={returnKeyType}
          onSubmitEditing={onSubmitEditing}
          blurOnSubmit={blurOnSubmit}
          selectionColor={colors.primary}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          style={[styles.textInput, styles.passwordTextInput]}
          allowFontScaling
          accessibilityLabel={accessibilityLabel ?? label}
          accessibilityHint={accessibilityHint}
          accessibilityState={{ disabled }}
          testID={testID}
        />
        <Pressable
          onPress={() => setVisible((prev) => !prev)}
          disabled={disabled}
          style={styles.toggleButton}
          accessibilityLabel={visible ? "Hide password" : "Show password"}
          accessibilityHint="Toggles password visibility"
          hitSlop={touchTarget.hitSlop}
        >
          <Text style={styles.toggleText} allowFontScaling>
            {visible ? "Hide" : "Show"}
          </Text>
        </Pressable>
      </Pressable>
      {error ? (
        <Text style={styles.errorText} allowFontScaling accessibilityLiveRegion="polite">
          {error}
        </Text>
      ) : hint ? (
        <Text style={styles.hintText} allowFontScaling>
          {hint}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  fieldContainer: {
    gap: 6,
  },
  label: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  inputContainer: {
    minHeight: 56,
    flexDirection: "row",
    alignItems: "center",
    borderRadius: radii.pill,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
  },
  inputFocused: {
    borderColor: colors.primary,
    backgroundColor: colors.surface,
  },
  inputError: {
    borderColor: colors.critical,
  },
  inputDisabled: {
    backgroundColor: colors.background,
    borderColor: colors.border,
  },
  textInput: {
    flex: 1,
    fontSize: typography.fontSize.body,
    color: colors.textPrimary,
    minHeight: 50,
    paddingVertical: 10,
    paddingHorizontal: 0,
    textAlignVertical: "center",
  },
  passwordTextInput: {
    paddingRight: spacing.xs,
  },
  toggleButton: {
    minWidth: 48,
    minHeight: 48,
    justifyContent: "center",
    alignItems: "flex-end",
    paddingLeft: spacing.xs,
  },
  toggleText: {
    fontSize: typography.fontSize.caption,
    fontWeight: "600",
    color: colors.primary,
  },
  errorText: {
    fontSize: typography.fontSize.caption,
    color: colors.critical,
    fontWeight: "500",
  },
  hintText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
});
