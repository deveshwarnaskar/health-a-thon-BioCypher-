import React, { useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { useAuth } from "../../auth/AuthProvider";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { Divider } from "../../components/primitives/Divider";
import { Button } from "../../components/primitives/Button";
import { EmptyState } from "../../components/primitives/EmptyState";
import { colors, spacing } from "../../theming/tokens";
import { GlucoseEntryForm } from "./GlucoseEntryForm";
import { GlucoseTimeline } from "./GlucoseTimeline";
import { useGlucoseFeed } from "./useGlucoseFeed";
import { useIngestGlucose } from "./useIngestGlucose";
import type { ApiErrorDetails } from "../../services/api/errors";
import type { IngestGlucoseResponse } from "../../services/schemas/clinical";

export type PatientGlucoseScreenProps = {
  patientId?: string;
  onBack?: () => void;
  testID?: string;
};

export function PatientGlucoseScreen({
  patientId: propPatientId,
  onBack,
  testID,
}: PatientGlucoseScreenProps) {
  const { state } = useAuth();
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const authUser = state.name === "authenticated" ? state.user : null;
  const isPatientRole = authUser?.role === "Patient";
  const resolvedPatientId = propPatientId ?? authUser?.patient_id ?? null;

  // Query and mutation hooks
  const feed = useGlucoseFeed(resolvedPatientId, {
    enabled: isPatientRole && Boolean(resolvedPatientId),
  });

  const ingest = useIngestGlucose({
    patientId: resolvedPatientId,
    onSuccess: (response: IngestGlucoseResponse) => {
      setErrorMessage(null);
      setSuccessMessage(`Reading of ${response.value_mg_dl} mg/dL recorded successfully.`);
    },
    onError: (error: unknown) => {
      setSuccessMessage(null);
      const apiError = error as ApiErrorDetails | undefined;

      if (apiError?.httpStatus === 403) {
        setErrorMessage("Access denied. Your patient record is inactive or access has been revoked.");
      } else if (apiError?.httpStatus === 409) {
        setErrorMessage("A conflicting submission is already in progress. Please wait a moment.");
      } else if (apiError?.httpStatus === 429) {
        const retry = apiError.retryAfterSeconds;
        setErrorMessage(
          retry
            ? `Too many requests. Please wait ${retry} seconds before recording again.`
            : "Too many requests. Please wait a moment before trying again."
        );
      } else if (apiError?.kind === "NETWORK_ERROR") {
        setErrorMessage("Unable to connect. Your glucose reading has not been submitted.");
      } else {
        setErrorMessage(apiError?.message ?? "An unexpected error occurred. Please try again.");
      }
    },
  });

  // Guard: Role must be Patient
  if (!isPatientRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Glucose"
          onBack={onBack}
          leadingLabel={onBack ? "Back" : undefined}
        />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="The glucose logging screen is only available in Patient mode."
          />
          {onBack ? (
            <Button label="Return to Main Menu" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  // Guard: Patient identity must be linked
  if (!resolvedPatientId) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Glucose"
          onBack={onBack}
          leadingLabel={onBack ? "Back" : undefined}
        />
        <View style={styles.content}>
          <View testID="unlinked-patient-state">
            <EmptyState
              title="Account Linking Required"
              message="Your account is not yet linked to a patient profile. Please contact your clinic coordinator to activate your patient record."
            />
          </View>
          {onBack ? (
            <Button label="Return to Main Menu" variant="outline" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Glucose Logbook"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
      />

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {successMessage ? (
          <AlertBanner
            tone="success"
            title="Recorded"
            message={successMessage}
          />
        ) : null}

        {errorMessage ? (
          <AlertBanner
            tone="critical"
            title="Submission Failed"
            message={errorMessage}
          />
        ) : null}

        <GlucoseEntryForm
          onSubmit={(data) => {
            setSuccessMessage(null);
            setErrorMessage(null);
            ingest.mutate(data);
          }}
          isSubmitting={ingest.isPending}
          testID="patient-glucose-form"
        />

        <Divider label="Observation Feed" />

        <GlucoseTimeline
          readings={feed.readings}
          isLoading={feed.isLoading}
          isError={feed.isError}
          onRetry={() => feed.refetch()}
          testID="patient-glucose-timeline"
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
