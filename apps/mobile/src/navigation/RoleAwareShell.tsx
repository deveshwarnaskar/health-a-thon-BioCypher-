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
      <View style={styles.hero}>
        <Text style={styles.brandLine} allowFontScaling>
          THALI in
        </Text>
        <Text style={styles.roleName} allowFontScaling>
          {roleLabel(role)}
        </Text>
        <Text style={styles.caption} allowFontScaling>
          Authorized workspace
        </Text>
      </View>

      <View style={styles.metricGrid}>
        <View style={[styles.metricTile, styles.metricTileBlue]}>
          <Text style={styles.metricValue} allowFontScaling>
            {destinations.length}
          </Text>
          <Text style={styles.metricLabel} allowFontScaling>
            Destinations
          </Text>
        </View>
        <View style={[styles.metricTile, styles.metricTileYellow]}>
          <Text style={styles.metricValueDark} allowFontScaling>
            {capabilities.length}
          </Text>
          <Text style={styles.metricLabelDark} allowFontScaling>
            Capabilities
          </Text>
        </View>
      </View>

      <View style={styles.capabilities}>
        {capabilities.map((capability) => (
          <Badge key={capability} label={capability} tone="info" />
        ))}
      </View>

      <Divider label="Destinations" />

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
            Open {destination.label.toLowerCase()} workspace.
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
    paddingBottom: spacing.xxl,
  },
  hero: {
    gap: spacing.xxs,
  },
  brandLine: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: colors.textSecondary,
  },
  roleName: {
    fontSize: typography.fontSize.display,
    lineHeight: typography.lineHeight.display,
    fontWeight: "800",
    color: colors.textPrimary,
  },
  caption: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    fontWeight: "700",
  },
  metricGrid: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  metricTile: {
    flex: 1,
    borderRadius: 12,
    padding: spacing.md,
    minHeight: 104,
    justifyContent: "space-between",
    borderWidth: 1,
    borderColor: "#FFFFFF",
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.08,
    shadowRadius: 18,
    elevation: 3,
  },
  metricTileBlue: {
    backgroundColor: colors.tileBlue,
  },
  metricTileYellow: {
    backgroundColor: colors.tileYellow,
  },
  metricValue: {
    fontSize: typography.fontSize.display,
    lineHeight: typography.lineHeight.display,
    fontWeight: "800",
    color: colors.textOnPrimary,
  },
  metricValueDark: {
    fontSize: typography.fontSize.display,
    lineHeight: typography.lineHeight.display,
    fontWeight: "800",
    color: colors.primaryInk,
  },
  metricLabel: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: colors.textOnPrimary,
  },
  metricLabelDark: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: colors.primaryInk,
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
