import React, { useState, useMemo } from "react";
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { colors, radii, spacing, typography } from "../../../theming/tokens";
import { PatientScreenHeader } from "../components/PatientScreenHeader";
import { TimelineItemRow } from "../components/TimelineItemRow";
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
  { key: "tasks", label: "Tasks" },
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
  const { data: events = [], isRefetching, refetch } = useUnifiedTimeline(patientId);

  // Filter events
  const filteredEvents = useMemo(() => {
    if (selectedFilter === "all") return events;
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

  return (
    <View style={styles.container}>
      <PatientScreenHeader
        title="Care Timeline"
        subtitle="Your complete chronological health history"
        onPressAssist={onOpenAssist}
      />

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
            <Text style={styles.emptyIcon} allowFontScaling>
              📅
            </Text>
            <Text style={styles.emptyTitle} allowFontScaling>
              No timeline records
            </Text>
            <Text style={styles.emptySubtitle} allowFontScaling>
              {selectedFilter === "all"
                ? "Your glucose readings, meals, and completed care tasks will appear here in chronological order."
                : `No ${selectedFilter} entries found. New entries will show up here.`}
            </Text>
          </View>
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
                  onPress={onSelectEvent}
                />
              ))}
            </View>
          ))
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  filterContainer: {
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingVertical: spacing.xs,
  },
  filterScroll: {
    paddingHorizontal: spacing.md,
    gap: spacing.xs,
  },
  filterChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: "#F4F6F7",
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: 34,
    alignItems: "center",
    justifyContent: "center",
  },
  filterChipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
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
    fontWeight: typography.weight.bold,
    color: colors.textSecondary,
    letterSpacing: 1.2,
  },
  groupLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.border,
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.xxl,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: spacing.md,
  },
  emptyTitle: {
    fontSize: typography.fontSize.headline,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  emptySubtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.xs,
    textAlign: "center",
    maxWidth: 280,
    lineHeight: 20,
  },
});
