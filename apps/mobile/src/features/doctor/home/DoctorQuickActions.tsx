import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "../doctorDesign";
import { SectionHeader } from "./DoctorHomeBits";

export interface QuickAction {
  key: string;
  label: string;
  subLabel?: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
  onPress: () => void;
  badges?: number;
}

export function DoctorQuickActions({ actions }: { actions: QuickAction[] }) {
  return (
    <View style={styles.section}>
      <SectionHeader title="Clinical Workspace Quick Actions" />
      <View style={styles.grid}>
        {actions.map((action) => (
          <Pressable
            key={action.key}
            style={({ pressed }) => [styles.tile, pressed && styles.tilePressed]}
            onPress={action.onPress}
            accessibilityRole="button"
            accessibilityLabel={`${action.label}${action.subLabel ? `, ${action.subLabel}` : ""}`}
          >
            <View style={styles.topRow}>
              <View style={styles.iconWrap}>
                <Ionicons name={action.icon} size={18} color={doctorPalette.primary} />
              </View>
              {action.badges && action.badges > 0 ? (
                <View style={styles.badge} accessible={false}>
                  <Text style={styles.badgeText} allowFontScaling>
                    {action.badges}
                  </Text>
                </View>
              ) : null}
            </View>
            <View style={styles.labelCol}>
              <Text style={styles.tileLabel} allowFontScaling numberOfLines={1}>
                {action.label}
              </Text>
              {action.subLabel ? (
                <Text style={styles.tileSubLabel} allowFontScaling numberOfLines={1}>
                  {action.subLabel}
                </Text>
              ) : null}
            </View>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: 12,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  tile: {
    flexGrow: 1,
    flexBasis: "47%",
    minWidth: 140,
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 14,
    gap: 10,
    ...doctorSoftShadow,
  },
  tilePressed: {
    opacity: 0.86,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  iconWrap: {
    width: 36,
    height: 36,
    borderRadius: 12,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  badge: {
    minWidth: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: doctorPalette.primary,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 6,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  labelCol: {
    gap: 2,
  },
  tileLabel: {
    fontSize: 13,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.2,
  },
  tileSubLabel: {
    fontSize: 11,
    fontWeight: "500",
    color: doctorPalette.muted,
  },
});