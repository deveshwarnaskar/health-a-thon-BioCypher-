import React, { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useAuth } from "../../auth/AuthProvider";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { Divider } from "../../components/primitives/Divider";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { DoctorPatientCard } from "../doctor/DoctorPatientCard";
import { usePatients } from "../doctor/usePatients";
import { useClinicianMeals } from "./useClinicianMeals";
import { colors, spacing, typography } from "../../theming/tokens";
import type { PatientSummaryResponse } from "../../services/schemas/patients";
import type { ClinicianMealObservation } from "./types";
import type { ApiErrorDetails } from "../../services/api/errors";

export type DietitianFlow = "patients" | "food";

export type DietitianWorkflowProps = {
  flow?: DietitianFlow;
  onHome?: () => void;
  testID?: string;
};

type ViewState =
  | { name: "cohort" }
  | { name: "patient"; patient: PatientSummaryResponse };

export function DietitianWorkflow({
  flow = "food",
  onHome,
  testID,
}: DietitianWorkflowProps) {
  const { state } = useAuth();
  const authUser = state.name === "authenticated" ? state.user : null;
  const isDietitianRole =
    authUser?.role === "Dietitian" || authUser?.role === "Doctor";

  const [view, setView] = useState<ViewState>({ name: "cohort" });

  const patients = usePatients({ enabled: isDietitianRole });

  if (!isDietitianRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Dietitian Portal"
          onBack={onHome}
          leadingLabel={onHome ? "Home" : undefined}
        />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="Nutrition review workflows are only accessible to Dietitians and authorized clinicians."
          />
          {onHome ? (
            <Button label="Return to Main Menu" variant="primary" onPress={onHome} />
          ) : null}
        </View>
      </View>
    );
  }

  if (view.name === "patient") {
    return (
      <DietitianPatientMealDetailScreen
        patient={view.patient}
        onBack={() => setView({ name: "cohort" })}
        testID={testID ? `${testID}-patient-detail` : undefined}
      />
    );
  }

  // Cohort view
  if (patients.isError && (patients.error as ApiErrorDetails | undefined)?.httpStatus === 403) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Patient Cohort"
          onBack={onHome}
          leadingLabel={onHome ? "Home" : undefined}
        />
        <View style={styles.content}>
          <View testID="dietitian-cohort-access-revoked">
            <EmptyState
              title="Access Revoked"
              message="Your access to this facility's patient cohort was removed or expired. Returning to main menu."
            />
          </View>
          {onHome ? (
            <Button label="Return to Main Menu" variant="primary" onPress={onHome} />
          ) : null}
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title={flow === "food" ? "Nutrition & Meals" : "Patient Cohort"}
        onBack={onHome}
        leadingLabel={onHome ? "Home" : undefined}
      />

      {patients.isLoading ? <LoadingState label="Loading patient cohort…" /> : null}

      {!patients.isLoading && patients.isError ? (
        <View style={styles.content}>
          <ErrorState
            title="Could not load cohort"
            message="Unable to load the patient cohort. Please try again."
            onRetry={() => patients.refetch()}
          />
        </View>
      ) : null}

      {!patients.isLoading && !patients.isError && patients.patients.length === 0 ? (
        <View style={styles.content}>
          <EmptyState
            title="No active patients"
            message="There are no active patients in your facility's cohort right now."
          />
        </View>
      ) : null}

      {!patients.isLoading && !patients.isError && patients.patients.length > 0 ? (
        <ScrollView contentContainerStyle={styles.listContent}>
          {patients.patients.map((patient) => (
            <DoctorPatientCard
              key={patient.patient_id}
              patient={patient}
              onSelect={(selected) => setView({ name: "patient", patient: selected })}
            />
          ))}
        </ScrollView>
      ) : null}
    </View>
  );
}

export type DietitianPatientMealDetailScreenProps = {
  patient: PatientSummaryResponse;
  onBack: () => void;
  testID?: string;
};

export function DietitianPatientMealDetailScreen({
  patient,
  onBack,
  testID,
}: DietitianPatientMealDetailScreenProps) {
  const mealFeed = useClinicianMeals(patient.patient_id);

  if (mealFeed.isError && (mealFeed.error as unknown as ApiErrorDetails | undefined)?.httpStatus === 403) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Nutrition Detail" onBack={onBack} leadingLabel="Back" />
        <View style={styles.content}>
          <View testID="dietitian-patient-access-revoked">
            <EmptyState
              title="Access Revoked"
              message="Your access to this patient's clinical nutrition record was removed or expired."
            />
          </View>
          <Button label="Return to Patient Cohort" variant="primary" onPress={onBack} />
        </View>
      </View>
    );
  }

  if (mealFeed.isError && (mealFeed.error as unknown as ApiErrorDetails | undefined)?.httpStatus === 404) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Nutrition Detail" onBack={onBack} leadingLabel="Back" />
        <View style={styles.content}>
          <View testID="dietitian-patient-unavailable">
            <EmptyState
              title="Patient unavailable"
              message="This patient record is no longer available."
            />
          </View>
          <Button label="Return to Patient Cohort" variant="primary" onPress={onBack} />
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar title="Nutrition Detail" onBack={onBack} leadingLabel="Back" />

      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.name} allowFontScaling>
            {patient.name}
          </Text>
          {patient.active ? (
            <Badge label="Active" tone="success" />
          ) : (
            <Badge label="Inactive" tone="critical" />
          )}
        </View>
        <Text style={styles.meta} allowFontScaling>
          UH ID {patient.uh_id}
        </Text>

        <Divider label="Clinical Nutrition & Meal Observations" />

        {mealFeed.isLoading ? (
          <LoadingState label="Loading clinical meal observations…" />
        ) : null}

        {!mealFeed.isLoading && mealFeed.isError ? (
          <ErrorState
            title="Could not load observations"
            message="Please try again."
            onRetry={() => mealFeed.refetch()}
          />
        ) : null}

        {!mealFeed.isLoading && !mealFeed.isError && mealFeed.meals.length === 0 ? (
          <EmptyState
            title="No meal observations yet"
            message="No clinical meal observations have been recorded for this patient."
          />
        ) : null}

        {!mealFeed.isLoading && !mealFeed.isError && mealFeed.meals.length > 0 ? (
          <View style={styles.feedContainer} testID="clinician-meal-feed">
            {mealFeed.meals.map((meal, index) => (
              <ClinicianMealObservationCard
                key={meal.observation_id ?? index}
                item={meal}
                testID={testID ? `${testID}-meal-${index}` : undefined}
              />
            ))}
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
}

export function ClinicianMealObservationCard({
  item,
  testID,
}: {
  item: ClinicianMealObservation;
  testID?: string;
}) {
  return (
    <View
      style={styles.observationCard}
      testID={testID}
      accessible
      accessibilityLabel={`Meal observation ${item.description}, carbs ${item.carbs_grams ?? "unknown"} grams`}
    >
      <View style={styles.cardHeader}>
        <Text style={styles.observationTitle} allowFontScaling>
          {item.description}
        </Text>
        <Badge
          label={item.confirmation === "confirmed" ? "Confirmed" : "Draft"}
          tone={item.confirmation === "confirmed" ? "success" : "warning"}
        />
      </View>

      {item.portion_label ? (
        <Text style={styles.meta} allowFontScaling>
          Portion: {item.portion_label}
          {item.quantity != null ? ` (${item.quantity}x)` : ""}
        </Text>
      ) : null}

      <View style={styles.nutritionRow}>
        <Text style={styles.nutritionMetric} allowFontScaling>
          Carbohydrates: {item.carbs_grams != null ? `${item.carbs_grams} g` : "n/a"}
        </Text>
        <Text style={styles.nutritionMetric} allowFontScaling>
          Glycemic Index: {item.glycemic_index ?? "n/a"}
        </Text>
      </View>

      <Text style={styles.timestamp} allowFontScaling>
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
  listContent: {
    padding: spacing.md,
    gap: spacing.sm,
    paddingBottom: spacing.xxl,
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
  },
  name: {
    fontSize: typography.fontSize.headline,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  meta: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  feedContainer: {
    gap: spacing.sm,
  },
  observationCard: {
    backgroundColor: colors.surface,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    gap: spacing.xs,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  observationTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
    flexShrink: 1,
  },
  nutritionRow: {
    flexDirection: "row",
    gap: spacing.md,
    marginVertical: spacing.xs,
  },
  nutritionMetric: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "500",
    color: colors.textPrimary,
  },
  timestamp: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
});
