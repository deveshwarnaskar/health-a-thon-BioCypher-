import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { AppCard } from "../../components/primitives/AppCard";
import { Badge, type BadgeTone } from "../../components/primitives/Badge";
import { colors, spacing, typography } from "../../theming/tokens";
import type { CareTaskResponse, CareTaskStatus } from "../../services/schemas/tasks";

export type CareTaskCardProps = {
  task: CareTaskResponse;
  onPress?: (task: CareTaskResponse) => void;
  patientName?: string;
  testID?: string;
};

const statusConfig: Record<CareTaskStatus, { label: string; tone: BadgeTone }> = {
  open: { label: "Open", tone: "info" },
  in_progress: { label: "In Progress", tone: "warning" },
  completed: { label: "Completed", tone: "success" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

export function CareTaskCard({ task, onPress, patientName, testID }: CareTaskCardProps) {
  const config = statusConfig[task.status] ?? { label: task.status, tone: "neutral" };
  const formattedDueDate = task.due_at ? new Date(task.due_at).toLocaleDateString() : null;

  return (
    <AppCard
      onPress={onPress ? () => onPress(task) : undefined}
      accessibilityLabel={`Task: ${task.description}, Status: ${config.label}${
        formattedDueDate ? `, Due: ${formattedDueDate}` : ""
      }`}
      style={styles.card}
    >
      <View style={styles.header} testID={testID}>
        <Badge label={config.label} tone={config.tone} />
        {formattedDueDate ? (
          <Text style={styles.dueText} allowFontScaling>
            Due: {formattedDueDate}
          </Text>
        ) : null}
      </View>

      <Text style={styles.description} numberOfLines={3} allowFontScaling>
        {task.description}
      </Text>

      {patientName ? (
        <Text style={styles.patientInfo} allowFontScaling>
          Patient: {patientName}
        </Text>
      ) : (
        <Text style={styles.patientId} allowFontScaling>
          Patient ID: {task.patient_id.slice(0, 8)}…
        </Text>
      )}
    </AppCard>
  );
}

const styles = StyleSheet.create({
  card: {
    marginVertical: spacing.xs,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  dueText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  description: {
    fontSize: typography.fontSize.body,
    color: colors.textPrimary,
    fontWeight: "600",
    marginVertical: spacing.xxs,
  },
  patientInfo: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  patientId: {
    fontSize: typography.fontSize.caption,
    color: colors.disabled,
    fontFamily: "monospace",
  },
});
