import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useNotConfiguredAuth } from "../../src/auth/notConfiguredSession";
import { colors, spacing, typography } from "../../src/theming/tokens";

/**
 * Rendered when EXPO_PUBLIC_AUTH_ENABLED=false. Fails loud with NO fake
 * login, NO demo-token path, and no skip button — the device tells the user
 * (and their administrator) that authentication is not configured.
 */
export default function NotConfiguredScreen() {
  useNotConfiguredAuth();

  return (
    <View style={styles.container}>
      <Text style={styles.title} allowFontScaling>
        Authentication is not configured
      </Text>
      <Text style={styles.body} allowFontScaling>
        This build does not have an identity provider wired up yet. No sign-in
        is available, and no protected data can be shown.
      </Text>
      <Text style={styles.note} allowFontScaling>
        To enable authentication, your administrator must set EXPO_PUBLIC_AUTH_ENABLED=true
        and configure the Keycloak issuer, realm, and client as documented in
        the Gate 10C migration notes.
      </Text>
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
  note: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
  },
});