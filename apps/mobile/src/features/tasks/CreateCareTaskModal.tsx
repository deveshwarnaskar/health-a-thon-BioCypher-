import React, { useState } from "react";
import { Modal, ScrollView, StyleSheet, Text, View } from "react-native";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { TextInput } from "../../components/primitives/TextInput";
import { Button } from "../../components/primitives/Button";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { colors, spacing, typography } from "../../theming/tokens";
import { useCreateCareTask } from "./useCareTasks";
import { usePatients } from "../doctor/usePatients";
import type { ApiErrorDetails } from "../../services/api/errors";

export type CreateCareTaskModalProps = {
  visible: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  testID?: string;
};

export function CreateCareTaskModal({
  visible,
  onClose,
  onSuccess,
  testID,
}: CreateCareTaskModalProps) {
  const [patientId, setPatientId] = useState<string>("");
  const [assignedUserId, setAssignedUserId] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [dueAt, setDueAt] = useState<string>("");

  const [validationError, setValidationError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  const { patients } = usePatients({ enabled: visible });

  const createMutation = useCreateCareTask({
    onSuccess: () => {
      setServerError(null);
      setValidationError(null);
      setPatientId("");
      setAssignedUserId("");
      setDescription("");
      setDueAt("");
      onSuccess?.();
      onClose();
    },
    onError: (err) => {
      const apiErr = err as ApiErrorDetails | undefined;
      if (apiErr?.httpStatus === 403) {
        setServerError("You are not authorized to create care tasks for this patient or facility.");
      } else if (apiErr?.httpStatus === 404) {
        setServerError("The specified patient was not found in your facility.");
      } else {
        setServerError(apiErr?.message || "Failed to create care task.");
      }
    },
  });

  const validate = (): boolean => {
    if (!patientId.trim()) {
      setValidationError("Patient ID is required.");
      return false;
    }
    if (!assignedUserId.trim()) {
      setValidationError("Assigned worker ID is required.");
      return false;
    }
    if (!description.trim()) {
      setValidationError("Task description cannot be empty.");
      return false;
    }
    setValidationError(null);
    return true;
  };

  const handleSubmit = () => {
    if (!validate()) return;
    createMutation.mutate({
      patient_id: patientId.trim(),
      assigned_to_user_id: assignedUserId.trim(),
      description: description.trim(),
      due_at: dueAt.trim() ? dueAt.trim() : undefined,
    });
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Create Care Task" onBack={onClose} />

        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          {validationError ? (
            <AlertBanner
              title="Validation Error"
              message={validationError}
              tone="warning"
            />
          ) : null}

          {serverError ? (
            <AlertBanner
              title="Submission Error"
              message={serverError}
              tone="critical"
            />
          ) : null}

          <Text style={styles.sectionLabel} allowFontScaling>
            Select Facility Patient or Enter UUID
          </Text>

          {patients.length > 0 ? (
            <View style={styles.quickPatientList}>
              {patients.slice(0, 4).map((p) => (
                <Button
                  key={p.patient_id}
                  label={`${p.name} (${p.uh_id})`}
                  variant={patientId === p.patient_id ? "primary" : "outline"}
                  onPress={() => setPatientId(p.patient_id)}
                  style={styles.quickPatientBtn}
                />
              ))}
            </View>
          ) : null}

          <TextInput
            label="Patient UUID"
            value={patientId}
            onChangeText={(text) => {
              setPatientId(text);
              if (validationError) setValidationError(null);
            }}
            placeholder="00000000-0000-0000-0000-000000000000"
            accessibilityLabel="Patient UUID input"
          />

          <TextInput
            label="Assigned Worker UUID"
            value={assignedUserId}
            onChangeText={(text) => {
              setAssignedUserId(text);
              if (validationError) setValidationError(null);
            }}
            placeholder="Worker User UUID"
            accessibilityLabel="Assigned Worker User UUID input"
            accessibilityHint="No dedicated worker-directory endpoint; enter care worker user UUID"
          />

          <TextInput
            label="Task Description"
            value={description}
            onChangeText={(text) => {
              setDescription(text);
              if (validationError) setValidationError(null);
            }}
            placeholder="e.g. Follow-up on fasting blood glucose"
            accessibilityLabel="Task description input"
            multiline
            numberOfLines={3}
          />

          <TextInput
            label="Due Date (Optional ISO or YYYY-MM-DD)"
            value={dueAt}
            onChangeText={setDueAt}
            placeholder="YYYY-MM-DDTHH:MM:SSZ"
            accessibilityLabel="Due date optional input"
          />

          <View style={styles.actions}>
            <Button
              label={createMutation.isPending ? "Creating…" : "Create Task"}
              variant="primary"
              disabled={createMutation.isPending}
              onPress={handleSubmit}
              testID="submit-create-task-button"
            />
            <Button
              label="Cancel"
              variant="ghost"
              disabled={createMutation.isPending}
              onPress={onClose}
              testID="cancel-create-task-button"
            />
          </View>
        </ScrollView>
      </View>
    </Modal>
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
  sectionLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: spacing.xxs,
  },
  quickPatientList: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  quickPatientBtn: {
    marginVertical: spacing.xxs,
  },
  actions: {
    gap: spacing.sm,
    marginTop: spacing.md,
  },
});
