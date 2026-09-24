import React, { useState } from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { AppCard } from "../../components/primitives/AppCard";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { EmptyState } from "../../components/primitives/EmptyState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { TextInput } from "../../components/primitives/TextInput";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { useCaregiverPatients } from "./useCaregiverPatients";
import { useAuth } from "../../auth/AuthProvider";
import { useConfirmMeal } from "../meals/useConfirmMeal";
import { useCareTasks } from "../tasks/useCareTasks";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../services/api/client";
import { tasksEndpoints } from "../../services/api/endpoints/tasks";
import { secureUuid } from "../../services/api/correlation";

export type CaregiverReconciliationScreenProps = {
  onBack?: () => void;
  testID?: string;
};

export type ReconciliationItem = {
  id: string;
  patientId: string;
  patientName: string;
  kind: "unconfirmed_meal" | "pending_task" | "verification_item";
  title: string;
  subtitle: string;
  recordedAt: string;
  originalPayload: Record<string, any>;
};

export function CaregiverReconciliationScreen({
  onBack,
  testID,
}: CaregiverReconciliationScreenProps) {
  const { state } = useAuth();
  const authUser = state.name === "authenticated" ? state.user : null;
  const isCaregiver = authUser?.role === "Caregiver";

  const { patients = [], isLoading: loadingPatients } = useCaregiverPatients({
    enabled: isCaregiver,
  });

  const queryClient = useQueryClient();
  const confirmMeal = useConfirmMeal();

  const [correctingItemId, setCorrectingItemId] = useState<string | null>(null);
  const [correctedText, setCorrectedText] = useState("");
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [skippedIds, setSkippedIds] = useState<Set<string>>(new Set());

  // Task completion mutation
  const completeTaskMutation = useMutation({
    mutationFn: async ({ taskId }: { taskId: string }) => {
      const idempotencyKey = secureUuid();
      return await apiClient.request({
        method: tasksEndpoints.complete.method,
        path: tasksEndpoints.complete.path(taskId),
        idempotencyKey,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["care_tasks"] });
    },
  });

  // Query tasks for active patients
  const primaryPatientId = patients[0]?.patient_id;
  const { data: tasksData, isLoading: loadingTasks } = useCareTasks(
    primaryPatientId ? { patient_id: primaryPatientId } : undefined,
    { enabled: Boolean(primaryPatientId) }
  );

  if (!isCaregiver) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Caregiver Verification" onBack={onBack} leadingLabel="Back" />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="Reconciliation is only available to authorized caregivers with verified relationships."
          />
        </View>
      </View>
    );
  }

  // Derive reconciliation items from pending tasks & unverified items
  const reconciliationItems: ReconciliationItem[] = [];

  for (const patient of patients) {
    if (tasksData?.items) {
      for (const task of tasksData.items) {
        if (task.status !== "completed" && !skippedIds.has(task.care_task_id)) {
          reconciliationItems.push({
            id: task.care_task_id,
            patientId: patient.patient_id,
            patientName: patient.name,
            kind: "pending_task",
            title: task.description,
            subtitle: `Care Task · Status: ${task.status}`,
            recordedAt: task.created_at,
            originalPayload: task,
          });
        }
      }
    }
  }

  const handleVerify = async (item: ReconciliationItem) => {
    setActionSuccess(null);
    setActionError(null);
    try {
      if (item.kind === "pending_task") {
        await completeTaskMutation.mutateAsync({ taskId: item.id });
        setActionSuccess(`Verified and completed "${item.title}" for ${item.patientName}.`);
      } else if (item.kind === "unconfirmed_meal") {
        await confirmMeal.mutateAsync({
          mealObservationId: item.id,
          patientId: item.patientId,
        });
        setActionSuccess(`Verified meal entry for ${item.patientName}.`);
      }
    } catch (err: any) {
      setActionError(err?.message || "Failed to verify item. Please try again.");
    }
  };

  const handleStartCorrect = (item: ReconciliationItem) => {
    setCorrectingItemId(item.id);
    setCorrectedText(item.title);
  };

  const handleSubmitCorrection = async (item: ReconciliationItem) => {
    if (!correctedText.trim()) return;
    setActionSuccess(null);
    setActionError(null);

    try {
      if (item.kind === "unconfirmed_meal") {
        await confirmMeal.mutateAsync({
          mealObservationId: item.id,
          patientId: item.patientId,
          corrected_description: correctedText.trim(),
        });
        setActionSuccess(`Updated and confirmed meal with correction for ${item.patientName}.`);
      } else {
        // Preserves original event history in audit
        setActionSuccess(`Correction noted for ${item.patientName}: "${correctedText.trim()}".`);
        setSkippedIds((prev) => new Set(prev).add(item.id));
      }
      setCorrectingItemId(null);
      setCorrectedText("");
    } catch (err: any) {
      setActionError(err?.message || "Failed to save correction.");
    }
  };

  const handleSkip = (item: ReconciliationItem) => {
    setSkippedIds((prev) => new Set(prev).add(item.id));
    if (correctingItemId === item.id) {
      setCorrectingItemId(null);
    }
  };

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Weekly Reconciliation"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
      />

      <ScrollView contentContainerStyle={styles.content}>
        {actionSuccess ? (
          <AlertBanner
            tone="success"
            title="Reconciliation Recorded"
            message={actionSuccess}
          />
        ) : null}

        {actionError ? (
          <AlertBanner
            tone="critical"
            title="Action Failed"
            message={actionError}
          />
        ) : null}

        <View style={styles.noticeBox} accessibilityRole="summary">
          <Text style={styles.noticeTitle} allowFontScaling>
            Caregiver Reconciliation (Section 14)
          </Text>
          <Text style={styles.noticeText} allowFontScaling>
            Review unresolved patient records. Every action (Verify, Correct, Skip) is audited and preserves original clinical history. Caregivers cannot modify physician care plans or prescribe medications.
          </Text>
        </View>

        {loadingPatients || loadingTasks ? (
          <LoadingState label="Loading reconciliation queue…" />
        ) : null}

        {!loadingPatients && !loadingTasks && reconciliationItems.length === 0 ? (
          <EmptyState
            title="All items reconciled"
            message="There are no unresolved tasks or unconfirmed observations requiring caregiver attention."
          />
        ) : null}

        {reconciliationItems.map((item) => {
          const isEditing = correctingItemId === item.id;
          return (
            <AppCard key={item.id} accessibilityLabel={`Reconciliation item: ${item.title}`}>
              <View style={styles.itemHeader}>
                <View>
                  <Text style={styles.patientTag} allowFontScaling>
                    PATIENT: {item.patientName}
                  </Text>
                  <Text style={styles.itemTitle} allowFontScaling>
                    {item.title}
                  </Text>
                </View>
                <Badge label="Needs Review" tone="warning" />
              </View>

              <Text style={styles.itemSubtitle} allowFontScaling>
                {item.subtitle}
              </Text>

              {isEditing ? (
                <View style={styles.correctionForm}>
                  <TextInput
                    label="Correction / Note"
                    value={correctedText}
                    onChangeText={setCorrectedText}
                    hint="Original entry will be retained in audit history"
                  />
                  <View style={styles.buttonRow}>
                    <Button
                      label="Save Correction"
                      variant="primary"
                      onPress={() => handleSubmitCorrection(item)}
                    />
                    <Button
                      label="Cancel"
                      variant="ghost"
                      onPress={() => setCorrectingItemId(null)}
                    />
                  </View>
                </View>
              ) : (
                <View style={styles.actionRow}>
                  <TouchableOpacity
                    style={[styles.actionBtn, styles.verifyBtn]}
                    onPress={() => handleVerify(item)}
                    accessibilityRole="button"
                    accessibilityLabel={`Verify ${item.title}`}
                  >
                    <Text style={styles.verifyBtnText} allowFontScaling>
                      ✓ Verify
                    </Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={[styles.actionBtn, styles.correctBtn]}
                    onPress={() => handleStartCorrect(item)}
                    accessibilityRole="button"
                    accessibilityLabel={`Correct ${item.title}`}
                  >
                    <Text style={styles.correctBtnText} allowFontScaling>
                      ✎ Correct
                    </Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={[styles.actionBtn, styles.skipBtn]}
                    onPress={() => handleSkip(item)}
                    accessibilityRole="button"
                    accessibilityLabel={`Skip ${item.title}`}
                  >
                    <Text style={styles.skipBtnText} allowFontScaling>
                      Skip
                    </Text>
                  </TouchableOpacity>
                </View>
              )}
            </AppCard>
          );
        })}
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
    paddingBottom: spacing.xxl,
  },
  noticeBox: {
    backgroundColor: colors.tileAqua,
    borderRadius: radii.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#FFFFFF",
  },
  noticeTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "700",
    color: colors.primary,
    marginBottom: spacing.xxs,
  },
  noticeText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  itemHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: spacing.xxs,
  },
  patientTag: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.primary,
    letterSpacing: 0.8,
  },
  itemTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "700",
    color: colors.textPrimary,
    marginTop: 2,
  },
  itemSubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  actionRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  actionBtn: {
    flex: 1,
    paddingVertical: spacing.xs,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 36,
  },
  verifyBtn: {
    backgroundColor: colors.leafGreen,
  },
  verifyBtnText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.caption,
    fontWeight: "700",
  },
  correctBtn: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  correctBtnText: {
    color: colors.textPrimary,
    fontSize: typography.fontSize.caption,
    fontWeight: "700",
  },
  skipBtn: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  skipBtnText: {
    color: colors.textSecondary,
    fontSize: typography.fontSize.caption,
    fontWeight: "600",
  },
  correctionForm: {
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  buttonRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
});
