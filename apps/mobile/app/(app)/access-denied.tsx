import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Button } from "../../src/components/primitives/Button";
import { useAuth } from "../../src/auth/AuthProvider";
import { denialMessage } from "../../src/auth/denial";
import { colors, spacing, typography } from "../../src/theming/tokens";

/**
 * Safe denial screen for protected areas. 403 ≠ logout: the user stays
 * connected but is told exactly why access is denied (unlinked identity,
 * caregiver revoked/expired, facility mismatch, insufficient capability,
 * deactivated, unknown role).  Only "Sign out" or "Retry" are offered.
 */
export default function AccessDeniedScreen() {
  const { state, signOut, signIn } = useAuth();

  const reason =
    state.name === "access_denied"
      ? state.reason
      : state.name === "deactivated"
        ? "deactivated"
        : "general";

  return (
    <View style={styles.container}>
      <Text style={styles.title} allowFontScaling>
        Access is limited
      </Text>
      <Text style={styles.body} allowFontScaling>
        {denialMessage(reason)}
      </Text>
      <Button
        label="Try signing in again"
        variant="outline"
        onPress={() => void signIn()}
      />
      <Button
        label="Sign out"
        variant="ghost"
        onPress={() => void signOut()}
        accessibilityHint="Returns to the sign-in screen."
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    padding: spacing.xl,
    gap: spacing.md,
    backgroundColor: colors.background,
  },
  title: {
    fontSize: typography.fontSize.headline,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  body: {
    fontSize: typography.fontSize.body,
    color: colors.textSecondary,
    lineHeight: 22,
  },
});