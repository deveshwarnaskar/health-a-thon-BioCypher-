import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Redirect } from "expo-router";
import { Button } from "../src/components/primitives/Button";
import { useAuth } from "../src/auth/AuthProvider";
import { denialMessage } from "../src/auth/denial";
import { colors, spacing, typography } from "../src/theming/tokens";

/**
 * Safe denial screen for protected areas. 403 ≠ logout: the user stays
 * connected but is told exactly why access is denied (unlinked identity,
 * caregiver revoked/expired, facility mismatch, insufficient capability,
 * deactivated, unknown role). The user can clear the session and sign in again.
 */
export default function AccessDeniedScreen() {
  const { state, signOut } = useAuth();

  if (state.name === "authenticated") {
    return <Redirect href="/(app)/shell" />;
  }

  if (state.name !== "access_denied" && state.name !== "deactivated") {
    return <Redirect href="/(auth)/login" />;
  }

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
        label="Back to sign in"
        variant="outline"
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
