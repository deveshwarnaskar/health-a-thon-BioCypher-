import React, { useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../auth/AuthProvider";
import { useCreateMedicationPlan } from "./useCreateMedicationPlan";
import { doctorKeys } from "./doctorKeys";
import { PlanForm } from "./PlanForm";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { EmptyState } from "../../components/primitives/EmptyState";
import { colors, spacing } from "../../theming/tokens";
import type { PatientSummaryResponse } from "../../services/schemas/patients";
import type { ApiErrorDetails } from "../../services/api/errors";
import type { CreateMedicationPlanResponse } from "../../services/schemas/medication";

export type CreateMedicationPlanScreenProps = {
  patient: PatientSummaryResponse;
  /** Return to the patient detail view (do NOT create a plan). */
  onCancel?: () => void;
  /** Called after the backend confirms the plan was created. */
  onCreated?: (data: CreateMedicationPlanResponse) => void;
  testID?: string;
};

/**
 * Clinician medication-plan creation (Gate 10F-M). The request body contains
 * ONLY patient_id / medication / instruction — the prescriber is always
 * derived by the backend from the authenticated context. A network failure
 * never implies success: no banner is shown without backend confirmation.
 */
export function CreateMedicationPlanScreen({
  patient,
  onCancel,
  onCreated,
  testID,
}: CreateMedicationPlanScreenProps) {
  const { state } = useAuth();
  const queryClient = useQueryClient();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  const authUser = state.name === "authenticated" ? state.user : null;
  const isDoctorRole = authUser?.role === "Doctor";

  const create = useCreateMedicationPlan({
    onSuccess: (data) => {
      setErrorMessage(null);
      setFieldErrors({});
      onCreated?.(data);
    },
    onError: (error) => {
      setFieldErrors({});
      const apiError = error as ApiErrorDetails | undefined;
      if (apiError?.httpStatus === 403) {
        // Plan-boundary revocation mid-session: never a logout. Invalidate
        // plan caches and return to a safe view.
        void queryClient.invalidateQueries({ queryKey: doctorKeys.medicationPlans() });
        void queryClient.invalidateQueries({
          queryKey: doctorKeys.medicationPlans(patient.patient_id),
        });
        setErrorMessage(null);
        return;
      }
      if (apiError?.httpStatus === 422) {
        setFieldErrors(apiError.fieldErrors ?? {});
        setErrorMessage("The plan could not be validated. Fix the highlighted fields and try again.");
        return;
      }
      if (apiError?.httpStatus === 409) {
        setErrorMessage("A conflicting plan is already being created. Please wait a moment before trying again.");
      } else if (apiError?.httpStatus === 429) {
        const retry = apiError.retryAfterSeconds;
        setErrorMessage(
          retry
            ? `Too many requests. Please wait ${retry} seconds before creating a plan.`
            : "Too many requests. Please wait a moment before trying again."
        );
      } else if (apiError?.kind === "NETWORK_ERROR") {
        setErrorMessage("Unable to connect. The plan has not been submitted.");
      } else {
        setErrorMessage(apiError?.message ?? "The plan could not be created. Please try again.");
      }
    },
  });

  if (!isDoctorRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Create Plan" onBack={onCancel} leadingLabel={onCancel ? "Cancel" : undefined} />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="Medication plan creation is only available in Doctor mode."
          />
        </View>
      </View>
    );
  }

  if (create.isError && ((create.error as unknown) as ApiErrorDetails | undefined)?.httpStatus === 403) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Create Plan" onBack={onCancel} leadingLabel={onCancel ? "Cancel" : undefined} />
        <View style={styles.content}>
          <View testID="doctor-create-plan-access-revoked">
            <EmptyState
              title="Access Revoked"
              message="Your ability to create plans for this patient was removed or expired. Returning to the patient record."
            />
          </View>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Create Plan"
        onBack={onCancel}
        leadingLabel={onCancel ? "Cancel" : undefined}
      />

      <ScrollView contentContainerStyle={styles.scrollContent}>
        <AlertBanner tone="info" title={patient.name} message="Creating a clinician-authored medication plan." />
        {errorMessage ? (
          <AlertBanner tone="critical" title="Plan Creation Failed" message={errorMessage} />
        ) : null}
        <PlanForm
          patientId={patient.patient_id}
          isSubmitting={create.isPending}
          backendFieldErrors={fieldErrors}
          onSubmit={(request) => {
            setErrorMessage(null);
            setFieldErrors({});
            create.mutate(request);
          }}
          testID="doctor-create-plan-form"
        />
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
  scrollContent: {
    padding: spacing.md,
    gap: spacing.md,
    paddingBottom: spacing.xxl,
  },
});