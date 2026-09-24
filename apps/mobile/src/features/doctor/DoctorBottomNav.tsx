import React from "react";
import { Platform, StyleSheet, Text, TouchableOpacity, View, type ViewStyle } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { touchTarget } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorShadow, doctorPillShadow } from "./doctorDesign";

export type DoctorTab = "dashboard" | "patients" | "review" | "tasks" | "workspace";

export type DoctorBottomNavProps = {
  currentTab: DoctorTab;
  onSelectTab: (tab: DoctorTab) => void;
  badgeCount?: {
    reviews?: number;
    tasks?: number;
  };
};

export type TabItem = {
  key: DoctorTab;
  label: string;
  iconActive: keyof typeof Ionicons.glyphMap;
  iconInactive: keyof typeof Ionicons.glyphMap;
  accessibilityLabel: string;
};

export const DOCTOR_TABS: TabItem[] = [
  {
    key: "dashboard",
    label: "Home",
    iconActive: "home",
    iconInactive: "home-outline",
    accessibilityLabel: "Clinical dashboard home",
  },
  {
    key: "patients",
    label: "Patients",
    iconActive: "people",
    iconInactive: "people-outline",
    accessibilityLabel: "Patient directory",
  },
  {
    key: "review",
    label: "AI Review",
    iconActive: "sparkles",
    iconInactive: "sparkles-outline",
    accessibilityLabel: "Clinical AI review queue",
  },
  {
    key: "tasks",
    label: "Tasks",
    iconActive: "calendar",
    iconInactive: "calendar-outline",
    accessibilityLabel: "Care tasks and follow-ups",
  },
  {
    key: "workspace",
    label: "Profile",
    iconActive: "person",
    iconInactive: "person-outline",
    accessibilityLabel: "Clinical utilities and profile",
  },
];

function useSafeInsetsFallback() {
  try {
    return useSafeAreaInsets();
  } catch {
    return { top: 0, right: 0, bottom: 0, left: 0 };
  }
}

const glassWebStyle = Platform.select({
  web: {
    backdropFilter: "blur(20px)",
    WebkitBackdropFilter: "blur(20px)",
  } as unknown as ViewStyle,
  default: {},
});

const FADE_STEPS = [
  { height: 8, bg: "rgba(245, 247, 250, 0.02)" },
  { height: 8, bg: "rgba(245, 247, 250, 0.05)" },
  { height: 8, bg: "rgba(245, 247, 250, 0.12)" },
  { height: 10, bg: "rgba(245, 247, 250, 0.22)" },
  { height: 10, bg: "rgba(245, 247, 250, 0.38)" },
  { height: 12, bg: "rgba(245, 247, 250, 0.60)" },
  { height: 14, bg: "rgba(245, 247, 250, 0.85)" },
];

export function DoctorBottomNav({ currentTab, onSelectTab, badgeCount }: DoctorBottomNavProps) {
  const insets = useSafeInsetsFallback();
  const bottomOffset = Math.max(insets.bottom, 12);
  const bottomAreaHeight = bottomOffset + 64 + 36;

  return (
    <View style={[styles.wrapper, { height: bottomAreaHeight }]} pointerEvents="box-none">
      {/* Feathered blur backdrop */}
      <View style={styles.blurBackdropContainer} pointerEvents="none">
        {FADE_STEPS.map((step, idx) => (
          <View
            key={idx}
            style={{
              height: step.height,
              backgroundColor: step.bg,
            }}
          />
        ))}
        <View style={[styles.blurMainBody, glassWebStyle]} />
      </View>

      {/* Floating Pill Navbar */}
      <View
        style={[styles.container, glassWebStyle, { bottom: bottomOffset }]}
        accessibilityRole="tablist"
      >
        {DOCTOR_TABS.map((tab) => {
          const isSelected = currentTab === tab.key;
          const count =
            tab.key === "review"
              ? badgeCount?.reviews
              : tab.key === "tasks"
              ? badgeCount?.tasks
              : undefined;

          return (
            <TouchableOpacity
              key={tab.key}
              style={styles.tab}
              onPress={() => onSelectTab(tab.key)}
              accessibilityRole="tab"
              accessibilityState={{ selected: isSelected }}
              accessibilityLabel={tab.accessibilityLabel}
              activeOpacity={0.7}
            >
              <View style={[styles.iconCircle, isSelected ? styles.activeIconCircle : null]}>
                <Ionicons
                  name={isSelected ? tab.iconActive : tab.iconInactive}
                  size={isSelected ? 20 : 22}
                  color={isSelected ? "#FFFFFF" : doctorPalette.muted}
                />
                {count != null && count > 0 ? (
                  <View
                    style={[
                      styles.badge,
                      tab.key === "review" ? styles.badgeWarning : styles.badgeInfo,
                    ]}
                    accessibilityElementsHidden
                  >
                    <Text style={styles.badgeText} allowFontScaling>
                      {count > 9 ? "9+" : count}
                    </Text>
                  </View>
                ) : null}
              </View>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 1000,
    justifyContent: "flex-end",
    alignItems: "center",
  },
  blurBackdropContainer: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    top: 0,
    flexDirection: "column",
  },
  blurMainBody: {
    flex: 1,
    backgroundColor: "rgba(245, 247, 250, 0.92)",
  },
  container: {
    position: "absolute",
    flexDirection: "row",
    backgroundColor: "rgba(255, 255, 255, 0.96)",
    marginHorizontal: 20,
    borderRadius: doctorRadii.pill,
    paddingVertical: 8,
    paddingHorizontal: 12,
    alignItems: "center",
    justifyContent: "space-between",
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.8)",
    ...doctorShadow,
    maxWidth: 360,
    width: "88%",
  },
  tab: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: touchTarget.min,
  },
  iconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
  },
  activeIconCircle: {
    backgroundColor: doctorPalette.primary,
    ...doctorPillShadow,
  },
  badge: {
    position: "absolute",
    top: 0,
    right: 0,
    minWidth: 16,
    height: 16,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 3,
    borderWidth: 1.5,
    borderColor: doctorPalette.surface,
  },
  badgeWarning: {
    backgroundColor: "#F59E0B",
  },
  badgeInfo: {
    backgroundColor: "#2563EB",
  },
  badgeText: {
    color: "#FFFFFF",
    fontSize: 9,
    fontWeight: "800",
    lineHeight: 11,
  },
});
