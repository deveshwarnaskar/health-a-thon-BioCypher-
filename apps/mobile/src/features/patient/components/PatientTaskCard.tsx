import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, typography } from "../../../theming/tokens";
import type { CareTaskResponse } from "../../../services/schemas/tasks";

export type PatientTaskCardProps = {
  task: CareTaskResponse;
  onPress?: (task: CareTaskResponse) => void;
  onComplete?: (taskId: string) => void;
  isCompleting?: boolean;
};

export function PatientTaskCard({
  task,
  onPress,
  onComplete,
  isCompleting = false,
}: PatientTaskCardProps) {
  const isCompleted = task.status === "completed";

  const formattedTime = task.due_at
    ? new Date(task.due_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : null;

  return (
    <TouchableOpacity
      style={[styles.card, isCompleted && styles.cardCompleted]}
      onPress={() => onPress?.(task)}
      activeOpacity={0.7}
      accessibilityRole="button"
      accessibilityLabel={`Task: ${task.description}, status: ${task.status}`}
    >
      <View style={styles.leftColumn}>
        <TouchableOpacity
          style={[
            styles.checkCircle,
            isCompleted ? styles.checkCircleCompleted : styles.checkCirclePending,
            isCompleting && styles.checkCircleBusy,
          ]}
          onPress={() => {
            if (!isCompleted && onComplete) {
              onComplete(task.care_task_id);
            }
          }}
          disabled={isCompleted || isCompleting}
          accessibilityRole="checkbox"
          accessibilityState={{ checked: isCompleted }}
          accessibilityLabel={isCompleted ? "Completed" : "Tap to complete task"}
        >
          {isCompleted ? (
            <Ionicons name="checkmark" size={16} color="#FFFFFF" />
          ) : null}
        </TouchableOpacity>

        <View style={styles.contentColumn}>
          <Text
            style={[styles.description, isCompleted && styles.descriptionCompleted]}
            allowFontScaling
            numberOfLines={2}
          >
            {task.description}
          </Text>

          <View style={styles.metaRow}>
            <View style={styles.timeRow}>
              <Ionicons name="time-outline" size={12} color="#64748B" style={{ marginRight: 3 }} />
              <Text style={styles.timeText} allowFontScaling>
                {isCompleted ? "Completed" : formattedTime ? `Due ${formattedTime}` : "Scheduled"}
              </Text>
            </View>

            <View
              style={[
                styles.badge,
                isCompleted ? styles.badgeCompleted : styles.badgePending,
              ]}
            >
              <Text
                style={[
                  styles.badgeText,
                  isCompleted ? styles.badgeTextCompleted : styles.badgeTextPending,
                ]}
                allowFontScaling
              >
                {task.status.replace("_", " ").toUpperCase()}
              </Text>
            </View>
          </View>
        </View>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 2,
  },
  cardCompleted: {
    backgroundColor: "#F8FAFC",
    borderColor: "#E2E8F0",
    opacity: 0.85,
  },
  leftColumn: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  checkCircle: {
    width: 26,
    height: 26,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.sm,
    marginTop: 2,
  },
  checkCirclePending: {
    borderWidth: 2,
    borderColor: "#0D9488",
    backgroundColor: "transparent",
  },
  checkCircleCompleted: {
    backgroundColor: "#10B981",
    borderWidth: 0,
  },
  checkCircleBusy: {
    opacity: 0.5,
  },
  contentColumn: {
    flex: 1,
  },
  description: {
    fontSize: 15,
    fontWeight: "600",
    color: "#0F172A",
    lineHeight: 20,
  },
  descriptionCompleted: {
    color: "#94A3B8",
    textDecorationLine: "line-through",
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  timeRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  timeText: {
    fontSize: 12,
    color: "#64748B",
    fontWeight: "500",
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  badgePending: {
    backgroundColor: "#FEF3C7",
  },
  badgeCompleted: {
    backgroundColor: "#ECFDF5",
  },
  badgeText: {
    fontSize: 10,
    fontWeight: "700",
  },
  badgeTextPending: {
    color: "#D97706",
  },
  badgeTextCompleted: {
    color: "#059669",
  },
});
