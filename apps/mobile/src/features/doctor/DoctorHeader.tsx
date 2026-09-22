import React, { useState } from "react";
import { StyleSheet, Text, View, TextInput, Pressable, ScrollView } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Badge } from "../../components/primitives/Badge";
import { spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorShadow, doctorSoftShadow } from "./doctorDesign";
import type { PatientSummaryResponse } from "../../services/schemas/patients";

export type DoctorHeaderProps = {
  compact?: boolean;
  doctorName?: string;
  facilityId?: string;
  patients: PatientSummaryResponse[];
  activeDestinationLabel?: string;
  selectedPatientName?: string | null;
  onMenuPress?: () => void;
  onSelectPatient: (patient: PatientSummaryResponse) => void;
  onSignOut?: () => void;
  pendingReviewCount?: number;
  onOpenReviews?: () => void;
};

export function DoctorHeader({
  compact = false,
  doctorName = "Doctor",
  facilityId = "Main Hospital",
  patients,
  activeDestinationLabel = "Clinical Workstation",
  selectedPatientName,
  onMenuPress,
  onSelectPatient,
  onSignOut,
  pendingReviewCount = 0,
  onOpenReviews,
}: DoctorHeaderProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchFocused, setIsSearchFocused] = useState(false);

  const filteredPatients = searchQuery.trim().length >= 1
    ? patients.filter(
        (p) =>
          p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          p.uh_id.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : [];

  const searchNode = (
    <View style={[styles.searchSection, compact ? styles.searchSectionCompact : null]}>
      <View style={[styles.searchInputContainer, compact ? styles.searchInputContainerCompact : null]}>
        <Ionicons name="search" size={19} color={doctorPalette.quiet} style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          placeholder={compact ? "Search patients or UHID" : "Search patients, UHID, reviews..."}
          placeholderTextColor={doctorPalette.quiet}
          value={searchQuery}
          onChangeText={setSearchQuery}
          onFocus={() => setIsSearchFocused(true)}
          onBlur={() => {
            setTimeout(() => setIsSearchFocused(false), 250);
          }}
          autoCapitalize="none"
          autoCorrect={false}
          accessibilityLabel="Search patient by name or UHID"
        />
        {searchQuery ? (
          <Pressable
            onPress={() => setSearchQuery("")}
            hitSlop={8}
            style={styles.clearBtn}
            accessibilityRole="button"
            accessibilityLabel="Clear patient search"
          >
            <Ionicons name="close" size={17} color={doctorPalette.muted} />
          </Pressable>
        ) : null}
      </View>

      {isSearchFocused && filteredPatients.length > 0 ? (
        <View style={styles.searchDropdown}>
          <ScrollView keyboardShouldPersistTaps="handled" style={styles.dropdownScroll}>
            {filteredPatients.map((p) => (
              <Pressable
                key={p.patient_id}
                style={styles.dropdownItem}
                onPress={() => {
                  onSelectPatient(p);
                  setSearchQuery("");
                  setIsSearchFocused(false);
                }}
                accessibilityRole="button"
                accessibilityLabel={`Open ${p.name}`}
              >
                <View style={styles.dropdownItemInfo}>
                  <Text style={styles.dropdownName} numberOfLines={1}>
                    {p.name}
                  </Text>
                  <Text style={styles.dropdownMeta}>UHID: {p.uh_id}</Text>
                </View>
                <Badge
                  label={p.active ? "Active" : "Inactive"}
                  tone={p.active ? "success" : "neutral"}
                />
              </Pressable>
            ))}
          </ScrollView>
        </View>
      ) : null}
    </View>
  );

  return (
    <View style={[styles.headerContainer, compact ? styles.headerContainerCompact : null]}>
      <View style={[styles.topRow, compact ? styles.topRowCompact : null]}>
        <View style={[styles.brandSection, compact ? styles.brandSectionCompact : null]}>
          {compact && onMenuPress ? (
            <Pressable
              style={styles.menuButton}
              onPress={onMenuPress}
              accessibilityRole="button"
              accessibilityLabel="Open doctor navigation menu"
            >
              <Ionicons name="menu" size={24} color={doctorPalette.ink} />
            </Pressable>
          ) : (
            <View style={styles.logoBadge}>
              <Text style={styles.logoText}>TX</Text>
            </View>
          )}
          <View style={styles.titleStack}>
            {compact ? (
              <Text style={styles.greetingText} numberOfLines={1}>
                Good Morning
              </Text>
            ) : null}
            <View style={styles.doctorInfoRow}>
              <Text style={[styles.doctorTitle, compact ? styles.doctorTitleCompact : null]} allowFontScaling numberOfLines={1}>
                {selectedPatientName ?? `Dr. ${doctorName}`}
              </Text>
              {!compact ? <Badge label="DOCTOR" tone="info" /> : null}
              {!compact ? (
                <View style={styles.liveSyncBadge}>
                  <View style={styles.pulseDot} />
                  <Text style={styles.liveSyncText}>Live Sync</Text>
                </View>
              ) : null}
            </View>
            <Text style={styles.facilitySubtitle} allowFontScaling numberOfLines={1}>
              {compact ? activeDestinationLabel : `${facilityId} · Clinical Workstation`}
            </Text>
          </View>
        </View>

        {compact ? null : searchNode}

        <View style={[styles.actionsSection, compact ? styles.actionsSectionCompact : null]}>
          {onOpenReviews ? (
            <Pressable
              onPress={onOpenReviews}
              style={[
                styles.reviewPill,
                pendingReviewCount > 0 ? styles.reviewPillActive : styles.reviewPillNeutral,
              ]}
              accessibilityLabel={`Review Queue, ${pendingReviewCount} pending`}
            >
              <Ionicons
                name="notifications"
                size={18}
                color={pendingReviewCount > 0 ? doctorPalette.ink : doctorPalette.muted}
              />
              <Text style={styles.reviewPillText}>
                <Text style={styles.reviewPillCount}>{pendingReviewCount}</Text>
              </Text>
            </Pressable>
          ) : null}

          {onSignOut ? (
            <Pressable
              style={styles.signOutButton}
              onPress={onSignOut}
              accessibilityLabel="Sign out"
              accessibilityHint="Signs out of clinical session"
            >
              <Ionicons name="log-out-outline" size={20} color={doctorPalette.ink} />
            </Pressable>
          ) : null}
        </View>
      </View>

      {compact ? <View style={styles.compactSearchRow}>{searchNode}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  headerContainer: {
    backgroundColor: doctorPalette.appBackground,
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 16,
    zIndex: 100,
  },
  headerContainerCompact: {
    paddingHorizontal: 12,
    paddingTop: 12,
    paddingBottom: 10,
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 14,
    flexWrap: "wrap",
  },
  topRowCompact: {
    alignItems: "center",
    flexWrap: "nowrap",
    gap: 10,
  },
  brandSection: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    minWidth: 220,
    flexShrink: 1,
  },
  brandSectionCompact: {
    minWidth: 0,
    flex: 1,
    gap: spacing.xs,
  },
  menuButton: {
    width: 50,
    height: 50,
    borderRadius: 25,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: doctorPalette.surface,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.9)",
    ...doctorSoftShadow,
  },
  logoBadge: {
    width: 48,
    height: 48,
    backgroundColor: doctorPalette.primary,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    ...doctorSoftShadow,
  },
  logoText: {
    color: doctorPalette.surface,
    fontWeight: "800",
    fontSize: typography.fontSize.body,
    letterSpacing: 0,
  },
  titleStack: {
    flex: 1,
    minWidth: 0,
  },
  greetingText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
    fontWeight: "700",
  },
  doctorInfoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    minWidth: 0,
  },
  doctorTitle: {
    fontSize: typography.fontSize.title,
    lineHeight: typography.lineHeight.title,
    fontWeight: "800",
    color: doctorPalette.ink,
    flexShrink: 1,
  },
  doctorTitleCompact: {
    fontSize: 22,
    lineHeight: 28,
    fontWeight: "900",
  },
  facilitySubtitle: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
    fontWeight: "600",
  },
  liveSyncBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: doctorPalette.limeSoft,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 12,
  },
  pulseDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#47B741",
  },
  liveSyncText: {
    fontSize: 10,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  searchSection: {
    flex: 1,
    minWidth: 260,
    maxWidth: 520,
    position: "relative",
  },
  searchSectionCompact: {
    minWidth: "100%",
    maxWidth: "100%",
    width: "100%",
  },
  searchInputContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: doctorPalette.surface,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.9)",
    borderRadius: doctorRadii.pill,
    paddingHorizontal: spacing.md,
    height: 54,
    ...doctorSoftShadow,
  },
  searchInputContainerCompact: {
    height: 50,
    paddingHorizontal: spacing.sm,
  },
  searchIcon: {
    marginRight: spacing.xs,
  },
  searchInput: {
    flex: 1,
    fontSize: typography.fontSize.body,
    color: doctorPalette.ink,
    paddingVertical: 0,
  },
  clearBtn: {
    padding: 4,
  },
  searchDropdown: {
    position: "absolute",
    top: 60,
    left: 0,
    right: 0,
    backgroundColor: doctorPalette.surface,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    borderRadius: doctorRadii.lg,
    maxHeight: 240,
    ...doctorShadow,
    zIndex: 200,
    overflow: "hidden",
  },
  dropdownScroll: {
    maxHeight: 240,
  },
  dropdownItem: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.border,
  },
  dropdownItemInfo: {
    flex: 1,
  },
  dropdownName: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  dropdownMeta: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  actionsSection: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginLeft: "auto",
  },
  actionsSectionCompact: {
    marginLeft: 0,
    flexShrink: 0,
  },
  reviewPill: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    minWidth: 54,
    height: 54,
    paddingHorizontal: spacing.sm,
    borderRadius: 27,
    borderWidth: 1,
    ...doctorSoftShadow,
  },
  compactSearchRow: {
    marginTop: spacing.sm,
  },
  reviewPillActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.surfaceLime,
  },
  reviewPillNeutral: {
    backgroundColor: doctorPalette.surface,
    borderColor: "rgba(255,255,255,0.9)",
  },
  reviewPillText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  reviewPillCount: {
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  signOutButton: {
    width: 54,
    height: 54,
    borderRadius: 27,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: doctorPalette.surface,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.9)",
    ...doctorSoftShadow,
  },
});
