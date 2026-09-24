import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing, typography } from "../../../theming/tokens";

export type RoleOption = "patient" | "caregiver" | "doctor";

export type RoleDefinition = {
  id: RoleOption;
  title: string;
  subtitle: string;
  badge?: string;
};

export const AUTH_ROLES: readonly RoleDefinition[] = [
  {
    id: "patient",
    title: "Patient",
    subtitle: "Manage your own health information and daily care activities.",
  },
  {
    id: "caregiver",
    title: "Caregiver",
    subtitle: "Support a patient who has given you access to their care information.",
  },
  {
    id: "doctor",
    title: "Doctor",
    subtitle: "Access authorized clinical information for patients under your care.",
    badge: "Verification required",
  },
] as const;

export type RoleSelectorProps = {
  selectedRole: string;
  onSelectRole: (role: RoleOption) => void;
  disabled?: boolean;
};

export function RoleSelector({
  selectedRole,
  onSelectRole,
  disabled = false,
}: RoleSelectorProps) {
  return (
    <View style={styles.container} accessibilityRole="radiogroup">
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle} allowFontScaling>
          How will you use THALI × P.L.A.T.E.?
        </Text>
        <Text style={styles.sectionSubtitle} allowFontScaling>
          Choose the account type that applies to you.
        </Text>
      </View>

      <View style={styles.cardsStack}>
        {AUTH_ROLES.map((role) => {
          const isSelected = selectedRole === role.id;
          return (
            <Pressable
              key={role.id}
              onPress={() => onSelectRole(role.id)}
              disabled={disabled}
              accessibilityRole="radio"
              accessibilityState={{ selected: isSelected, disabled }}
              accessibilityLabel={`${role.title}: ${role.subtitle}${role.badge ? ` (${role.badge})` : ""}`}
              style={({ pressed }) => [
                styles.roleCard,
                isSelected && styles.roleCardSelected,
                disabled && styles.roleCardDisabled,
                pressed && !disabled && styles.roleCardPressed,
              ]}
            >
              <View style={styles.radioRow}>
                <View style={[styles.radioCircle, isSelected && styles.radioCircleSelected]}>
                  {isSelected ? <View style={styles.radioInnerDot} /> : null}
                </View>
                <View style={styles.roleTextContainer}>
                  <View style={styles.titleRow}>
                    <Text
                      style={[styles.roleTitle, isSelected && styles.roleTitleSelected]}
                      allowFontScaling
                    >
                      {role.title}
                    </Text>
                    {role.badge ? (
                      <View style={styles.roleBadge}>
                        <Text style={styles.roleBadgeText} allowFontScaling>
                          {role.badge}
                        </Text>
                      </View>
                    ) : null}
                  </View>
                  <Text style={styles.roleSubtitle} allowFontScaling>
                    {role.subtitle}
                  </Text>
                </View>
              </View>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.sm,
  },
  sectionHeader: {
    gap: 4,
  },
  sectionTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  sectionSubtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  cardsStack: {
    gap: spacing.xs,
  },
  roleCard: {
    backgroundColor: "#F8FAFC",
    borderRadius: radii.md,
    borderWidth: 1.5,
    borderColor: "#E2E8F0",
    padding: spacing.md,
  },
  roleCardSelected: {
    borderColor: "#0D5C75",
    backgroundColor: "#F0F8FA",
    shadowColor: "#0D5C75",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 2,
  },
  roleCardDisabled: {
    opacity: 0.6,
  },
  roleCardPressed: {
    opacity: 0.85,
  },
  radioRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
  },
  radioCircle: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: "#CBD5E1",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
    backgroundColor: "#FFFFFF",
  },
  radioCircleSelected: {
    borderColor: "#0D5C75",
  },
  radioInnerDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: "#0D5C75",
  },
  roleTextContainer: {
    flex: 1,
    gap: 4,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  roleTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  roleTitleSelected: {
    color: colors.primary,
    fontWeight: "700",
  },
  roleSubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  roleBadge: {
    backgroundColor: "#FEF3C7",
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: "#FDE68A",
  },
  roleBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#92400E",
    letterSpacing: 0.4,
  },
});
