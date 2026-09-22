import React from "react";
import { StyleSheet, Text, View, Pressable, ScrollView } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import type { PatientSummaryResponse } from "../../services/schemas/patients";

export type DoctorDestinationKey =
  | "overview"
  | "patients"
  | "review"
  | "monitoring"
  | "reports"
  | "tasks"
  | "plans"
  | "documents"
  | "messages"
  | "audit";

export type DoctorSidebarProps = {
  activeDestination: DoctorDestinationKey;
  compact?: boolean;
  onSelectDestination: (dest: DoctorDestinationKey) => void;
  selectedPatient?: PatientSummaryResponse | null;
  onClearPatient?: () => void;
  reviewCount?: number;
  taskCount?: number;
  onRequestClose?: () => void;
};

export interface DoctorNavItem {
  key: DoctorDestinationKey;
  label: string;
  shortLabel: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
  badge?: number;
}

const baseNavItems: Omit<DoctorNavItem, "badge">[] = [
  { key: "overview", label: "Overview", shortLabel: "Home", icon: "home" },
  { key: "patients", label: "Patient Directory", shortLabel: "Patients", icon: "people" },
  { key: "review", label: "Review Queue", shortLabel: "Review", icon: "sparkles" },
  { key: "monitoring", label: "Monitoring", shortLabel: "Vitals", icon: "analytics" },
  { key: "reports", label: "Clinical Reports", shortLabel: "Reports", icon: "document-text" },
  { key: "tasks", label: "Care Tasks", shortLabel: "Tasks", icon: "checkbox" },
  { key: "plans", label: "Medication Plans", shortLabel: "Plans", icon: "medkit" },
  { key: "documents", label: "Documents", shortLabel: "Docs", icon: "folder-open" },
  { key: "messages", label: "Communication", shortLabel: "Inbox", icon: "chatbubble-ellipses" },
  { key: "audit", label: "Audit Log", shortLabel: "Audit", icon: "shield-checkmark" },
];

export function getDoctorDestinationLabel(destination: DoctorDestinationKey) {
  return baseNavItems.find((item) => item.key === destination)?.shortLabel ?? "Workspace";
}

export function DoctorSidebar({
  activeDestination,
  compact = false,
  onSelectDestination,
  selectedPatient,
  onClearPatient,
  reviewCount = 0,
  taskCount = 0,
  onRequestClose,
}: DoctorSidebarProps) {
  const items: DoctorNavItem[] = baseNavItems.map((item) => ({
    ...item,
    badge:
      item.key === "review"
        ? reviewCount
        : item.key === "tasks"
        ? taskCount
        : undefined,
  }));

  const handleSelect = (item: DoctorNavItem) => {
    if (selectedPatient && onClearPatient) {
      onClearPatient();
    }
    onSelectDestination(item.key);
    onRequestClose?.();
  };

  const navList = (
    <ScrollView
      style={styles.navScroll}
      contentContainerStyle={[styles.navContent, compact ? styles.navContentCompact : null]}
      showsVerticalScrollIndicator={false}
    >
      <Text style={styles.sectionHeader}>CLINICAL WORKSPACE</Text>
      {items.map((item) => {
        const isActive = !selectedPatient && activeDestination === item.key;
        return (
          <Pressable
            key={item.key}
            style={[
              styles.navItem,
              compact ? styles.navItemCompact : null,
              isActive ? styles.navItemActive : null,
            ]}
            onPress={() => handleSelect(item)}
            accessibilityRole="button"
            accessibilityLabel={`${item.label}${item.badge ? `, ${item.badge} items` : ""}`}
          >
            <View style={[styles.navItemIcon, isActive ? styles.navItemIconActive : null]}>
              <Ionicons
                name={item.icon}
                size={compact ? 20 : 18}
                color={isActive ? doctorPalette.ink : doctorPalette.muted}
              />
            </View>
            <View style={styles.navItemCopy}>
              <Text
                style={[styles.navItemLabel, isActive ? styles.navItemLabelActive : null]}
                numberOfLines={1}
              >
                {item.label}
              </Text>
              {compact ? (
                <Text style={styles.navItemHint} numberOfLines={1}>
                  {item.shortLabel}
                </Text>
              ) : null}
            </View>
            {item.badge && item.badge > 0 ? (
              <View style={styles.badgeContainer}>
                <Text style={styles.badgeText}>{item.badge}</Text>
              </View>
            ) : null}
          </Pressable>
        );
      })}
    </ScrollView>
  );

  const activePatient = selectedPatient ? (
    <View style={[styles.activePatientBox, compact ? styles.activePatientBoxCompact : null]}>
      <Text style={styles.activePatientLabel}>ACTIVE PATIENT</Text>
      <Text style={styles.activePatientName} numberOfLines={1}>
        {selectedPatient.name}
      </Text>
      <Text style={styles.activePatientUhid}>UHID: {selectedPatient.uh_id}</Text>
      {onClearPatient ? (
        <Pressable
          style={styles.closePatientBtn}
          onPress={onClearPatient}
          accessibilityRole="button"
          accessibilityLabel="Close patient and return to doctor workspace"
        >
          <Text style={styles.closePatientText}>All Patients</Text>
        </Pressable>
      ) : null}
    </View>
  ) : null;

  const footer = (
    <View style={[styles.footerNotice, compact ? styles.footerNoticeCompact : null]}>
      <Text style={styles.footerNoticeTitle}>ICMR-NIN & ADA / EASD</Text>
      <Text style={styles.footerNoticeText}>
        Assistive clinical intelligence. Targets and medications require clinician authorship.
      </Text>
    </View>
  );

  if (compact) {
    return (
      <View style={styles.drawerContainer}>
        <View style={styles.drawerHeader}>
          <View style={styles.drawerBrand}>
            <View style={styles.drawerLogo}>
              <Text style={styles.drawerLogoText}>TX</Text>
            </View>
            <View style={styles.drawerTitleBlock}>
              <Text style={styles.drawerTitle}>Doctor</Text>
              <Text style={styles.drawerSubtitle}>Clinical workspace</Text>
            </View>
          </View>
          <Pressable
            style={styles.drawerClose}
            onPress={onRequestClose}
            accessibilityRole="button"
            accessibilityLabel="Close navigation menu"
          >
            <Ionicons name="close" size={22} color={doctorPalette.ink} />
          </Pressable>
        </View>

        {activePatient}
        {navList}
        {footer}
      </View>
    );
  }

  return (
    <View style={styles.sidebarContainer}>
      {activePatient}
      {navList}
      {footer}
    </View>
  );
}

const styles = StyleSheet.create({
  sidebarContainer: {
    width: 244,
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.xl,
    marginLeft: 16,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.84)",
    display: "flex",
    flexDirection: "column",
    justifyContent: "space-between",
    ...doctorSoftShadow,
  },
  drawerContainer: {
    flex: 1,
    backgroundColor: doctorPalette.surface,
    borderTopRightRadius: doctorRadii.xl,
    borderBottomRightRadius: doctorRadii.xl,
    overflow: "hidden",
  },
  drawerHeader: {
    minHeight: 92,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
    backgroundColor: doctorPalette.surfaceBlue,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.border,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  drawerBrand: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    flex: 1,
  },
  drawerLogo: {
    width: 46,
    height: 46,
    borderRadius: 23,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: doctorPalette.primary,
  },
  drawerLogoText: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "900",
    color: doctorPalette.surface,
  },
  drawerTitleBlock: {
    flex: 1,
  },
  drawerTitle: {
    fontSize: typography.fontSize.title,
    lineHeight: typography.lineHeight.title,
    fontWeight: "900",
    color: doctorPalette.ink,
  },
  drawerSubtitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: "700",
    color: doctorPalette.muted,
  },
  drawerClose: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.82)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.9)",
  },
  activePatientBox: {
    backgroundColor: doctorPalette.surfaceBlue,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.border,
    padding: spacing.md,
    gap: 5,
    borderTopLeftRadius: doctorRadii.xl,
    borderTopRightRadius: doctorRadii.xl,
  },
  activePatientBoxCompact: {
    margin: spacing.md,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.82)",
  },
  activePatientLabel: {
    fontSize: 10,
    fontWeight: "800",
    color: doctorPalette.primary,
    letterSpacing: 0,
  },
  activePatientName: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  activePatientUhid: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  closePatientBtn: {
    marginTop: spacing.xs,
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surface,
    alignSelf: "flex-start",
  },
  closePatientText: {
    fontSize: typography.fontSize.caption,
    fontWeight: "800",
    color: doctorPalette.primary,
  },
  navScroll: {
    flex: 1,
  },
  navContent: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    gap: 7,
  },
  navContentCompact: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.lg,
  },
  sectionHeader: {
    fontSize: 10,
    fontWeight: "800",
    color: doctorPalette.quiet,
    letterSpacing: 0,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    marginBottom: spacing.xs,
  },
  navItem: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 52,
    paddingVertical: 8,
    paddingHorizontal: spacing.sm,
    borderRadius: doctorRadii.lg,
    gap: spacing.sm,
  },
  navItemCompact: {
    minHeight: 58,
    paddingHorizontal: spacing.md,
  },
  navItemActive: {
    backgroundColor: doctorPalette.surfaceLime,
  },
  navItemIcon: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: doctorPalette.surfaceSoft,
  },
  navItemIconActive: {
    backgroundColor: "rgba(255,255,255,0.72)",
  },
  navItemCopy: {
    flex: 1,
    minWidth: 0,
  },
  navItemLabel: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.muted,
    fontWeight: "800",
  },
  navItemLabelActive: {
    color: doctorPalette.ink,
    fontWeight: "900",
  },
  navItemHint: {
    fontSize: 11,
    fontWeight: "700",
    color: doctorPalette.quiet,
  },
  badgeContainer: {
    backgroundColor: doctorPalette.primary,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 10,
    minWidth: 18,
    alignItems: "center",
  },
  badgeText: {
    fontSize: 10,
    fontWeight: "800",
    color: doctorPalette.surface,
  },
  footerNotice: {
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: doctorPalette.border,
    backgroundColor: doctorPalette.surfaceSoft,
    borderBottomLeftRadius: doctorRadii.xl,
    borderBottomRightRadius: doctorRadii.xl,
  },
  footerNoticeCompact: {
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: doctorRadii.xl,
  },
  footerNoticeTitle: {
    fontSize: 10,
    fontWeight: "800",
    color: doctorPalette.muted,
    marginBottom: 2,
  },
  footerNoticeText: {
    fontSize: 9,
    color: doctorPalette.muted,
    lineHeight: 12,
  },
});
