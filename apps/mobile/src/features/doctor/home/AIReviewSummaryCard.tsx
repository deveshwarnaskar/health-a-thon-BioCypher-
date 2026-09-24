import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "../doctorDesign";
import { SectionHeader, HomeInlineState } from "./DoctorHomeBits";

export function AIReviewSummaryCard({
  total,
  kinds,
  onOpen,
  isLoading,
}: {
  total: number;
  kinds: { key: string; label: string; count: number }[];
  onOpen: () => void;
  isLoading?: boolean;
}) {
  const core = kinds.slice(0, 4);

  return (
    <View style={styles.section}>
      <SectionHeader title="AI Decision Support" viewAllLabel="Open review queue" onViewAll={onOpen} />
      <Pressable
        style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
        onPress={onOpen}
        accessibilityRole="button"
        accessibilityLabel={`AI Review Queue: ${total} items pending validation`}
      >
        <View style={styles.cardHeader}>
          <View style={styles.sparkIconWrap}>
            <Ionicons name="sparkles" size={17} color="#D97706" />
          </View>
          <View style={styles.headerText}>
            <View style={styles.titleRow}>
              <Text style={styles.cardTitle} allowFontScaling numberOfLines={1}>
                Clinical Review Queue
              </Text>
              <View
                style={[
                  styles.statusBadge,
                  total > 0 ? styles.statusBadgePending : styles.statusBadgeClear,
                ]}
              >
                <Text
                  style={[
                    styles.statusBadgeText,
                    total > 0 ? styles.statusBadgeTextPending : styles.statusBadgeTextClear,
                  ]}
                  allowFontScaling
                >
                  {isLoading ? "…" : total > 0 ? `${total} Pending` : "Queue Clear"}
                </Text>
              </View>
            </View>
            <Text style={styles.cardSubtitle} allowFontScaling numberOfLines={1}>
              Summaries & patterns awaiting clinician validation
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={doctorPalette.muted} />
        </View>

        {!isLoading && kinds.length > 0 ? (
          <View style={styles.kindsRow}>
            {core.map((kind) => (
              <View
                key={kind.key}
                style={styles.kindPill}
                accessible
                accessibilityRole="text"
                accessibilityLabel={`${kind.label}: ${kind.count}`}
              >
                <Text style={styles.kindLabel} allowFontScaling numberOfLines={1}>
                  {kind.label}
                </Text>
                <View style={styles.kindCountBadge}>
                  <Text style={styles.kindCount} allowFontScaling>
                    {kind.count}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        ) : null}

        {!isLoading && kinds.length === 0 ? (
          <View style={styles.emptyNote}>
            <Ionicons name="checkmark-done-circle" size={15} color="#10B981" />
            <Text style={styles.emptyNoteText} allowFontScaling>
              All AI-assisted clinical observations have been reviewed.
            </Text>
          </View>
        ) : null}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: 12,
  },
  card: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 16,
    gap: 12,
    ...doctorSoftShadow,
  },
  cardPressed: {
    opacity: 0.86,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  sparkIconWrap: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "#FEF3C7",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "#FDE68A",
  },
  headerText: {
    flex: 1,
    gap: 2,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.2,
    flexShrink: 1,
  },
  statusBadge: {
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderWidth: 1,
  },
  statusBadgePending: {
    backgroundColor: "#FFFBEB",
    borderColor: "#FDE68A",
  },
  statusBadgeClear: {
    backgroundColor: "#F0FDF4",
    borderColor: "#BBF7D0",
  },
  statusBadgeText: {
    fontSize: 10,
    fontWeight: "800",
  },
  statusBadgeTextPending: {
    color: "#B45309",
  },
  statusBadgeTextClear: {
    color: "#15803D",
  },
  cardSubtitle: {
    fontSize: 11,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  kindsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 7,
    paddingTop: 2,
  },
  kindPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: doctorPalette.surfaceSoft,
    borderRadius: doctorRadii.pill,
    paddingLeft: 10,
    paddingRight: 6,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
  },
  kindLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: doctorPalette.inkSecondary,
  },
  kindCountBadge: {
    backgroundColor: doctorPalette.primary,
    borderRadius: 10,
    minWidth: 18,
    height: 18,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 4,
  },
  kindCount: {
    fontSize: 10,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  emptyNote: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "#F0FDF4",
    borderRadius: doctorRadii.md,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  emptyNoteText: {
    fontSize: 11,
    fontWeight: "600",
    color: "#15803D",
  },
});