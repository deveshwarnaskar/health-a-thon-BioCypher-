import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { caregiverPalette, caregiverRadii, caregiverShadow } from "./caregiverDesign";
import {
  canReadCaregiverGlucose,
  canRecordCaregiverGlucose,
  canRecordCaregiverMeal,
  canReadCaregiverTasks,
  type CaregiverPatientListItem,
} from "../../services/schemas/caregiver";

export type CaregiverPatientCardProps = {
  patient: CaregiverPatientListItem;
  onSelect: (patient: CaregiverPatientListItem) => void;
  disabled?: boolean;
};

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "PT";
  const first = parts[0] ?? "";
  if (parts.length === 1) return first.slice(0, 2).toUpperCase() || "PT";
  const last = parts[parts.length - 1] ?? "";
  return ((first[0] ?? "") + (last[0] ?? "")).toUpperCase() || "PT";
}

export function CaregiverPatientCard({
  patient,
  onSelect,
  disabled = false,
}: CaregiverPatientCardProps) {
  const canReadGlucose = canReadCaregiverGlucose(patient.capabilities);
  const canRecordGlucose = canRecordCaregiverGlucose(patient.capabilities);
  const canRecordMeal = canRecordCaregiverMeal(patient.capabilities);
  const canTasks = canReadCaregiverTasks(patient.capabilities);

  const initials = getInitials(patient.name);

  return (
    <TouchableOpacity
      style={[styles.card, disabled && styles.disabled]}
      onPress={disabled ? undefined : () => onSelect(patient)}
      activeOpacity={0.78}
      accessibilityRole="button"
      accessibilityLabel={`View glucose for ${patient.name}`}
    >
      {/* Top Patient Identity Row */}
      <View style={styles.topRow}>
        <View style={styles.patientInfoRow}>
          <View style={styles.avatarWrapper}>
            <View style={styles.avatar}>
              <Text style={styles.avatarText} allowFontScaling>
                {initials}
              </Text>
            </View>
            <View style={styles.activeDotBadge}>
              <View style={styles.activeDotInner} />
            </View>
          </View>

          <View style={styles.nameBlock}>
            <Text style={styles.name} numberOfLines={1} allowFontScaling>
              {patient.name}
            </Text>

            <View style={styles.metaRow}>
              {patient.relationship_label ? (
                <View style={styles.relationshipBadge}>
                  <Ionicons name="people" size={11} color={caregiverPalette.primary} />
                  <Text style={styles.relationshipText} allowFontScaling>
                    {patient.relationship_label}
                  </Text>
                </View>
              ) : null}

              <View style={styles.verifiedBadge}>
                <Ionicons name="shield-checkmark" size={11} color={caregiverPalette.emeraldDark} />
                <Text style={styles.verifiedText} allowFontScaling>
                  Verified
                </Text>
              </View>
            </View>
          </View>
        </View>

        <View style={styles.chevronCircle}>
          <Ionicons name="chevron-forward" size={16} color={caregiverPalette.muted} />
        </View>
      </View>

      {/* Granted Capabilities Chips (Strictly Preserving Text for Tests) */}
      <View style={styles.capabilitiesRow}>
        {canReadGlucose ? (
          <View style={[styles.capChip, styles.capChipBlue]}>
            <Ionicons name="water" size={12} color={caregiverPalette.sky} />
            <Text style={[styles.capText, styles.capTextBlue]} allowFontScaling>
              Glucose view
            </Text>
          </View>
        ) : null}

        {canRecordGlucose ? (
          <View style={[styles.capChip, styles.capChipGreen]}>
            <Ionicons name="add-circle" size={12} color={caregiverPalette.emeraldDark} />
            <Text style={[styles.capText, styles.capTextGreen]} allowFontScaling>
              Can record
            </Text>
          </View>
        ) : null}

        {canRecordMeal ? (
          <View style={[styles.capChip, styles.capChipAmber]}>
            <Ionicons name="restaurant" size={12} color={caregiverPalette.amberDark} />
            <Text style={[styles.capText, styles.capTextAmber]} allowFontScaling>
              Log Meals
            </Text>
          </View>
        ) : null}

        {canTasks ? (
          <View style={[styles.capChip, styles.capChipPurple]}>
            <Ionicons name="checkbox" size={12} color={caregiverPalette.purpleDark} />
            <Text style={[styles.capText, styles.capTextPurple]} allowFontScaling>
              Care Tasks
            </Text>
          </View>
        ) : null}
      </View>

      {/* Footer Bar */}
      <View style={styles.footerRow}>
        <View style={styles.footerHintGroup}>
          <Ionicons name="sparkles" size={12} color={caregiverPalette.tealDark} />
          <Text style={styles.footerHint} allowFontScaling numberOfLines={1}>
            Tap to view daily meals, glucose timing & tasks
          </Text>
        </View>

        <View style={styles.openPill}>
          <Text style={styles.openText} allowFontScaling>
            Open Care
          </Text>
          <Ionicons name="arrow-forward" size={12} color={caregiverPalette.primary} />
        </View>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: caregiverPalette.surface,
    borderRadius: caregiverRadii.lg,
    padding: 15,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    gap: 12,
    ...caregiverShadow.card,
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  patientInfoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    flex: 1,
  },
  avatarWrapper: {
    position: "relative",
  },
  avatar: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: caregiverPalette.surfaceTeal,
    borderWidth: 1.5,
    borderColor: caregiverPalette.tealSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: {
    fontSize: 15,
    fontWeight: "800",
    color: caregiverPalette.tealDark,
    letterSpacing: 0.5,
  },
  activeDotBadge: {
    position: "absolute",
    bottom: -1,
    right: -1,
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: caregiverPalette.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  activeDotInner: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: caregiverPalette.emerald,
  },
  nameBlock: {
    flex: 1,
    gap: 4,
  },
  name: {
    fontSize: 16,
    fontWeight: "800",
    color: caregiverPalette.ink,
    letterSpacing: -0.2,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 6,
  },
  relationshipBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: caregiverPalette.primaryLight,
    paddingHorizontal: 8,
    paddingVertical: 2.5,
    borderRadius: caregiverRadii.pill,
    borderWidth: 1,
    borderColor: caregiverPalette.primaryBorder,
  },
  relationshipText: {
    fontSize: 11,
    fontWeight: "700",
    color: caregiverPalette.primary,
  },
  verifiedBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    backgroundColor: caregiverPalette.emeraldSoft,
    paddingHorizontal: 7,
    paddingVertical: 2.5,
    borderRadius: caregiverRadii.pill,
    borderWidth: 1,
    borderColor: caregiverPalette.emeraldBorder,
  },
  verifiedText: {
    fontSize: 11,
    fontWeight: "700",
    color: caregiverPalette.emeraldDark,
  },
  chevronCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: caregiverPalette.surfaceSoft,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: 6,
  },
  capabilitiesRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  capChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 9,
    paddingVertical: 3.5,
    borderRadius: caregiverRadii.pill,
  },
  capChipBlue: {
    backgroundColor: caregiverPalette.skySoft,
    borderWidth: 1,
    borderColor: caregiverPalette.skyBorder,
  },
  capTextBlue: {
    color: caregiverPalette.sky,
  },
  capChipGreen: {
    backgroundColor: caregiverPalette.emeraldSoft,
    borderWidth: 1,
    borderColor: caregiverPalette.emeraldBorder,
  },
  capTextGreen: {
    color: caregiverPalette.emeraldDark,
  },
  capChipAmber: {
    backgroundColor: caregiverPalette.amberSoft,
    borderWidth: 1,
    borderColor: caregiverPalette.amberBorder,
  },
  capTextAmber: {
    color: caregiverPalette.amberDark,
  },
  capChipPurple: {
    backgroundColor: caregiverPalette.purpleSoft,
    borderWidth: 1,
    borderColor: caregiverPalette.purpleBorder,
  },
  capTextPurple: {
    color: caregiverPalette.purpleDark,
  },
  capText: {
    fontSize: 11,
    fontWeight: "700",
  },
  footerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: caregiverPalette.borderLight,
    gap: 8,
  },
  footerHintGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    flex: 1,
  },
  footerHint: {
    fontSize: 11,
    color: caregiverPalette.muted,
    flex: 1,
  },
  openPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: caregiverPalette.primaryLight,
    paddingHorizontal: 9,
    paddingVertical: 4.5,
    borderRadius: caregiverRadii.sm,
    borderWidth: 1,
    borderColor: caregiverPalette.primaryBorder,
  },
  openText: {
    fontSize: 11,
    fontWeight: "700",
    color: caregiverPalette.primary,
  },
  disabled: {
    opacity: 0.5,
  },
});