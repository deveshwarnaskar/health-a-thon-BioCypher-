import React, { useState } from "react";
import {
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { touchTarget } from "../../../theming/tokens";
import {
  doctorPalette,
  doctorRadii,
  doctorSoftShadow,
  doctorPillShadow,
} from "../doctorDesign";
import { useCareTasks } from "../useCareTasks";
import type { PatientSummaryResponse } from "../../../services/schemas/patients";

export type DoctorTasksTabProps = {
  patients: PatientSummaryResponse[];
  onOpenPatientById?: (patientId: string) => void;
};

export function DoctorTasksTab({ patients, onOpenPatientById }: DoctorTasksTabProps) {
  const {
    tasks,
    taskCount,
    isLoading,
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
  const [newTaskPatientId, setNewTaskPatientId] = useState<string>(
    patients[0]?.patient_id ?? ""
  );
  const [newTaskDescription, setNewTaskDescription] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handlePullToRefresh = async () => {
    setIsRefreshing(true);
    try {
      await refetch();
    } finally {
      setIsRefreshing(false);
    }
  };

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

  const filteredTasks = tasks.filter((t) => {
    if (statusFilter === "all") return true;
    return t.status === statusFilter;
  });

  const getPatientName = (pId: string): string => {
    const found = patients.find((p) => p.patient_id === pId);
    return found ? found.name : `Patient ${pId.slice(0, 6)}`;
  };

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing || isLoading}
            onRefresh={handlePullToRefresh}
            tintColor={doctorPalette.primary}
            colors={[doctorPalette.primary]}
          />
        }
      >
        {/* Header Action Row */}
        <View style={styles.headerRow}>
          <View style={styles.headerTextCol}>
            <Text style={styles.headerTitle} allowFontScaling>
              Care Tasks & Follow-ups
            </Text>
            <Text style={styles.headerSubtitle} allowFontScaling>
              {taskCount} active clinical action{taskCount === 1 ? "" : "s"} across cohort
            </Text>
          </View>
          <TouchableOpacity
            style={styles.newTaskButton}
            onPress={() => setShowCreateModal(true)}
            accessibilityRole="button"
            accessibilityLabel="Create new care task"
            activeOpacity={0.85}
          >
            <Ionicons name="add" size={18} color="#FFFFFF" />
            <Text style={styles.newTaskButtonText} allowFontScaling>
              New Task
            </Text>
          </TouchableOpacity>
        </View>

        {/* Status Filter Chips */}
        <View style={styles.filtersRow}>
          {[
            { key: "all", label: `All (${taskCount})` },
            { key: "open", label: "Open" },
            { key: "in_progress", label: "In Progress" },
            { key: "completed", label: "Completed" },
          ].map((st) => {
            const active = statusFilter === st.key;
            return (
              <Pressable
                key={st.key}
                style={[styles.filterChip, active ? styles.filterChipActive : null]}
                onPress={() => setStatusFilter(st.key)}
                accessibilityRole="button"
                accessibilityLabel={`Filter by ${st.label}`}
              >
                <Text
                  style={[styles.filterChipText, active ? styles.filterChipTextActive : null]}
                  allowFontScaling
                >
                  {st.label}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {/* Task Cards List */}
        {filteredTasks.length > 0 ? (
          <View style={styles.list}>
            {filteredTasks.map((task) => {
              const isDone = task.status === "completed";
              const isInProgress = task.status === "in_progress";
              const patientName = getPatientName(task.patient_id);

              return (
                <View key={task.care_task_id} style={styles.card}>
                  <View style={styles.cardHeader}>
                    <View
                      style={[
                        styles.statusBadge,
                        isDone
                          ? styles.statusBadgeDone
                          : isInProgress
                          ? styles.statusBadgeProgress
                          : styles.statusBadgeOpen,
                      ]}
                    >
                      <Text
                        style={[
                          styles.statusBadgeText,
                          isDone
                            ? styles.statusBadgeTextDone
                            : isInProgress
                            ? styles.statusBadgeTextProgress
                            : styles.statusBadgeTextOpen,
                        ]}
                        allowFontScaling
                      >
                        {task.status.replace("_", " ").toUpperCase()}
                      </Text>
                    </View>

                    <Text style={styles.timestamp} allowFontScaling>
                      {new Date(task.created_at).toLocaleDateString()}
                    </Text>
                  </View>

                  <Text style={styles.descriptionText} allowFontScaling>
                    {task.description}
                  </Text>

                  <View style={styles.cardFooter}>
                    <View style={styles.patientMeta}>
                      <Text style={styles.patientLabel} allowFontScaling>
                        Patient:
                      </Text>
                      <Text style={styles.patientName} numberOfLines={1} allowFontScaling>
                        {patientName}
                      </Text>
                      {onOpenPatientById ? (
                        <TouchableOpacity
                          onPress={() => onOpenPatientById(task.patient_id)}
                          accessibilityRole="button"
                          accessibilityLabel={`View record for ${patientName}`}
                        >
                          <Text style={styles.openPatientText} allowFontScaling>
                            View →
                          </Text>
                        </TouchableOpacity>
                      ) : null}
                    </View>

                    {/* Action buttons */}
                    <View style={styles.actionButtons}>
                      {task.status === "open" ? (
                        <TouchableOpacity
                          style={styles.actionBtnOutline}
                          onPress={() => startTask(task.care_task_id)}
                          disabled={isStarting}
                          accessibilityRole="button"
                          accessibilityLabel="Start this care task"
                        >
                          <Text style={styles.actionBtnOutlineText} allowFontScaling>
                            {isStarting ? "Starting…" : "Start"}
                          </Text>
                        </TouchableOpacity>
                      ) : null}

                      {task.status !== "completed" ? (
                        <TouchableOpacity
                          style={styles.actionBtnPrimary}
                          onPress={() => completeTask(task.care_task_id)}
                          disabled={isCompleting}
                          accessibilityRole="button"
                          accessibilityLabel="Mark care task as complete"
                        >
                          <Text style={styles.actionBtnPrimaryText} allowFontScaling>
                            {isCompleting ? "Saving…" : "Complete"}
                          </Text>
                        </TouchableOpacity>
                      ) : (
                        <View style={styles.completedBadge}>
                          <Ionicons name="checkmark-circle" size={16} color="#15803D" />
                          <Text style={styles.completedBadgeText} allowFontScaling>
                            Completed
                          </Text>
                        </View>
                      )}
                    </View>
                  </View>
                </View>
              );
            })}
          </View>
        ) : (
          <View style={styles.emptyCard}>
            <Ionicons name="calendar-outline" size={36} color={doctorPalette.muted} />
            <Text style={styles.emptyTitle} allowFontScaling>
              No Tasks Found
            </Text>
            <Text style={styles.emptySubtitle} allowFontScaling>
              {statusFilter === "all"
                ? "No care tasks assigned. Tap '+ New Task' above to assign a clinical action."
                : `No tasks currently in "${statusFilter.replace("_", " ")}" status.`}
            </Text>
          </View>
        )}
      </ScrollView>

      {/* Modern Bottom Sheet Modal */}
      <Modal
        visible={showCreateModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowCreateModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <View>
                <Text style={styles.modalTitle} allowFontScaling>
                  Assign Care Task
                </Text>
                <Text style={styles.modalSubtitle} allowFontScaling>
                  Direct action for patient or care coordinator follow-up
                </Text>
              </View>
              <TouchableOpacity
                onPress={() => setShowCreateModal(false)}
                style={styles.closeModalBtn}
                accessibilityRole="button"
                accessibilityLabel="Close modal"
              >
                <Ionicons name="close" size={20} color={doctorPalette.ink} />
              </TouchableOpacity>
            </View>

            {createError ? (
              <View style={styles.errorBanner}>
                <Ionicons name="alert-circle" size={16} color="#DC2626" />
                <Text style={styles.errorText} allowFontScaling>
                  {createError}
                </Text>
              </View>
            ) : null}

            {/* Patient Picker Chips */}
            <View style={styles.formGroup}>
              <Text style={styles.inputLabel} allowFontScaling>
                Select Target Patient
              </Text>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.patientPickerRow}
              >
                {patients.map((p) => {
                  const selected = newTaskPatientId === p.patient_id;
                  return (
                    <TouchableOpacity
                      key={p.patient_id}
                      style={[
                        styles.patientPickerChip,
                        selected ? styles.patientPickerChipSelected : null,
                      ]}
                      onPress={() => setNewTaskPatientId(p.patient_id)}
                      accessibilityRole="button"
                      accessibilityLabel={`Select patient ${p.name}`}
                    >
                      <Text
                        style={[
                          styles.patientPickerChipText,
                          selected ? styles.patientPickerChipTextSelected : null,
                        ]}
                        allowFontScaling
                      >
                        {p.name}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </ScrollView>
            </View>

            {/* Task Description */}
            <View style={styles.formGroup}>
              <Text style={styles.inputLabel} allowFontScaling>
                Clinical Instructions
              </Text>
              <TextInput
                style={styles.textArea}
                placeholder="e.g. Schedule fasting glucose check, review meal logs, or titrate basal insulin…"
                placeholderTextColor={doctorPalette.quiet}
                value={newTaskDescription}
                onChangeText={setNewTaskDescription}
                multiline
                numberOfLines={4}
                textAlignVertical="top"
              />
            </View>

            {/* Modal Actions */}
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setShowCreateModal(false)}
                accessibilityRole="button"
                accessibilityLabel="Cancel task creation"
              >
                <Text style={styles.modalCancelText} allowFontScaling>
                  Cancel
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[
                  styles.modalSubmitBtn,
                  !newTaskDescription.trim() || isCreating ? styles.modalSubmitBtnDisabled : null,
                ]}
                onPress={handleCreate}
                disabled={!newTaskDescription.trim() || isCreating}
                accessibilityRole="button"
                accessibilityLabel="Confirm and save care task"
              >
                <Text style={styles.modalSubmitText} allowFontScaling>
                  {isCreating ? "Saving…" : "Save Task"}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: doctorPalette.appBackground,
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 4,
    gap: 16,
    paddingBottom: 130,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
  },
  headerTextCol: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.2,
  },
  headerSubtitle: {
    fontSize: 12,
    color: doctorPalette.muted,
    marginTop: 2,
  },
  newTaskButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: doctorPalette.primary,
    borderRadius: doctorRadii.pill,
    minHeight: touchTarget.min,
    paddingHorizontal: 16,
    ...doctorPillShadow,
  },
  newTaskButtonText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "800",
  },
  filtersRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  filterChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surface,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    ...doctorSoftShadow,
  },
  filterChipActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.limeBorder,
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  filterChipTextActive: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  list: {
    gap: 12,
  },
  card: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 18,
    gap: 12,
    ...doctorSoftShadow,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: doctorRadii.pill,
  },
  statusBadgeOpen: {
    backgroundColor: "#DBEAFE",
  },
  statusBadgeProgress: {
    backgroundColor: "#FEF3C7",
  },
  statusBadgeDone: {
    backgroundColor: doctorPalette.limeSoft,
  },
  statusBadgeText: {
    fontSize: 10,
    fontWeight: "800",
  },
  statusBadgeTextOpen: {
    color: "#1E40AF",
  },
  statusBadgeTextProgress: {
    color: "#92400E",
  },
  statusBadgeTextDone: {
    color: "#15803D",
  },
  timestamp: {
    fontSize: 11,
    color: doctorPalette.muted,
  },
  descriptionText: {
    fontSize: 14,
    fontWeight: "500",
    color: doctorPalette.ink,
    lineHeight: 20,
  },
  cardFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderTopWidth: 1,
    borderTopColor: doctorPalette.borderSubtle,
    paddingTop: 12,
    marginTop: 2,
  },
  patientMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    flexShrink: 1,
  },
  patientLabel: {
    fontSize: 11,
    color: doctorPalette.muted,
  },
  patientName: {
    fontSize: 12,
    fontWeight: "800",
    color: doctorPalette.ink,
    maxWidth: 120,
  },
  openPatientText: {
    fontSize: 11,
    fontWeight: "800",
    color: doctorPalette.primary,
    marginLeft: 2,
  },
  actionButtons: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  actionBtnOutline: {
    borderWidth: 1,
    borderColor: doctorPalette.border,
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 12,
    paddingVertical: 7,
    backgroundColor: doctorPalette.surface,
  },
  actionBtnOutlineText: {
    fontSize: 11,
    fontWeight: "700",
    color: doctorPalette.ink,
  },
  actionBtnPrimary: {
    backgroundColor: doctorPalette.primary,
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 14,
    paddingVertical: 7,
    ...doctorPillShadow,
  },
  actionBtnPrimaryText: {
    fontSize: 11,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  completedBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 6,
    paddingVertical: 4,
  },
  completedBadgeText: {
    fontSize: 11,
    fontWeight: "800",
    color: "#15803D",
  },
  emptyCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    padding: 32,
    alignItems: "center",
    gap: 8,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    marginTop: 8,
    ...doctorSoftShadow,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  emptySubtitle: {
    fontSize: 13,
    color: doctorPalette.muted,
    textAlign: "center",
    maxWidth: 280,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.45)",
    justifyContent: "flex-end",
  },
  modalContent: {
    backgroundColor: doctorPalette.surface,
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
    padding: 24,
    gap: 16,
    maxHeight: "85%",
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  modalSubtitle: {
    fontSize: 12,
    color: doctorPalette.muted,
    marginTop: 2,
  },
  closeModalBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: doctorPalette.appBackground,
    alignItems: "center",
    justifyContent: "center",
  },
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: doctorPalette.criticalSoft,
    borderRadius: 14,
    padding: 10,
  },
  errorText: {
    fontSize: 12,
    color: doctorPalette.criticalText,
    flex: 1,
  },
  formGroup: {
    gap: 8,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  patientPickerRow: {
    gap: 8,
    paddingVertical: 4,
  },
  patientPickerChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.appBackground,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
  },
  patientPickerChipSelected: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.limeBorder,
  },
  patientPickerChipText: {
    fontSize: 12,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  patientPickerChipTextSelected: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  textArea: {
    borderWidth: 1,
    borderColor: doctorPalette.border,
    borderRadius: 18,
    padding: 14,
    fontSize: 14,
    color: doctorPalette.ink,
    minHeight: 110,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  modalActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 12,
    marginTop: 4,
  },
  modalCancelBtn: {
    paddingHorizontal: 18,
    minHeight: touchTarget.min,
    justifyContent: "center",
    alignItems: "center",
  },
  modalCancelText: {
    fontSize: 14,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  modalSubmitBtn: {
    backgroundColor: doctorPalette.primary,
    paddingHorizontal: 22,
    minHeight: touchTarget.min,
    borderRadius: doctorRadii.pill,
    justifyContent: "center",
    alignItems: "center",
    ...doctorPillShadow,
  },
  modalSubmitBtnDisabled: {
    opacity: 0.5,
  },
  modalSubmitText: {
    fontSize: 14,
    fontWeight: "800",
    color: "#FFFFFF",
  },
});
