import React, { useState } from "react";
import { StyleSheet, Text, View, ScrollView, Pressable, TextInput } from "react-native";
import { useCareTasks } from "./useCareTasks";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { LoadingState } from "../../components/primitives/LoadingState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { EmptyState } from "../../components/primitives/EmptyState";
import { spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import type { PatientSummaryResponse } from "../../services/schemas/patients";

export type CareTasksWorkspaceProps = {
  patients: PatientSummaryResponse[];
  onOpenPatientById?: (patientId: string) => void;
};

export function CareTasksWorkspace({ patients, onOpenPatientById }: CareTasksWorkspaceProps) {
  const {
    tasks,
    taskCount,
    isLoading,
    isError,
    refetch,
    createTask,
    isCreating,
    startTask,
    isStarting,
    completeTask,
    isCompleting,
  } = useCareTasks();

  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTaskPatientId, setNewTaskPatientId] = useState<string>(patients[0]?.patient_id ?? "");
  const [newTaskDescription, setNewTaskDescription] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const filteredTasks = tasks.filter((t) => {
    if (statusFilter === "all") return true;
    return t.status === statusFilter;
  });

  const handleCreate = async () => {
    if (!newTaskPatientId || !newTaskDescription.trim()) return;
    setCreateError(null);
    try {
      await createTask({
        patient_id: newTaskPatientId,
        assigned_to_user_id: newTaskPatientId,
        description: newTaskDescription.trim(),
      });
      setNewTaskDescription("");
      setShowCreateModal(false);
    } catch (err: any) {
      setCreateError(err?.message || "Failed to create care task.");
    }
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Care Plan Tasks</Text>
          <Text style={styles.subtitle}>
            Facility clinical workflows, intervention follow-ups, and field tasks ({taskCount} total)
          </Text>
        </View>
        <View style={styles.headerButtons}>
          <Button
            label="+ New Care Task"
            variant="primary"
            onPress={() => setShowCreateModal(true)}
          />
          <Button label="Refresh" variant="outline" onPress={() => refetch()} />
        </View>
      </View>

      {/* Filter Tabs */}
      <View style={styles.filterRow}>
        {["all", "open", "in_progress", "completed"].map((st) => (
          <Pressable
            key={st}
            style={[styles.filterChip, statusFilter === st ? styles.filterChipActive : null]}
            onPress={() => setStatusFilter(st)}
          >
            <Text style={[styles.filterText, statusFilter === st ? styles.filterTextActive : null]}>
              {st === "all" ? `All (${taskCount})` : st.replace("_", " ")}
            </Text>
          </Pressable>
        ))}
      </View>

      {/* Create Modal */}
      {showCreateModal ? (
        <View style={styles.createCard}>
          <Text style={styles.createTitle}>Create New Care Task</Text>

          <View style={styles.formGroup}>
            <Text style={styles.formLabel}>Target Patient:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.patientRow}>
              {patients.map((p) => (
                <Pressable
                  key={p.patient_id}
                  style={[
                    styles.patientChip,
                    newTaskPatientId === p.patient_id ? styles.patientChipActive : null,
                  ]}
                  onPress={() => setNewTaskPatientId(p.patient_id)}
                >
                  <Text
                    style={[
                      styles.patientChipText,
                      newTaskPatientId === p.patient_id ? styles.patientChipTextActive : null,
                    ]}
                  >
                    {p.name}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
          </View>

          <View style={styles.formGroup}>
            <Text style={styles.formLabel}>Task Description / Directive:</Text>
            <TextInput
              style={styles.textInput}
              placeholder="e.g. Schedule fasting glucose verification and post-meal SMBG audit"
              placeholderTextColor={doctorPalette.quiet}
              value={newTaskDescription}
              onChangeText={setNewTaskDescription}
            />
          </View>

          {createError ? <Text style={styles.errorText}>{createError}</Text> : null}

          <View style={styles.createBtnRow}>
            <Button
              label={isCreating ? "Creating…" : "Save Task"}
              variant="primary"
              disabled={isCreating || !newTaskDescription.trim()}
              onPress={handleCreate}
            />
            <Button
              label="Cancel"
              variant="ghost"
              onPress={() => setShowCreateModal(false)}
            />
          </View>
        </View>
      ) : null}

      {/* Main List */}
      {isLoading ? (
        <LoadingState label="Loading care tasks…" />
      ) : isError ? (
        <ErrorState
          title="Could not load care tasks"
          message="Please check facility network connection."
          onRetry={() => refetch()}
        />
      ) : filteredTasks.length === 0 ? (
        <EmptyState
          title="No care tasks"
          message="No tasks match the selected status filter."
        />
      ) : (
        <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
          {filteredTasks.map((task) => {
            const patientObj = patients.find((p) => p.patient_id === task.patient_id);
            return (
              <View key={task.care_task_id} style={styles.taskCard}>
                <View style={styles.taskCardHeader}>
                  <View style={styles.taskHeaderLeft}>
                    <Badge
                      label={task.status.replace("_", " ").toUpperCase()}
                      tone={
                        task.status === "completed"
                          ? "success"
                          : task.status === "in_progress"
                          ? "warning"
                          : "neutral"
                      }
                    />
                    <Text style={styles.taskPatientName}>
                      {patientObj ? patientObj.name : `Patient ${task.patient_id.slice(0, 8)}…`}
                    </Text>
                  </View>
                  <Text style={styles.taskDate}>
                    {new Date(task.created_at).toLocaleDateString()}
                  </Text>
                </View>

                <Text style={styles.taskDescription}>{task.description}</Text>

                <View style={styles.taskFooter}>
                  <View style={styles.taskFooterMeta}>
                    <Text style={styles.taskMetaText}>Task ID: {task.care_task_id.slice(0, 8)}…</Text>
                    {onOpenPatientById ? (
                      <Pressable onPress={() => onOpenPatientById(task.patient_id)}>
                        <Text style={styles.openPatientLink}>Open Patient</Text>
                      </Pressable>
                    ) : null}
                  </View>

                  <View style={styles.taskActionBtns}>
                    {task.status === "open" ? (
                      <Button
                        label={isStarting ? "Starting…" : "Start Task"}
                        variant="outline"
                        disabled={isStarting}
                        onPress={() => startTask(task.care_task_id)}
                      />
                    ) : null}

                    {task.status === "in_progress" ? (
                      <Button
                        label={isCompleting ? "Completing…" : "Mark Complete"}
                        variant="primary"
                        disabled={isCompleting}
                        onPress={() => completeTask(task.care_task_id)}
                      />
                    ) : null}
                  </View>
                </View>
              </View>
            );
          })}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  title: {
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  subtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.muted,
    fontWeight: "600",
  },
  headerButtons: {
    flexDirection: "row",
    gap: spacing.sm,
    flexWrap: "wrap",
  },
  filterRow: {
    flexDirection: "row",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    backgroundColor: doctorPalette.surface,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.border,
    flexWrap: "wrap",
  },
  filterChip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
  },
  filterChipActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.surfaceLime,
  },
  filterText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
    fontWeight: "700",
    textTransform: "capitalize",
  },
  filterTextActive: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  createCard: {
    margin: spacing.lg,
    marginBottom: 0,
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.md,
    gap: spacing.md,
    ...doctorSoftShadow,
  },
  createTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  formGroup: {
    gap: 4,
  },
  formLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: "700",
    color: doctorPalette.muted,
  },
  patientRow: {
    flexDirection: "row",
  },
  patientChip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    marginRight: 6,
  },
  patientChipActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.surfaceLime,
  },
  patientChipText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
    fontWeight: "700",
  },
  patientChipTextActive: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  textInput: {
    borderWidth: 1,
    borderColor: doctorPalette.border,
    borderRadius: doctorRadii.md,
    padding: spacing.sm,
    fontSize: typography.fontSize.bodySmall,
    backgroundColor: doctorPalette.surfaceSoft,
    color: doctorPalette.ink,
  },
  errorText: {
    color: "#BE185D",
    fontSize: typography.fontSize.caption,
  },
  createBtnRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  taskCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.md,
    gap: spacing.sm,
    ...doctorSoftShadow,
  },
  taskCardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
    flexWrap: "wrap",
  },
  taskHeaderLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  taskPatientName: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  taskDate: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  taskDescription: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.ink,
    lineHeight: 20,
  },
  taskFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: doctorPalette.border,
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  taskFooterMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  taskMetaText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  openPatientLink: {
    fontSize: typography.fontSize.caption,
    fontWeight: "800",
    color: doctorPalette.primary,
    marginLeft: 6,
  },
  taskActionBtns: {
    flexDirection: "row",
    gap: spacing.xs,
  },
});
