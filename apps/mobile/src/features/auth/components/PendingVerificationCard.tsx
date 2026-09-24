import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing, typography } from "../../../theming/tokens";

export type PendingVerificationCardProps = {
  role?: string;
};

export function PendingVerificationCard({ role = "doctor" }: PendingVerificationCardProps) {
  return (
    <View style={styles.card} accessibilityRole="alert">
      <View style={styles.badgeRow}>
        <Text style={styles.badge} allowFontScaling>
          CLINICAL VERIFICATION REQUIRED
        </Text>
      </View>
      <Text style={styles.title} allowFontScaling>
        Account created
      </Text>
      <Text style={styles.body} allowFontScaling>
        Clinician verification is required before active clinical review is unlocked. A health facility administrator will review your medical credentials before clinical review access is enabled.
      </Text>
      <View style={styles.noticeBox}>
        <Text style={styles.noticeText} allowFontScaling>
          You may sign in to access your profile settings. Clinical operations and patient management will activate upon verification.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: radii.md,
    borderWidth: 1.5,
    borderColor: "#BCE0EB",
    padding: spacing.md,
    gap: spacing.xs,
  },
  badgeRow: {
    alignSelf: "flex-start",
  },
  badge: {
    backgroundColor: "#E0F2F7",
    color: colors.primary,
    fontSize: 10,
    fontWeight: "700",
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    borderRadius: radii.sm,
    letterSpacing: 0.5,
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  body: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  noticeBox: {
    marginTop: spacing.xs,
    backgroundColor: "#F8F9FA",
    padding: spacing.sm,
    borderRadius: radii.sm,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
  },
  noticeText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
});
