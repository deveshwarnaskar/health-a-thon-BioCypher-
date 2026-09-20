import React from "react";
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { PatientScreenHeader } from "../components/PatientScreenHeader";
import { TodaySummaryCard, type TodayItem } from "../components/TodaySummaryCard";
import { DailyCareGrid, type DailyCareItem } from "../components/DailyCareGrid";
import { TimelineItemRow } from "../components/TimelineItemRow";
import { useGlucoseFeed } from "../../glucose/useGlucoseFeed";
import { usePatientMeals } from "../../meals/usePatientMeals";
import { usePatientMedications, useUnifiedTimeline, usePatientNotifications } from "../api";
import { useCareTasks } from "../../tasks/useCareTasks";

export type HomeTabProps = {
  patientId: string | null;
  patientName?: string;
  onNavigateToRecord: (type?: "glucose" | "meal" | "medication" | "task") => void;
  onNavigateToTimeline: () => void;
  onNavigateToTasks: () => void;
  onNavigateToMedications: () => void;
  onOpenNotifications: () => void;
  onOpenAssist: () => void;
  onSignOut?: () => void;
};

export function HomeTab({
  patientId,
  patientName,
  onNavigateToRecord,
  onNavigateToTimeline,
  onNavigateToTasks,
  onNavigateToMedications,
  onOpenNotifications,
  onOpenAssist,
  onSignOut,
}: HomeTabProps) {
  const glucoseFeed = useGlucoseFeed(patientId);
  const mealsFeed = usePatientMeals(patientId);
  const medicationsQuery = usePatientMedications(patientId);
  const tasksQuery = useCareTasks({ patient_id: patientId ?? undefined });
  const timelineQuery = useUnifiedTimeline(patientId);
  const notificationsQuery = usePatientNotifications(patientId);

  const [isRefreshing, setIsRefreshing] = React.useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([
        glucoseFeed.refetch(),
        mealsFeed.refetch(),
        medicationsQuery.refetch(),
        tasksQuery.refetch(),
        timelineQuery.refetch(),
        notificationsQuery.refetch(),
      ]);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Derive today's state
  const latestGlucose = glucoseFeed.readings?.[0];
  const mealCountToday = mealsFeed.meals?.length || 0;
  const plans = medicationsQuery.data || [];
  const firstPlan = plans[0];
  const activeTasks = tasksQuery.data?.items || [];
  const pendingTasks = activeTasks.filter((t) => t.status !== "completed");

  const unreadNotifications = (notificationsQuery.data || []).filter(
    (n) => n.status !== "delivered" && n.status !== "cancelled"
  ).length;

  // Build Today attention items
  const todayItems: TodayItem[] = [];

  // 1. Medication
  if (firstPlan) {
    todayItems.push({
      id: "med-1",
      label: `Medication (${firstPlan.medication})`,
      status: "due",
      time: "Scheduled",
    });
  }

  // 2. Glucose
  if (latestGlucose) {
    const timeStr = new Date(latestGlucose.taken_at).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    todayItems.push({
      id: "glucose-1",
      label: `Glucose reading (${latestGlucose.value_mg_dl ?? "--"} mg/dL)`,
      status: "completed",
      time: timeStr,
    });
  } else {
    todayItems.push({
      id: "glucose-1",
      label: "Record morning glucose",
      status: "due",
      time: "Fasting",
    });
  }

  // 3. Breakfast / Meal
  if (mealCountToday > 0) {
    todayItems.push({
      id: "meal-1",
      label: "Meal logged",
      status: "completed",
      time: "Today",
    });
  } else {
    todayItems.push({
      id: "meal-1",
      label: "Log meal",
      status: "due",
      time: "Due",
    });
  }

  // 4. Daily Care Grid
  const dailyCareItems: DailyCareItem[] = [
    {
      id: "glucose",
      category: "glucose",
      title: "Blood Glucose",
      value: latestGlucose ? `${latestGlucose.value_mg_dl} mg/dL` : "No reading",
      subtext: latestGlucose
        ? `${latestGlucose.tag?.replace("_", " ").toLowerCase() || "reading"}`
        : "Tap to record",
      icon: "🩸",
      statusBadge: latestGlucose ? "Recorded" : "Due",
      onPress: () => onNavigateToRecord("glucose"),
    },
    {
      id: "meals",
      category: "meals",
      title: "Meals Logged",
      value: `${mealCountToday} logged`,
      subtext: mealCountToday > 0 ? "Today's nutrition" : "Tap to record meal",
      icon: "🍲",
      statusBadge: mealCountToday > 0 ? "Active" : undefined,
      onPress: () => onNavigateToRecord("meal"),
    },
    {
      id: "medication",
      category: "medication",
      title: "Medication",
      value: plans.length > 0 ? `${plans.length} prescribed` : "None active",
      subtext: plans.length > 0 ? "Clinician-authored" : "No active plans",
      icon: "💊",
      statusBadge: plans.length > 0 ? "Scheduled" : undefined,
      onPress: onNavigateToMedications,
    },
    {
      id: "tasks",
      category: "tasks",
      title: "Care Tasks",
      value: `${pendingTasks.length} remaining`,
      subtext: `${activeTasks.length - pendingTasks.length} completed today`,
      icon: "📋",
      statusBadge: pendingTasks.length === 0 ? "✓ Caught up" : undefined,
      onPress: onNavigateToTasks,
    },
  ];

  // Recent activity (top 3 timeline events)
  const recentEvents = (timelineQuery.data || []).slice(0, 3);

  return (
    <View style={styles.container}>
      <PatientScreenHeader
        patientName={patientName}
        showGreeting={true}
        role="Patient"
        unreadNotificationsCount={unreadNotifications}
        onPressNotifications={onOpenNotifications}
        onPressAssist={onOpenAssist}
        onSignOut={onSignOut}
      />

      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            tintColor={colors.primary}
            colors={[colors.primary]}
          />
        }
      >
        {/* Section 1: Today Summary Card */}
        <TodaySummaryCard items={todayItems} />

        {/* Section 2: Daily Care Cards */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle} allowFontScaling>
            Daily Care
          </Text>
          <DailyCareGrid items={dailyCareItems} />
        </View>

        {/* Section 3: Upcoming Reminder Banner */}
        {firstPlan ? (
          <View style={styles.upcomingBox}>
            <View style={styles.upcomingHeaderRow}>
              <Text style={styles.upcomingKicker} allowFontScaling>
                NEXT SCHEDULED
              </Text>
              <Text style={styles.upcomingTime} allowFontScaling>
                Evening
              </Text>
            </View>
            <Text style={styles.upcomingTitle} allowFontScaling>
              {firstPlan.medication}
            </Text>
            <Text style={styles.upcomingSubtitle} allowFontScaling>
              {firstPlan.instruction || "Take with water as prescribed"}
            </Text>
            <TouchableOpacity
              style={styles.upcomingAction}
              onPress={onNavigateToMedications}
              accessibilityRole="button"
              accessibilityLabel={`View details for ${firstPlan.medication}`}
            >
              <Text style={styles.upcomingActionText} allowFontScaling>
                View Medication Plan →
              </Text>
            </TouchableOpacity>
          </View>
        ) : null}

        {/* Section 4: Recent Activity */}
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Text style={styles.sectionTitle} allowFontScaling>
              Recent Activity
            </Text>
            <TouchableOpacity
              onPress={onNavigateToTimeline}
              accessibilityRole="button"
              accessibilityLabel="View all care timeline activity"
            >
              <Text style={styles.seeAllLink} allowFontScaling>
                See all →
              </Text>
            </TouchableOpacity>
          </View>

          {recentEvents.length === 0 ? (
            <View style={styles.emptyRecentBox}>
              <Text style={styles.emptyRecentText} allowFontScaling>
                No readings or meals recorded yet today.
              </Text>
              <TouchableOpacity
                style={styles.quickRecordButton}
                onPress={() => onNavigateToRecord()}
                accessibilityRole="button"
                accessibilityLabel="Record your first health entry"
              >
                <Text style={styles.quickRecordButtonText} allowFontScaling>
                  Record an Entry
                </Text>
              </TouchableOpacity>
            </View>
          ) : (
            recentEvents.map((event) => (
              <TimelineItemRow
                key={event.id}
                event={event}
                onPress={onNavigateToTimeline}
              />
            ))
          )}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    gap: spacing.lg,
  },
  section: {
    gap: spacing.sm,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionTitle: {
    fontSize: typography.fontSize.headline,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  seeAllLink: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.semibold,
    color: colors.primary,
  },
  upcomingBox: {
    backgroundColor: "#FDF9F5",
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "#FAD7A0",
    padding: spacing.md,
  },
  upcomingHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  upcomingKicker: {
    fontSize: 10,
    fontWeight: typography.weight.bold,
    color: colors.assistive,
    letterSpacing: 1,
  },
  upcomingTime: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.semibold,
    color: colors.textSecondary,
  },
  upcomingTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  upcomingSubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: 2,
    marginBottom: spacing.xs,
  },
  upcomingAction: {
    marginTop: spacing.xs,
  },
  upcomingActionText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.assistive,
  },
  emptyRecentBox: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    alignItems: "center",
  },
  emptyRecentText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  quickRecordButton: {
    backgroundColor: colors.primary,
    borderRadius: radii.md,
    minHeight: touchTarget.min,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    justifyContent: "center",
  },
  quickRecordButtonText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.semibold,
  },
});
