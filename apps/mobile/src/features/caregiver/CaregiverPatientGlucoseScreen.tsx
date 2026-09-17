import React, { useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../auth/AuthProvider";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { Button } from "../../components/primitives/Button";
import { Divider } from "../../components/primitives/Divider";
import { EmptyState } from "../../components/primitives/EmptyState";
import { colors, spacing } from "../../theming/tokens";
import { GlucoseEntryForm } from "../glucose/GlucoseEntryForm";
import { GlucoseTimeline } from "../glucose/GlucoseTimeline";
import { useGlucoseFeed } from "../glucose/useGlucoseFeed";
import { useIngestGlucose } from "../glucose/useIngestGlucose";
import { caregiverKeys } from "./useCaregiverPatients";
import {
  canReadCaregiverGlucose,
  canRecordCaregiverGlucose,
  type CaregiverPatientListItem,
} from "../../services/schemas/caregiver";
import type { ApiErrorDetails } from "../../services/api/errors";
import type { IngestGlucoseResponse } from "../../services/schemas/clinical";

export type CaregiverPatientGlucoseScreenProps = {
  patient: CaregiverPatientListItem;
  onBack?: () => void;
  /**
   * Called when access to this patient is lost mid-session (403). The
   * caregiver patient list is invalidated so the screen can return to a fresh
   * discovery view. This is a per-patient revocation, NOT a logout (401).
   */
  onAccessLost?: () => void;
  testID?: string;
};

export function CaregiverPatientGlucoseScreen({
  patient,
  onBack,
  onAccessLost,
  testID,
}: CaregiverPatientGlucoseScreenProps) {
  const { state } = useAuth();
  const queryClient = useQueryClient();
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const authUser = state.name === "authenticated" ? state.user : null;
  const isCaregiverRole = authUser?.role === "Caregiver";
  const relationshipCapabilities = patient.capabilities;

  const canRead = canReadCaregiverGlucose(relationshipCapabilities);
  const canRecord = canRecordCaregiverGlucose(relationshipCapabilities);

  const feed = useGlucoseFeed(patient.patient_id, {
    enabled: isCaregiverRole && canRead,
  });

  const ingest = useIngestGlucose({
    patientId: patient.patient_id,
    onSuccess: (response: IngestGlucoseResponse) => {
      setErrorMessage(null);
      setSuccessMessage(`Reading of ${response.value_mg_dl} mg/dL recorded successfully.`);
    },
    onError: (error) => {
      setSuccessMessage(null);
      const apiError = error as ApiErrorDetails | undefined;

      if (apiError?.httpStatus === 403) {
        // Relationship capability was revoked mid-session: this patient's
        // access boundary closed. Refresh the discovery list and return to
        // patient selection — never a logout.
        void queryClient.invalidateQueries({ queryKey: caregiverKeys.patients() });
        onAccessLost?.();
        return;
      }
      if (apiError?.httpStatus === 409) {
        setErrorMessage("A conflicting submission is already in progress. Please wait a moment.");
      } else if (apiError?.httpStatus === 429) {
        const retry = apiError.retryAfterSeconds;
        setErrorMessage(
          retry
            ? `Too many requests. Please wait ${retry} seconds before recording again.`
            : "Too many requests. Please wait a moment before trying again."
        );
      } else if (apiError?.kind === "NETWORK_ERROR") {
        setErrorMessage("Unable to connect. The reading has not been submitted.");
      } else {
        setErrorMessage(apiError?.message ?? "An unexpected error occurred. Please try again.");
      }
    },
  });

  if (!isCaregiverRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Patient Glucose"
          onBack={onBack}
          leadingLabel={onBack ? "Back" : undefined}
        />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="Patient glucose is only available in Caregiver mode."
          />
          {onBack ? (
            <Button label="Return to Patient List" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  // 403 on the observation feed means this patient's access boundary closed
  // while the list was open. Show the revocation state (not a logout) and
  // offer a way back to a refreshed patient list.
  if (feed.isError && (feed.error as ApiErrorDetails | undefined)?.httpStatus === 403) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Patient Glucose"
          onBack={onBack}
          leadingLabel={onBack ? "Back" : undefined}
        />
        <View style={styles.content}>
          <View testID="caregiver-access-revoked">
            <EmptyState
              title="Access Revoked"
              message="Your relationship with this patient was revoked or expired. Returning to your patient list."
            />
          </View>
          {onAccessLost ? (
            <Button label="Back to Patient List" variant="primary" onPress={onAccessLost} />
          ) : null}
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Patient Glucose"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
      />

      <ScrollView contentContainerStyle={styles.scrollContent}>
        <AlertBanner tone="info" title={patient.name} message="Authorized to view this patient's glucose record." />

        {successMessage ? (
          <AlertBanner tone="success" title="Recorded" message={successMessage} />
        ) : null}

        {errorMessage ? (
          <AlertBanner tone="critical" title="Submission Failed" message={errorMessage} />
        ) : null}

        {canRecord ? (
          <GlucoseEntryForm
            onSubmit={(data) => {
              setSuccessMessage(null);
              setErrorMessage(null);
              ingest.mutate(data);
            }}
            isSubmitting={ingest.isPending}
            testID="caregiver-glucose-form"
          />
        ) : (
          <AlertBanner
            tone="info"
            title="View-only access"
            message="Your relationship allows viewing this patient's glucose records but not recording new readings."
          />
        )}

        {canRead ? (
          <>
            <Divider label="Observation Feed" />
            <GlucoseTimeline
              readings={feed.readings}
              isLoading={feed.isLoading}
              isError={feed.isError}
              onRetry={() => feed.refetch()}
              testID="caregiver-glucose-timeline"
            />
          </>
        ) : null}
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