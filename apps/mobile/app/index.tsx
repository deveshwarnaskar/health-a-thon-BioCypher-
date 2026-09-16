import React from "react";
import { router } from "expo-router";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { AppCard } from "../src/components/primitives/AppCard";
import { roleLabel, ROLES, type Role } from "../src/authz/roles";
import { useUiStore } from "../src/store/uiStore";
import { colors, spacing, typography } from "../src/theming/tokens";

/**
 * Gate 10B placeholder entry: choose the shell preview mode. Authentication
 * and automatic role resolution from AuthVerify land in Gate 10C; this screen
 * exercises the role-aware shell without faking an identity.
 */
export default function ModeSelectScreen() {
  const setActiveRoleMode = useUiStore((state) => state.setActiveRoleMode);

  const chooseRole = (role: Role) => {
    setActiveRoleMode(role);
    router.push("/shell");
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title} allowFontScaling>
        THALI x P.L.A.T.E.
      </Text>
      <Text style={styles.subtitle} allowFontScaling>
        Gate 10B foundation — choose a role to preview the role-aware shell.
        Authentication wiring is deferred to Gate 10C.
      </Text>

      <View style={styles.roles}>
        {ROLES.map((role) => (
          <AppCard
            key={role}
            accessibilityLabel={`Preview ${roleLabel(role)} mode`}
            onPress={() => chooseRole(role)}
          >
            <Text style={styles.roleLabel} allowFontScaling>
              {roleLabel(role)}
            </Text>
          </AppCard>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
  },
  title: {
    fontSize: typography.fontSize.display,
    fontWeight: "700",
    color: colors.primary,
  },
  subtitle: {
    fontSize: typography.fontSize.body,
    color: colors.textSecondary,
  },
  roles: {
    gap: spacing.sm,
  },
  roleLabel: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
});