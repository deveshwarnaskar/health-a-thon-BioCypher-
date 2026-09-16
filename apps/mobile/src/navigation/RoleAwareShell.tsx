import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import type { Role } from "../authz/roles";
import { roleLabel } from "../authz/roles";
import { capabilitiesForRole } from "../authz/capabilities";
import { destinationsForRole } from "../authz/navigation";
import { Badge } from "../components/primitives/Badge";
import { AppCard } from "../components/primitives/AppCard";
import { Divider } from "../components/primitives/Divider";
import { colors, spacing, typography } from "../theming/tokens";

/**
 * Role-aware navigation shell (Gate 10A §8). Gate 10B renders the frozen
 * surface-mode skeleton with explicit PLACEHOLDER destinations. No workflow
 * is faked: tapping a destination shows where the vertical slice will land.
 */
export type RoleAwareShellProps = {
  role: Role;
  onDestinationPress: (destinationKey: string) => void;
  testID?: string;
};

export function RoleAwareShell({ role, onDestinationPress }: RoleAwareShellProps) {
  const capabilities = capabilitiesForRole(role);
  const destinations = destinationsForRole(role);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.roleName} allowFontScaling>
        {roleLabel(role)}
      </Text>
      <Text style={styles.caption} allowFontScaling>
        Capabilities (mirrors backend policy; UI composition only)
      </Text>
      <View style={styles.capabilities}>
        {capabilities.map((capability) => (
          <Badge key={capability} label={capability} tone="info" />
        ))}
      </View>

      <Divider label="Placeholder destinations" />

      {destinations.map((destination) => (
        <AppCard
          key={destination.key}
          accessibilityLabel={`${destination.label} (placeholder)`}
          onPress={() => onDestinationPress(destination.key)}
        >
          <Text style={styles.destinationLabel} allowFontScaling>
            {destination.label}
          </Text>
          <Text style={styles.destinationNote} allowFontScaling>
            Workflow mounts in a later vertical slice (Gate 10D-10G).
          </Text>
        </AppCard>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    gap: spacing.md,
  },
  roleName: {
    fontSize: typography.fontSize.headline,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  caption: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
  },
  capabilities: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  destinationLabel: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  destinationNote: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
  },
});