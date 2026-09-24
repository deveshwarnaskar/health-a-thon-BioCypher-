import React, { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { Badge, type BadgeTone } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { LoadingState } from "../../components/primitives/LoadingState";
import { Divider } from "../../components/primitives/Divider";
import { colors, spacing, typography } from "../../theming/tokens";
import {
  useCareTaskDetail,
  useTaskPatient,
  useStartCareTask,
  useCompleteCareTask,
} from "./useCareTasks";
import type { CareTaskStatus } from "../../services/schemas/tasks";
import type { ApiErrorDetails } from "../../services/api/errors";

export type CareTaskDetailScreenProps = {
  taskId: string;
  onBack?: () => void;
  onReassign?: (taskId: string) => void;
  onRecordGlucose?: (patientId: string) => void;
  onLogMeal?: (patientId: string) => void;
  isCoordinator?: boolean;
  isFhw?: boolean;
  testID?: string;
};

const statusConfig: Record<CareTaskStatus, { label: string; tone: BadgeTone }> = {
  open: { label: "Open", tone: "info" },
  in_progress: { label: "In Progress", tone: "warning" },
  completed: { label: "Completed", tone: "success" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

export function CareTaskDetailScreen({
  taskId,
  onBack,
  onReassign,
  onRecordGlucose,
  onLogMeal,
  isCoordinator = false,
  isFhw = false,
  testID,
}: CareTaskDetailScreenProps) {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const { data: task, isLoading: isTaskLoading, error: taskError } = useCareTaskDetail(taskId);
  const { data: patient, isLoading: isPatientLoading, error: patientError } = useTaskPatient(
    task?.patient_id,
    { enabled: Boolean(task?.patient_id) }
  );

  const startTaskMutation = useStartCareTask({
    onSuccess: () => {
      setErrorMessage(null);
      setSuccessMessage("Task started successfully.");
    },
    onError: (err) => {
      setSuccessMessage(null);
      const apiErr = err as ApiErrorDetails | undefined;
      if (apiErr?.httpStatus === 403) {
        setErrorMessage("You are not authorized to start this task.");
      } else if (apiErr?.httpStatus === 409) {
        setErrorMessage("Task could not be started due to a state conflict. Refreshing…");
      } else {
        setErrorMessage(apiErr?.message || "Failed to start task.");
      }
    },
  });

  const completeTaskMutation = useCompleteCareTask({
    onSuccess: () => {
      setErrorMessage(null);
      setSuccessMessage("Task completed successfully.");
    },
    onError: (err) => {
      setSuccessMessage(null);
      const apiErr = err as ApiErrorDetails | undefined;
      if (apiErr?.httpStatus === 403) {
        setErrorMessage("You are not authorized to complete this task.");
      } else if (apiErr?.httpStatus === 409) {
        setErrorMessage("Task could not be completed due to a state conflict. Refreshing…");
      } else {
        setErrorMessage(apiErr?.message || "Failed to complete task.");
      }
    },
  });

  if (isTaskLoading) {
    return <LoadingState label="Loading task details…" testID={testID ? `${testID}-loading` : undefined} />;
  }

  if (taskError || !task) {
    const is403 = (taskError as ApiErrorDetails)?.httpStatus === 403;
    const is404 = (taskError as ApiErrorDetails)?.httpStatus === 404;
    return (
      <View style={styles.container} testID={testID ? `${testID}-error` : undefined}>
        <TopAppBar title="Task Details" onBack={onBack} />
        <View style={styles.content}>
          <AlertBanner
            title={is403 ? "Access Denied" : is404 ? "Not Found" : "Error"}
            message={
              is403
                ? "You do not have permission to view this task."
                : is404
                ? "Task not found or no longer exists."
                : "Unable to load task details."
            }
            tone={is403 ? "warning" : "critical"}
          />
          <Button label="Back" variant="outline" onPress={onBack ?? (() => {})} style={styles.backBtn} />
        </View>
      </View>
    );
  }

  const isPatientInactive = patient && !patient.active;
  const config = statusConfig[task.status] ?? { label: task.status, tone: "neutral" };
  const canStart = task.status === "open" && !isPatientInactive;
  const canComplete = (task.status === "in_progress" || task.status === "open") && !isPatientInactive;
  const canReassign =
    isCoordinator && (task.status === "open" || task.status === "in_progress") && !isPatientInactive;

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar title="Task Details" onBack={onBack} />

      <ScrollView contentContainerStyle={styles.content}>
        {errorMessage ? (
          <AlertBanner
            title="Action Error"
            message={errorMessage}
            tone="critical"
          />
        ) : null}

        {successMessage ? (
          <AlertBanner
            title="Success"
            message={successMessage}
            tone="success"
          />
        ) : null}

        {isPatientInactive ? (
          <AlertBanner
            title="Inactive Patient"
            message="This patient record is deactivated. Task actions are locked."
            tone="warning"
          />
        ) : null}

        <View style={styles.statusRow}>
          <Text style={styles.sectionTitle} allowFontScaling>
            Status
          </Text>
          <Badge label={config.label} tone={config.tone} />
        </View>

        <Text style={styles.taskDescription} allowFontScaling>
          {task.description}
        </Text>

        <Divider />

        <View style={styles.infoSection}>
          <Text style={styles.infoHeading} allowFontScaling>
            Patient Context
          </Text>
          {isPatientLoading ? (
            <Text style={styles.infoText} allowFontScaling>
              Resolving patient context…
            </Text>
          ) : patient ? (
            <View style={styles.patientCard}>
              <Text style={styles.patientName} allowFontScaling>
                {patient.name}
              </Text>
              <Text style={styles.patientMeta} allowFontScaling>
                UH-ID: {patient.uh_id}
              </Text>
            </View>
          ) : patientError ? (
            <Text style={styles.errorText} allowFontScaling>
              Patient information unavailable.
            </Text>
          ) : (
            <Text style={styles.infoText} allowFontScaling>
              Patient ID: {task.patient_id}
            </Text>
          )}
        </View>

        <Divider />

        <View style={styles.infoSection}>
          <Text style={styles.infoHeading} allowFontScaling>
            Schedule & Assignment
          </Text>
          {task.due_at ? (
            <Text style={styles.infoText} allowFontScaling>
              Due Date: {new Date(task.due_at).toLocaleString()}
            </Text>
          ) : (
            <Text style={styles.infoText} allowFontScaling>
              Due Date: None specified
            </Text>
          )}
          <Text style={styles.infoText} allowFontScaling>
            Assigned Worker: {task.assigned_to_user_id.slice(0, 8)}…
          </Text>
          <Text style={styles.infoText} allowFontScaling>
            Created: {new Date(task.created_at).toLocaleDateString()}
          </Text>
          {task.completed_at ? (
            <Text style={styles.infoText} allowFontScaling>
              Completed: {new Date(task.completed_at).toLocaleString()}
            </Text>
          ) : null}
        </View>

        <Divider />

        {/* Action Controls */}
        <View style={styles.actionsSection}>
          {canStart ? (
            <Button
              label={startTaskMutation.isPending ? "Starting…" : "Start Task"}
              variant="primary"
              disabled={startTaskMutation.isPending}
              onPress={() => startTaskMutation.mutate(task.care_task_id)}
              testID="start-task-button"
            />
          ) : null}

          {canComplete ? (
            <Button
              label={completeTaskMutation.isPending ? "Completing…" : "Complete Task"}
              variant="primary"
              disabled={completeTaskMutation.isPending}
              onPress={() => completeTaskMutation.mutate(task.care_task_id)}
              testID="complete-task-button"
            />
          ) : null}

          {canReassign ? (
            <Button
              label="Reassign Task"
              variant="outline"
              onPress={() => onReassign?.(task.care_task_id)}
              testID="reassign-task-button"
            />
          ) : null}

          {/* FHW field data capture links */}
          {isFhw && !isPatientInactive && task.status !== "completed" ? (
            <View style={styles.fhwFieldActions}>
              <Text style={styles.fieldActionTitle} allowFontScaling>
                Field Visit Data Capture
              </Text>
              <Button
                label="Record Blood Glucose"
                variant="outline"
                onPress={() => onRecordGlucose?.(task.patient_id)}
                testID="fhw-record-glucose-button"
              />
              <Button
                label="Log Meal Observation"
                variant="outline"
                onPress={() => onLogMeal?.(task.patient_id)}
                testID="fhw-log-meal-button"
              />
            </View>
          ) : null}
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
    gap: spacing.md,
  },
  statusRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionTitle: {
    fontSize: typography.fontSize.title,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  taskDescription: {
    fontSize: typography.fontSize.title,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  infoSection: {
    gap: spacing.xs,
  },
  infoHeading: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textSecondary,
  },
  infoText: {
    fontSize: typography.fontSize.body,
    color: colors.textPrimary,
  },
  patientCard: {
    backgroundColor: colors.surface,
    padding: spacing.sm,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  patientName: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  patientMeta: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  errorText: {
    fontSize: typography.fontSize.caption,
    color: colors.critical,
  },
  actionsSection: {
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  fhwFieldActions: {
    marginTop: spacing.md,
    gap: spacing.sm,
  },
  fieldActionTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: spacing.xxs,
  },
  backBtn: {
    marginTop: spacing.md,
  },
});
