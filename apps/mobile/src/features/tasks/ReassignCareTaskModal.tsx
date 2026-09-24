import React, { useState } from "react";
import { Modal, ScrollView, StyleSheet, Text, View } from "react-native";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { TextInput } from "../../components/primitives/TextInput";
import { Button } from "../../components/primitives/Button";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { colors, spacing, typography } from "../../theming/tokens";
import { useReassignCareTask } from "./useCareTasks";
import type { ApiErrorDetails } from "../../services/api/errors";

export type ReassignCareTaskModalProps = {
  visible: boolean;
  taskId: string;
  onClose: () => void;
  onSuccess?: () => void;
  testID?: string;
};

export function ReassignCareTaskModal({
  visible,
  taskId,
  onClose,
  onSuccess,
  testID,
}: ReassignCareTaskModalProps) {
  const [newUserId, setNewUserId] = useState<string>("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  const reassignMutation = useReassignCareTask({
    onSuccess: () => {
      setServerError(null);
      setValidationError(null);
      setNewUserId("");
      onSuccess?.();
      onClose();
    },
    onError: (err) => {
      const apiErr = err as ApiErrorDetails | undefined;
      if (apiErr?.httpStatus === 403) {
        setServerError("You are not authorized to reassign tasks, or target worker is outside facility.");
      } else if (apiErr?.httpStatus === 409) {
        setServerError("Completed or cancelled tasks cannot be reassigned.");
      } else if (apiErr?.httpStatus === 404) {
        setServerError("New assignee or task was not found.");
      } else {
        setServerError(apiErr?.message || "Failed to reassign task.");
      }
    },
  });

  const handleSubmit = () => {
    if (!newUserId.trim()) {
      setValidationError("New worker UUID is required.");
      return;
    }
    setValidationError(null);
    reassignMutation.mutate({
      taskId,
      body: { new_user_id: newUserId.trim() },
    });
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Reassign Care Task" onBack={onClose} />

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
              title="Reassignment Error"
              message={serverError}
              tone="critical"
            />
          ) : null}

          <Text style={styles.helperText} allowFontScaling>
            Enter the User UUID of the replacement care worker in the same facility:
          </Text>

          <TextInput
            label="Replacement Worker UUID"
            value={newUserId}
            onChangeText={(text) => {
              setNewUserId(text);
              if (validationError) setValidationError(null);
            }}
            placeholder="00000000-0000-0000-0000-000000000000"
            accessibilityLabel="Replacement worker UUID input"
            accessibilityHint="No dedicated worker-directory endpoint; enter replacement care worker user UUID"
          />

          <View style={styles.actions}>
            <Button
              label={reassignMutation.isPending ? "Reassigning…" : "Confirm Reassignment"}
              variant="primary"
              disabled={reassignMutation.isPending}
              onPress={handleSubmit}
              testID="submit-reassign-task-button"
            />
            <Button
              label="Cancel"
              variant="ghost"
              disabled={reassignMutation.isPending}
              onPress={onClose}
              testID="cancel-reassign-task-button"
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
  helperText: {
    fontSize: typography.fontSize.body,
    color: colors.textSecondary,
    marginBottom: spacing.xxs,
  },
  actions: {
    gap: spacing.sm,
    marginTop: spacing.md,
  },
});
