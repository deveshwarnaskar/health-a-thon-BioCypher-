import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useAuth } from "../../auth/AuthProvider";
import { usePatientDetail } from "./usePatientDetail";
import { useClinicianFeed } from "./useClinicianFeed";
import { useMedicationPlans } from "./useMedicationPlans";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { AppCard } from "../../components/primitives/AppCard";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { Divider } from "../../components/primitives/Divider";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { colors, spacing, typography } from "../../theming/tokens";
import type { PatientSummaryResponse } from "../../services/schemas/patients";
import type { ClinicianGlucoseObservation, ClinicianMealObservation } from "../../services/schemas/clinical";
import type { ApiErrorDetails } from "../../services/api/errors";

export type PatientDetailScreenProps = {
  patient: PatientSummaryResponse;
  onBack?: () => void;
  onCreatePlan?: (patient: PatientSummaryResponse) => void;
  testID?: string;
};

/**
 * Doctor patient detail (Gate 10F-M): identity facts, the clinician-only
 * observation feed (carbs_grams / glycemic_index present ONLY here — these
 * fields never reach patient/caregiver surfaces), and this patient's
 * medication plans plus plan creation. The clinician feed is the ONLY surface
 * to mount useClinicianFeed; patient/caregiver feeds use the separate,
 * strictly patient-safe pipeline.
 */
export function PatientDetailScreen({ patient, onBack, onCreatePlan, testID }: PatientDetailScreenProps) {
  const { state } = useAuth();
  const authUser = state.name === "authenticated" ? state.user : null;
  const isDoctorRole = authUser?.role === "Doctor";

  const patientId = patient.patient_id;
  const detail = usePatientDetail(patientId, { enabled: isDoctorRole });
  const feed = useClinicianFeed(patientId, { enabled: isDoctorRole });
  const plans = useMedicationPlans(patientId, { enabled: isDoctorRole });

  if (!isDoctorRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Patient Detail" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="Patient clinical detail is only available in Doctor mode."
          />
          {onBack ? (
            <Button label="Return to Main Menu" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  // A 403 on the clinical feed means this patient's read boundary closed
  // mid-session. Revocation, never a logout — return to the cohort.
  if (feed.isError && (feed.error as ApiErrorDetails | undefined)?.httpStatus === 403) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Patient Detail" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <View testID="doctor-patient-access-revoked">
            <EmptyState
              title="Access Revoked"
              message="Your access to this patient's clinical record was removed or expired. Returning to the patient list."
            />
          </View>
          {onBack ? (
            <Button label="Return to Patient List" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  // The patient detail read resolves to 404 (EntityNotFound) for deactivated,
  // cross-facility, or missing patients: treat as unavailable without
  // revealing which.
  if (detail.isError && (detail.error as ApiErrorDetails | undefined)?.httpStatus === 404) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Patient Detail" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <View testID="doctor-patient-unavailable">
            <EmptyState title="Patient unavailable" message="This patient record is no longer available." />
          </View>
          {onBack ? (
            <Button label="Return to Patient List" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  const shown = detail.patient ?? patient;

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Patient Detail"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
      />

      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.name} allowFontScaling>
            {shown.name}
          </Text>
          {shown.active ? <Badge label="Active" tone="success" /> : <Badge label="Inactive" tone="critical" />}
        </View>
        <Text style={styles.meta} allowFontScaling>
          UH ID {shown.uh_id}
        </Text>

        <Divider label="Clinical Observations" />
        {feed.isLoading ? <LoadingState label="Loading observations…" /> : null}

        {!feed.isLoading && feed.isError ? (
          <ErrorState
            title="Could not load observations"
            message="Please try again."
            onRetry={() => feed.refetch()}
          />
        ) : null}

        {!feed.isLoading && !feed.isError && (feed.feed?.items.length ?? 0) === 0 ? (
          <EmptyState title="No observations yet" message="No clinical observations are recorded for this patient." />
        ) : null}

        {!feed.isLoading && !feed.isError && feed.feed && feed.feed.items.length > 0 ? (
          <View style={styles.feed}>
            {feed.feed.items.map((item, index) => {
              if (item.kind === "glucose") {
                return <GlucoseObservationCard key={index} item={item} />;
              }
              return <MealObservationCard key={index} item={item} />;
            })}
          </View>
        ) : null}

        <Divider label="Medication Plans" />

        {plans.isLoading ? <LoadingState label="Loading medication plans…" /> : null}

        {!plans.isLoading && plans.isError ? (
          <View testID="doctor-patient-plans-error">
            <ErrorState title="Could not load plans" message="Please try again." onRetry={() => plans.refetch()} />
          </View>
        ) : null}

        {!plans.isLoading && !plans.isError && plans.plans.length > 0 ? (
          <View style={styles.plans}>
            {plans.plans.map((plan) => (
              <AppCard key={plan.medication_plan_id} accessibilityLabel={`Medication plan ${plan.medication}`}>
                <Text style={styles.planMedication} allowFontScaling>
                  {plan.medication}
                </Text>
                <Text style={styles.meta} allowFontScaling>
                  {plan.instruction || "No instruction"}
                </Text>
                <Text style={styles.meta} allowFontScaling>
                  Prescribed by {plan.prescribed_by_role === "doctor" ? "Doctor" : plan.prescribed_by_role}
                  {plan.active ? " · Active" : " · Inactive"}
                </Text>
              </AppCard>
            ))}
          </View>
        ) : null}

        {!plans.isLoading && !plans.isError && plans.plans.length === 0 ? (
          <EmptyState title="No medication plans" message="This patient has no clinician-authored medication plans." />
        ) : null}

        {onCreatePlan ? (
          <Button
            label="Create Medication Plan"
            variant="primary"
            onPress={() => onCreatePlan(shown)}
            accessibilityHint="Opens the clinician medication-plan form for this patient."
          />
        ) : null}
      </ScrollView>
    </View>
  );
}

function GlucoseObservationCard({ item }: { item: ClinicianGlucoseObservation }) {
  return (
    <View style={styles.observationCard} accessible accessibilityLabel={`Glucose reading ${item.value_mg_dl ?? "unknown"} mg/dL`}>
      <Text style={styles.observationTitle} allowFontScaling>
        Glucose
      </Text>
      <Text style={styles.observationValue} allowFontScaling>
        {item.value_mg_dl != null ? `${item.value_mg_dl} mg/dL` : "Not recorded"}
      </Text>
      <Text style={styles.meta} allowFontScaling>
        {item.tag ?? "No tag"} · {item.taken_at} · {item.confirmation}
      </Text>
    </View>
  );
}

function MealObservationCard({ item }: { item: ClinicianMealObservation }) {
  return (
    <View
      style={styles.observationCard}
      accessible
      accessibilityLabel={`Meal ${item.description} carbohydrates ${item.carbs_grams ?? "unknown"} grams`}
    >
      <Text style={styles.observationTitle} allowFontScaling>
        {item.description}
      </Text>
      {item.portion_label ? (
        <Text style={styles.meta} allowFontScaling>
          {item.portion_label}
          {item.quantity != null ? ` · ${item.quantity}` : ""}
        </Text>
      ) : null}
      <Text style={styles.meta} allowFontScaling>
        Carbs {item.carbs_grams != null ? `${item.carbs_grams} g` : "n/a"} · Glycemic index {item.glycemic_index ?? "n/a"}
      </Text>
      <Text style={styles.meta} allowFontScaling>
        {item.recorded_at} · {item.confirmation}
      </Text>
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
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
  },
  name: {
    flexShrink: 1,
    fontSize: typography.fontSize.headline,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  meta: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  feed: {
    gap: spacing.sm,
  },
  plans: {
    gap: spacing.sm,
  },
  planMedication: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  observationCard: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: spacing.md,
    gap: spacing.xxs,
  },
  observationTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  observationValue: {
    fontSize: typography.fontSize.body,
    color: colors.textPrimary,
  },
});