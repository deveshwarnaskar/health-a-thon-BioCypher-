import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { colors, radii, spacing, typography } from "../../src/theming/tokens";
import {
  AuthButton,
  AuthFooter,
  AuthHeader,
  AuthPanel,
  AuthScreen,
} from "../../src/features/auth";

/**
 * THALI Welcome Landing Screen
 * Clean, calm entry point into the clinical & patient experience.
 */
export default function WelcomeScreen() {
  const router = useRouter();

  return (
    <AuthScreen>
      <AuthHeader
        title="Care, connected."
        subtitle="Unified healthcare platform — patient and caregiver health logging with THALI, clinician review with P.L.A.T.E."
      />

      <AuthPanel>
        <View style={styles.pillarSection}>
          <View style={styles.pillarRow}>
            <View style={styles.pillarDot} />
            <Text style={styles.pillarText} allowFontScaling>
              Patient self-service glycemic and meal logging
            </Text>
          </View>
          <View style={styles.pillarRow}>
            <View style={styles.pillarDot} />
            <Text style={styles.pillarText} allowFontScaling>
              Caregiver delegated monitoring &amp; family support
            </Text>
          </View>
          <View style={styles.pillarRow}>
            <View style={styles.pillarDot} />
            <Text style={styles.pillarText} allowFontScaling>
              Verified clinician review &amp; intervention workflow
            </Text>
          </View>
        </View>

        <View style={styles.actionSection}>
          <AuthButton
            label="Sign in"
            onPress={() => router.replace("/(auth)/login")}
            accessibilityHint="Navigates to the sign in screen."
          />

          <AuthButton
            label="Create account"
            variant="outline"
            onPress={() => router.replace("/(auth)/signup")}
            accessibilityHint="Navigates to the account registration screen."
          />
        </View>

        <AuthFooter />
      </AuthPanel>
    </AuthScreen>
  );
}

const styles = StyleSheet.create({
  pillarSection: {
    backgroundColor: "#F4F7F8",
    padding: spacing.md,
    borderRadius: radii.lg,
    gap: spacing.sm,
  },
  pillarRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  pillarDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.primary,
  },
  pillarText: {
    fontSize: typography.fontSize.caption,
    color: colors.textPrimary,
    fontWeight: "500",
  },
  actionSection: {
    gap: spacing.sm,
  },
});
