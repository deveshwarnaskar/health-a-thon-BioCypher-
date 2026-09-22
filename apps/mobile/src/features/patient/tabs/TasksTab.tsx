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
import { colors, radii, spacing, typography } from "../../../theming/tokens";
import { PatientScreenHeader } from "../components/PatientScreenHeader";
import { PatientTaskCard } from "../components/PatientTaskCard";
import { useCareTasks, useCompleteCareTask } from "../../tasks/useCareTasks";
import type { CareTaskResponse } from "../../../services/schemas/tasks";

export type TasksTabProps = {
  patientId: string | null;
  onSelectTask?: (task: CareTaskResponse) => void;
  onOpenAssist?: () => void;
};

type TaskCategory = "today" | "upcoming" | "completed";

export function TasksTab({ patientId, onSelectTask, onOpenAssist }: TasksTabProps) {
  const [selectedCategory, setSelectedCategory] = useState<TaskCategory>("today");

  const { data: tasksData, isRefetching, refetch } = useCareTasks({
    patient_id: patientId ?? undefined,
  });

  const completeMutation = useCompleteCareTask();

  // Partition tasks into Today, Upcoming, and Completed
  const { todayTasks, upcomingTasks, completedTasks } = useMemo(() => {
    const allTasks = tasksData?.items || [];
    const today: CareTaskResponse[] = [];
    const upcoming: CareTaskResponse[] = [];
    const completed: CareTaskResponse[] = [];

    const now = new Date();
    const todayEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);

    for (const t of allTasks) {
      if (t.status === "completed") {
        completed.push(t);
      } else if (!t.due_at) {
        today.push(t);
      } else {
        const due = new Date(t.due_at);
        if (due <= todayEnd) {
          today.push(t);
        } else {
          upcoming.push(t);
        }
      }
    }

    return { todayTasks: today, upcomingTasks: upcoming, completedTasks: completed };
  }, [tasksData?.items]);

  const activeList =
    selectedCategory === "today"
      ? todayTasks
      : selectedCategory === "upcoming"
      ? upcomingTasks
      : completedTasks;

  const handleCompleteTask = (taskId: string) => {
    completeMutation.mutate(taskId);
  };

  return (
    <View style={styles.container}>
      <PatientScreenHeader
        title="Care Tasks"
        subtitle="Activities scheduled by your care team"
        onPressAssist={onOpenAssist}
      />

      {/* Segmented Control */}
      <View style={styles.segmentedControl} accessibilityRole="tablist">
        <TouchableOpacity
          style={[styles.segment, selectedCategory === "today" && styles.segmentActive]}
          onPress={() => setSelectedCategory("today")}
          accessibilityRole="tab"
          accessibilityState={{ selected: selectedCategory === "today" }}
          accessibilityLabel={`Today's tasks (${todayTasks.length})`}
        >
          <Text
            style={[styles.segmentText, selectedCategory === "today" && styles.segmentTextActive]}
            allowFontScaling
          >
            Today ({todayTasks.length})
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.segment, selectedCategory === "upcoming" && styles.segmentActive]}
          onPress={() => setSelectedCategory("upcoming")}
          accessibilityRole="tab"
          accessibilityState={{ selected: selectedCategory === "upcoming" }}
          accessibilityLabel={`Upcoming tasks (${upcomingTasks.length})`}
        >
          <Text
            style={[styles.segmentText, selectedCategory === "upcoming" && styles.segmentTextActive]}
            allowFontScaling
          >
            Upcoming ({upcomingTasks.length})
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.segment, selectedCategory === "completed" && styles.segmentActive]}
          onPress={() => setSelectedCategory("completed")}
          accessibilityRole="tab"
          accessibilityState={{ selected: selectedCategory === "completed" }}
          accessibilityLabel={`Completed tasks (${completedTasks.length})`}
        >
          <Text
            style={[styles.segmentText, selectedCategory === "completed" && styles.segmentTextActive]}
            allowFontScaling
          >
            Completed ({completedTasks.length})
          </Text>
        </TouchableOpacity>
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
        {activeList.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Ionicons
              name={selectedCategory === "completed" ? "clipboard-outline" : "checkmark-circle-outline"}
              size={44}
              color={colors.disabled}
              style={{ marginBottom: 12 }}
            />
            <Text style={styles.emptyTitle} allowFontScaling>
              {selectedCategory === "completed" ? "No completed tasks yet" : "You're all caught up"}
            </Text>
            <Text style={styles.emptySubtitle} allowFontScaling>
              {selectedCategory === "completed"
                ? "Tasks you complete will appear here for reference."
                : "No pending care tasks scheduled for this period."}
            </Text>
          </View>
        ) : (
          activeList.map((task) => (
            <PatientTaskCard
              key={task.care_task_id}
              task={task}
              onPress={onSelectTask}
              onComplete={handleCompleteTask}
              isCompleting={completeMutation.isPending}
            />
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
  segmentedControl: {
    flexDirection: "row",
    backgroundColor: colors.background,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.xs,
  },
  segment: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "#FFFFFF",
  },
  segmentActive: {
    backgroundColor: colors.primaryInk,
  },
  segmentText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.medium,
    color: colors.textSecondary,
  },
  segmentTextActive: {
    color: colors.textOnPrimary,
    fontWeight: typography.weight.bold,
  },
  content: {
    padding: spacing.md,
    paddingBottom: 100,
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl,
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#FFFFFF",
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
  },
});
