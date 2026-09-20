import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { colors, radii, spacing, typography } from "../../src/theming/tokens";
import {
  AuthButton,
  AuthFooter,
  AuthLogo,
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
      <View style={styles.content}>
        <View style={styles.logoSection}>
          <AuthLogo />
        </View>

        <View style={styles.headlineSection}>
          <Text style={styles.tagline} allowFontScaling>
            Care, connected.
          </Text>
          <Text style={styles.description} allowFontScaling>
            Unified healthcare platform — patient and caregiver health logging with THALI, clinician review with P.L.A.T.E.
          </Text>
        </View>

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
            onPress={() => router.push("/(auth)/login")}
            accessibilityHint="Navigates to the sign in screen."
          />

          <AuthButton
            label="Create account"
            variant="outline"
            onPress={() => router.push("/(auth)/signup")}
            accessibilityHint="Navigates to the account registration screen."
          />
        </View>

        <AuthFooter />
      </View>
    </AuthScreen>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: spacing.xl,
    paddingVertical: spacing.md,
  },
  logoSection: {
    alignItems: "flex-start",
  },
  headlineSection: {
    gap: spacing.xs,
  },
  tagline: {
    fontSize: typography.fontSize.display,
    fontWeight: "800",
    color: colors.primary,
    letterSpacing: -0.5,
    lineHeight: 38,
  },
  description: {
    fontSize: typography.fontSize.body,
    color: colors.textSecondary,
    lineHeight: 24,
  },
  pillarSection: {
    backgroundColor: colors.surface,
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
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
