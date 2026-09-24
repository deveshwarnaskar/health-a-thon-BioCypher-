import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, typography } from "../../theming/tokens";
import type { PermissionState, PermissionType } from "../../services/permissions/types";

export interface PermissionBannerProps {
  state: PermissionState;
  onPress: () => void;
}

export function PermissionBanner({ state, onPress }: PermissionBannerProps) {
  const missing: PermissionType[] = [];
  if (state.notifications !== "granted") missing.push("notifications");
  if (state.microphone !== "granted") missing.push("microphone");
  if (state.camera !== "granted") missing.push("camera");

  if (missing.length === 0) return null;

  const missingLabels = missing
    .map((m) => m.charAt(0).toUpperCase() + m.slice(1))
    .join(", ");

  return (
    <TouchableOpacity
      style={styles.banner}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`Permissions disabled: ${missingLabels}. Tap to enable.`}
    >
      <View style={styles.iconContainer}>
        <Ionicons name="warning-outline" size={18} color="#92400E" />
      </View>
      <View style={styles.textContainer}>
        <Text style={styles.title}>Permissions Required</Text>
        <Text style={styles.subtitle} numberOfLines={1}>
          {missingLabels} turned off. Tap to grant access.
        </Text>
      </View>
      <Ionicons name="chevron-forward" size={16} color="#92400E" />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  banner: {
    backgroundColor: "#FEF3C7",
    borderBottomWidth: 1,
    borderBottomColor: "#FDE68A",
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  iconContainer: {
    marginRight: spacing.xs,
  },
  textContainer: {
    flex: 1,
  },
  title: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: "#92400E",
  },
  subtitle: {
    fontSize: 11,
    color: "#B45309",
  },
});
