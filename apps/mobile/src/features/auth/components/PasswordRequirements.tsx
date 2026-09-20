import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, spacing, typography } from "../../../theming/tokens";

export type PasswordRequirementsProps = {
  password?: string;
  confirmPassword?: string;
};

export function PasswordRequirements({
  password = "",
  confirmPassword,
}: PasswordRequirementsProps) {
  const hasLength = password.length >= 8;
  const hasConfirm = confirmPassword !== undefined && confirmPassword.length > 0;
  const matches = hasConfirm && password === confirmPassword;

  return (
    <View style={styles.container} accessibilityRole="summary">
      <Text style={styles.header} allowFontScaling>
        Password security
      </Text>
      <View style={styles.ruleRow}>
        <Text style={[styles.icon, hasLength ? styles.iconMet : styles.iconUnmet]}>
          {hasLength ? "✓" : "○"}
        </Text>
        <Text
          style={[styles.ruleText, hasLength ? styles.ruleTextMet : styles.ruleTextUnmet]}
          allowFontScaling
        >
          At least 8 characters
        </Text>
      </View>
      {confirmPassword !== undefined ? (
        <View style={styles.ruleRow}>
          <Text style={[styles.icon, matches ? styles.iconMet : styles.iconUnmet]}>
            {matches ? "✓" : "○"}
          </Text>
          <Text
            style={[styles.ruleText, matches ? styles.ruleTextMet : styles.ruleTextUnmet]}
            allowFontScaling
          >
            Passwords match
          </Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#F4F7F8",
    padding: spacing.sm,
    borderRadius: 8,
    gap: spacing.xxs,
    borderWidth: 1,
    borderColor: "#E5ECEE",
  },
  header: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: 2,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  ruleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  icon: {
    fontSize: 13,
    fontWeight: "700",
  },
  iconMet: {
    color: colors.leafGreen,
  },
  iconUnmet: {
    color: colors.disabled,
  },
  ruleText: {
    fontSize: typography.fontSize.caption,
  },
  ruleTextMet: {
    color: colors.textPrimary,
    fontWeight: "500",
  },
  ruleTextUnmet: {
    color: colors.textSecondary,
  },
});
