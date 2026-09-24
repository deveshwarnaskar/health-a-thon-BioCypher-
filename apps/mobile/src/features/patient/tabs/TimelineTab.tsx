import React, { useState, useMemo } from "react";
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { PatientScreenHeader } from "../components/PatientScreenHeader";
import { TimelineItemRow } from "../components/TimelineItemRow";
import { EventDetailModal } from "../components/EventDetailModal";
import { useUnifiedTimeline } from "../api";
import type { TimelineEvent, TimelineFilter } from "../types";

export type TimelineTabProps = {
  patientId: string | null;
  onSelectEvent?: (event: TimelineEvent) => void;
  onOpenAssist?: () => void;
};

const FILTERS: { key: TimelineFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "glucose", label: "Glucose" },
  { key: "meals", label: "Meals" },
  { key: "medication", label: "Medication" },
  { key: "activity", label: "Activity" },
  { key: "vitals", label: "Vitals" },
  { key: "symptoms", label: "Symptoms" },
  { key: "sleep", label: "Sleep" },
  { key: "tasks", label: "Tasks" },
  { key: "documents", label: "Documents" },
];

function isSameDay(d1: Date, d2: Date): boolean {
  return (
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
  );
}

function getGroupHeader(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const yesterday = new Date();
  yesterday.setDate(now.getDate() - 1);

  if (isSameDay(date, now)) return "TODAY";
  if (isSameDay(date, yesterday)) return "YESTERDAY";

  return date.toLocaleDateString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).toUpperCase();
}

export function TimelineTab({
  patientId,
  onSelectEvent,
  onOpenAssist,
}: TimelineTabProps) {
  const [selectedFilter, setSelectedFilter] = useState<TimelineFilter>("all");
  const [viewMode, setViewMode] = useState<"feed" | "day_summary">("feed");
  const [activeModalEvent, setActiveModalEvent] = useState<TimelineEvent | null>(null);

  const { data: events = [], isRefetching, refetch } = useUnifiedTimeline(patientId);

  // Filter events
  const filteredEvents = useMemo(() => {
    if (selectedFilter === "all") return events;
    if (selectedFilter === "meals") return events.filter((e) => e.type === "meal");
    if (selectedFilter === "tasks") return events.filter((e) => e.type === "task");
    if (selectedFilter === "documents") return events.filter((e) => e.type === "document");
    if (selectedFilter === "vitals") return events.filter((e) => e.type === "vital");
    if (selectedFilter === "symptoms") return events.filter((e) => e.type === "symptom");
    return events.filter((e) => e.type === selectedFilter);
  }, [events, selectedFilter]);

  // Group events by day header
  const groupedEvents = useMemo(() => {
    const groups: { header: string; items: TimelineEvent[] }[] = [];
    let currentHeader = "";
    let currentGroup: TimelineEvent[] = [];

    for (const item of filteredEvents) {
      const header = getGroupHeader(item.timestamp);
      if (header !== currentHeader) {
        if (currentGroup.length > 0) {
          groups.push({ header: currentHeader, items: currentGroup });
        }
        currentHeader = header;
        currentGroup = [item];
      } else {
        currentGroup.push(item);
      }
    }

    if (currentGroup.length > 0) {
      groups.push({ header: currentHeader, items: currentGroup });
    }

    return groups;
  }, [filteredEvents]);

  const handleItemPress = (event: TimelineEvent) => {
    setActiveModalEvent(event);
    if (onSelectEvent) {
      onSelectEvent(event);
    }
  };

  return (
    <View style={styles.container}>
      <PatientScreenHeader
        title="Care Timeline"
        subtitle="Your complete chronological health history"
        onPressAssist={onOpenAssist}
      />

      {/* View Mode Toggle Row */}
      <View style={styles.topControlsRow}>
        <View style={styles.toggleButtonGroup}>
          <TouchableOpacity
            style={[styles.toggleButton, viewMode === "feed" && styles.toggleButtonActive]}
            onPress={() => setViewMode("feed")}
            accessibilityRole="button"
            accessibilityLabel="Feed View"
          >
            <Ionicons
              name="list-outline"
              size={14}
              color={viewMode === "feed" ? colors.textOnPrimary : colors.textSecondary}
            />
            <Text
              style={[
                styles.toggleButtonText,
                viewMode === "feed" && styles.toggleButtonTextActive,
              ]}
              allowFontScaling
            >
              Feed
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.toggleButton,
              viewMode === "day_summary" && styles.toggleButtonActive,
            ]}
            onPress={() => setViewMode("day_summary")}
            accessibilityRole="button"
            accessibilityLabel="Day Summary View"
          >
            <Ionicons
              name="calendar-outline"
              size={14}
              color={
                viewMode === "day_summary" ? colors.textOnPrimary : colors.textSecondary
              }
            />
            <Text
              style={[
                styles.toggleButtonText,
                viewMode === "day_summary" && styles.toggleButtonTextActive,
              ]}
              allowFontScaling
            >
              Day Summary
            </Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.countBadge} allowFontScaling>
          {filteredEvents.length} {filteredEvents.length === 1 ? "entry" : "entries"}
        </Text>
      </View>

      {/* Filter Bar */}
      <View style={styles.filterContainer}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterScroll}
        >
          {FILTERS.map((f) => {
            const isSelected = selectedFilter === f.key;
            return (
              <TouchableOpacity
                key={f.key}
                style={[styles.filterChip, isSelected && styles.filterChipSelected]}
                onPress={() => setSelectedFilter(f.key)}
                accessibilityRole="button"
                accessibilityState={{ selected: isSelected }}
                accessibilityLabel={`Filter by ${f.label}`}
                activeOpacity={0.7}
              >
                <Text
                  style={[styles.filterChipText, isSelected && styles.filterChipTextSelected]}
                  allowFontScaling
                >
                  {f.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={isRefetching}
            onRefresh={refetch}
            tintColor={colors.primary}
            colors={[colors.primary]}
          />
        }
      >
        {groupedEvents.length === 0 ? (
          <View style={styles.emptyContainer}>
            <View style={styles.emptyIconCircle}>
              <Ionicons name="calendar-outline" size={34} color="#0D9488" />
            </View>
            <Text style={styles.emptyTitle} allowFontScaling>
              No timeline records
            </Text>
            <Text style={styles.emptySubtitle} allowFontScaling>
              {selectedFilter === "all"
                ? "Your glucose readings, meals, and completed care tasks will appear here in chronological order."
                : `No ${selectedFilter} entries found. New entries will show up here.`}
            </Text>
          </View>
        ) : viewMode === "day_summary" ? (
          groupedEvents.map((group) => {
            const glucoseItems = group.items.filter((i) => i.type === "glucose");
            const mealItems = group.items.filter((i) => i.type === "meal");
            const medItems = group.items.filter((i) => i.type === "medication");
            const actItems = group.items.filter((i) => i.type === "activity");
            const sympItems = group.items.filter((i) => i.type === "symptom");

            return (
              <View key={group.header} style={styles.daySummaryCard}>
                <View style={styles.daySummaryHeader}>
                  <Text style={styles.daySummaryTitle} allowFontScaling>
                    {group.header}
                  </Text>
                  <View style={styles.daySummaryPill}>
                    <Text style={styles.daySummaryPillText} allowFontScaling>
                      {group.items.length} logged
                    </Text>
                  </View>
                </View>

                <View style={styles.daySummaryStatsGrid}>
                  <View style={styles.statBox}>
                    <Text style={styles.statValue} allowFontScaling>
                      {glucoseItems.length}
                    </Text>
                    <Text style={styles.statLabel} allowFontScaling>
                      Glucose
                    </Text>
                  </View>
                  <View style={styles.statBox}>
                    <Text style={styles.statValue} allowFontScaling>
                      {mealItems.length}
                    </Text>
                    <Text style={styles.statLabel} allowFontScaling>
                      Meals
                    </Text>
                  </View>
                  <View style={styles.statBox}>
                    <Text style={styles.statValue} allowFontScaling>
                      {medItems.length}
                    </Text>
                    <Text style={styles.statLabel} allowFontScaling>
                      Meds
                    </Text>
                  </View>
                  <View style={styles.statBox}>
                    <Text style={styles.statValue} allowFontScaling>
                      {actItems.length}
                    </Text>
                    <Text style={styles.statLabel} allowFontScaling>
                      Activity
                    </Text>
                  </View>
                </View>

                {sympItems.length > 0 ? (
                  <View style={styles.symptomNoticeRow}>
                    <Ionicons name="warning-outline" size={14} color="#D97706" />
                    <Text style={styles.symptomNoticeText} allowFontScaling>
                      {sympItems.length} unusual symptom observation logged
                    </Text>
                  </View>
                ) : null}

                <TouchableOpacity
                  style={styles.expandDayBtn}
                  onPress={() => setViewMode("feed")}
                  accessibilityRole="button"
                  accessibilityLabel={`View all items for ${group.header}`}
                  activeOpacity={0.7}
                >
                  <Text style={styles.expandDayBtnText} allowFontScaling>
                    View Timeline Feed
                  </Text>
                  <Ionicons name="arrow-forward" size={14} color="#0D9488" style={{ marginLeft: 4 }} />
                </TouchableOpacity>
              </View>
            );
          })
        ) : (
          groupedEvents.map((group) => (
            <View key={group.header} style={styles.groupSection}>
              <View style={styles.groupHeaderContainer}>
                <Text style={styles.groupHeaderText} allowFontScaling>
                  {group.header}
                </Text>
                <View style={styles.groupLine} />
              </View>

              {group.items.map((event) => (
                <TimelineItemRow
                  key={event.id}
                  event={event}
                  onPress={handleItemPress}
                />
              ))}
            </View>
          ))
        )}
      </ScrollView>

      {/* Auditable Event Detail Modal */}
      <EventDetailModal
        visible={!!activeModalEvent}
        event={activeModalEvent}
        onClose={() => setActiveModalEvent(null)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  filterContainer: {
    backgroundColor: colors.background,
    paddingVertical: spacing.sm,
  },
  filterScroll: {
    paddingHorizontal: spacing.md,
    gap: spacing.xs,
  },
  filterChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    minHeight: 34,
    alignItems: "center",
    justifyContent: "center",
  },
  filterChipSelected: {
    backgroundColor: colors.primaryInk,
    borderColor: colors.primaryInk,
  },
  filterChipText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.medium,
    color: colors.textSecondary,
  },
  filterChipTextSelected: {
    color: colors.textOnPrimary,
    fontWeight: typography.weight.bold,
  },
  content: {
    padding: spacing.md,
    paddingBottom: 110,
  },
  groupSection: {
    marginBottom: spacing.md,
  },
  groupHeaderContainer: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  groupHeaderText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#64748B",
    letterSpacing: 1.2,
  },
  groupLine: {
    flex: 1,
    height: 1,
    backgroundColor: "#E2E8F0",
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl,
    backgroundColor: colors.surface,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 2,
    marginTop: spacing.sm,
  },
  emptyIconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#0F172A",
  },
  emptySubtitle: {
    fontSize: 13,
    color: "#64748B",
    marginTop: spacing.xs,
    textAlign: "center",
    maxWidth: 280,
    lineHeight: 18,
  },
  topControlsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingTop: spacing.xs,
  },
  toggleButtonGroup: {
    flexDirection: "row",
    backgroundColor: "#EEF2F6",
    borderRadius: radii.pill,
    padding: 3,
    gap: 3,
  },
  toggleButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
  },
  toggleButtonActive: {
    backgroundColor: "#0D5C75",
  },
  toggleButtonText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#64748B",
  },
  toggleButtonTextActive: {
    color: "#FFFFFF",
    fontWeight: "700",
  },
  countBadge: {
    fontSize: 12,
    fontWeight: "600",
    color: "#64748B",
  },
  daySummaryCard: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 2,
    gap: spacing.sm,
  },
  daySummaryHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  daySummaryTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
  },
  daySummaryPill: {
    backgroundColor: "#F0FDFA",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#CCFBF1",
  },
  daySummaryPillText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#0D9488",
  },
  daySummaryStatsGrid: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  statBox: {
    flex: 1,
    backgroundColor: "#F8FAFC",
    borderRadius: 12,
    paddingVertical: spacing.xs,
    paddingHorizontal: 4,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#EEF2F6",
  },
  statValue: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
  },
  statLabel: {
    fontSize: 10,
    fontWeight: "600",
    color: "#64748B",
    marginTop: 2,
  },
  symptomNoticeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: "#FFFBEB",
    padding: spacing.xs + 2,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#FEF3C7",
  },
  symptomNoticeText: {
    fontSize: 12,
    color: "#B45309",
    fontWeight: "500",
  },
  expandDayBtn: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-end",
    paddingTop: spacing.xxs,
  },
  expandDayBtnText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0D9488",
  },
});
