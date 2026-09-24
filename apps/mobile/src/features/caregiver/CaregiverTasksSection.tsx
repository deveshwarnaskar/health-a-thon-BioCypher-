import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { caregiverPalette, caregiverRadii, caregiverShadow } from "./caregiverDesign";
import { EmptyState } from "../../components/primitives/EmptyState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { useCareTasks, useCompleteCareTask } from "../tasks/useCareTasks";
import type { CareTaskResponse } from "../../services/schemas/tasks";

export type CaregiverTasksSectionProps = {
  patientId: string;
  canComplete?: boolean;
  testID?: string;
};

export function CaregiverTasksSection({
  patientId,
  canComplete = true,
  testID,
}: CaregiverTasksSectionProps) {
  const tasksQuery = useCareTasks({ patient_id: patientId });

  const completeMutation = useCompleteCareTask({
    onSuccess: () => {
      void tasksQuery.refetch();
    },
  });

  if (tasksQuery.isLoading) {
    return <LoadingState label="Loading patient care tasks…" />;
  }

  const items = tasksQuery.data?.items ?? [];

  return (
    <View style={styles.container} testID={testID}>
      <View style={styles.header}>
        <View style={styles.headerIcon}>
          <Ionicons name="checkbox" size={18} color={caregiverPalette.purpleDark} />
        </View>
        <View style={styles.headerTitleCol}>
          <Text style={styles.title} allowFontScaling>
            Daily Care & Routine Tasks
          </Text>
          <Text style={styles.subtitle} allowFontScaling>
            Assist patient with medications, hydration & routine check-offs
          </Text>
        </View>
      </View>

      {items.length === 0 ? (
        <EmptyState
          title="No pending tasks"
          message="All daily care tasks for this patient are up to date."
        />
      ) : (
        <View style={styles.taskList}>
          {items.map((task) => (
            <TaskItemCard
              key={task.care_task_id}
              task={task}
              canComplete={canComplete}
              isPending={completeMutation.isPending}
              onComplete={() => completeMutation.mutate(task.care_task_id)}
            />
          ))}
        </View>
      )}
    </View>
  );
}

function TaskItemCard({
  task,
  canComplete,
  isPending,
  onComplete,
}: {
  task: CareTaskResponse;
  canComplete: boolean;
  isPending: boolean;
  onComplete: () => void;
}) {
  const isDone = task.status === "completed";

  return (
    <View style={[styles.taskCard, isDone && styles.taskCardDone]}>
      <View style={styles.taskContent}>
        <View style={styles.taskTitleRow}>
          <Text style={[styles.taskTitle, isDone && styles.taskTitleDone]} allowFontScaling>
            {task.description}
          </Text>
          <View
            style={[
              styles.statusBadge,
              isDone ? styles.badgeDone : styles.badgePending,
            ]}
          >
            <Text
              style={[
                styles.statusText,
                isDone ? styles.textDone : styles.textPending,
              ]}
              allowFontScaling
            >
              {task.status.toUpperCase()}
            </Text>
          </View>
        </View>

        {task.due_at ? (
          <View style={styles.dueRow}>
            <Ionicons name="time-outline" size={12} color={caregiverPalette.muted} />
            <Text style={styles.dueText} allowFontScaling>
              Due: {new Date(task.due_at).toLocaleDateString()}
            </Text>
          </View>
        ) : null}
      </View>

      {!isDone && canComplete ? (
        <TouchableOpacity
          style={styles.checkButton}
          onPress={onComplete}
          disabled={isPending}
          activeOpacity={0.8}
          accessibilityRole="button"
          accessibilityLabel={`Complete task: ${task.description}`}
        >
          <Ionicons name="checkmark" size={15} color="#FFFFFF" />
          <Text style={styles.checkButtonText} allowFontScaling>
            Mark Done
          </Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 12,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 2,
  },
  headerIcon: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: caregiverPalette.purpleSoft,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: caregiverPalette.purpleBorder,
  },
  headerTitleCol: {
    flex: 1,
  },
  title: {
    fontSize: 16,
    fontWeight: "800",
    color: caregiverPalette.ink,
  },
  subtitle: {
    fontSize: 11,
    color: caregiverPalette.muted,
    marginTop: 1,
  },
  taskList: {
    gap: 10,
  },
  taskCard: {
    backgroundColor: caregiverPalette.surface,
    borderRadius: caregiverRadii.md,
    padding: 14,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    ...caregiverShadow.subtle,
  },
  taskCardDone: {
    backgroundColor: caregiverPalette.surfaceMuted,
    opacity: 0.8,
  },
  taskContent: {
    flex: 1,
    gap: 4,
  },
  taskTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 6,
  },
  taskTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: caregiverPalette.ink,
    flex: 1,
  },
  taskTitleDone: {
    textDecorationLine: "line-through",
    color: caregiverPalette.muted,
  },
  statusBadge: {
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: caregiverRadii.pill,
  },
  badgePending: {
    backgroundColor: caregiverPalette.amberSoft,
    borderWidth: 1,
    borderColor: caregiverPalette.amberBorder,
  },
  badgeDone: {
    backgroundColor: caregiverPalette.emeraldSoft,
    borderWidth: 1,
    borderColor: caregiverPalette.emeraldBorder,
  },
  statusText: {
    fontSize: 9,
    fontWeight: "800",
  },
  textPending: {
    color: caregiverPalette.amberDark,
  },
  textDone: {
    color: caregiverPalette.emeraldDark,
  },
  dueRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginTop: 2,
  },
  dueText: {
    fontSize: 11,
    color: caregiverPalette.muted,
  },
  checkButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: caregiverPalette.emerald,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: caregiverRadii.sm,
  },
  checkButtonText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "700",
  },
});
