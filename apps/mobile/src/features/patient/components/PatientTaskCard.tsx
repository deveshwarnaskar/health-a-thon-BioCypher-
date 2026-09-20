import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
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
          <Text
            style={[
              styles.checkIcon,
              isCompleted ? styles.checkIconCompleted : styles.checkIconPending,
            ]}
            allowFontScaling
          >
            {isCompleted ? "✓" : ""}
          </Text>
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
            {formattedTime ? (
              <Text style={styles.timeText} allowFontScaling>
                {isCompleted ? "Completed" : `Due ${formattedTime}`}
              </Text>
            ) : (
              <Text style={styles.timeText} allowFontScaling>
                Scheduled
              </Text>
            )}

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
                {task.status.replace("_", " ")}
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
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.07,
    shadowRadius: 16,
    elevation: 2,
  },
  cardCompleted: {
    backgroundColor: colors.backgroundRaised,
    borderColor: "#FFFFFF",
  },
  leftColumn: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  checkCircle: {
    width: 28,
    height: 28,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.sm,
    marginTop: 2,
  },
  checkCirclePending: {
    borderWidth: 2,
    borderColor: colors.primary,
    backgroundColor: "transparent",
  },
  checkCircleCompleted: {
    backgroundColor: colors.leafGreen,
  },
  checkCircleBusy: {
    opacity: 0.5,
  },
  checkIcon: {
    fontSize: 14,
    fontWeight: "bold",
  },
  checkIconPending: {
    color: "transparent",
  },
  checkIconCompleted: {
    color: colors.textOnPrimary,
  },
  contentColumn: {
    flex: 1,
  },
  description: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.medium,
    color: colors.textPrimary,
    lineHeight: typography.lineHeight.body,
  },
  descriptionCompleted: {
    color: colors.textSecondary,
    textDecorationLine: "line-through",
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  timeText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  badge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.sm,
  },
  badgePending: {
    backgroundColor: colors.tileCream,
  },
  badgeCompleted: {
    backgroundColor: colors.tileGreen,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: typography.weight.bold,
  },
  badgeTextPending: {
    color: colors.assistive,
  },
  badgeTextCompleted: {
    color: colors.leafGreen,
  },
});
