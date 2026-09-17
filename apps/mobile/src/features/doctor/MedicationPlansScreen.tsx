import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useAuth } from "../../auth/AuthProvider";
import { useMedicationPlans } from "./useMedicationPlans";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { AppCard } from "../../components/primitives/AppCard";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { colors, spacing, typography } from "../../theming/tokens";
import type { MedicationPlanResponse } from "../../services/schemas/medication";
import type { ApiErrorDetails } from "../../services/api/errors";

export type MedicationPlansScreenProps = {
  onSelect?: (plan: MedicationPlanResponse) => void;
  onBack?: () => void;
  testID?: string;
};

/**
 * Facility-scoped medication-plan list (Gate 10F-B contract → Gate 10F-M).
 * Clinician-authored instructions are clinician-read-only DTOs; proxy roles
 * never reach this surface.
 */
export function MedicationPlansScreen({ onSelect, onBack, testID }: MedicationPlansScreenProps) {
  const { state } = useAuth();
  const authUser = state.name === "authenticated" ? state.user : null;
  const isDoctorRole = authUser?.role === "Doctor";

  const plans = useMedicationPlans(undefined, { enabled: isDoctorRole });

  if (!isDoctorRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Medication Plans" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="Medication plans are only available in Doctor mode."
          />
        </View>
      </View>
    );
  }

  if (plans.isError && (plans.error as ApiErrorDetails | undefined)?.httpStatus === 403) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Medication Plans" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <View testID="doctor-plans-access-revoked">
            <EmptyState
              title="Access Revoked"
              message="Your access to medication plans was removed or expired. Returning to the main menu."
            />
          </View>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Medication Plans"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
      />

      {plans.isLoading ? <LoadingState label="Loading medication plans…" /> : null}

      {!plans.isLoading && plans.isError ? (
        <View style={styles.content}>
          <ErrorState
            title="Could not load medication plans"
            message="Please try again."
            onRetry={() => plans.refetch()}
          />
        </View>
      ) : null}

      {!plans.isLoading && !plans.isError && plans.plans.length === 0 ? (
        <View style={styles.content}>
          <EmptyState
            title="No medication plans"
            message="There are no clinician-authored medication plans in your facility."
          />
        </View>
      ) : null}

      {!plans.isLoading && !plans.isError && plans.plans.length > 0 ? (
        <ScrollView contentContainerStyle={styles.listContent}>
          {plans.plans.map((plan) => (
            <AppCard
              key={plan.medication_plan_id}
              accessibilityLabel={`Medication plan ${plan.medication}`}
              onPress={onSelect ? () => onSelect(plan) : undefined}
            >
              <Text style={styles.medication} allowFontScaling>
                {plan.medication}
              </Text>
              <Text style={styles.meta} allowFontScaling>
                {plan.instruction || "No instruction"}
              </Text>
              <Text style={styles.meta} allowFontScaling>
                Patient {plan.patient_id} · {plan.active ? "Active" : "Inactive"}
              </Text>
            </AppCard>
          ))}
        </ScrollView>
      ) : null}
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
  medication: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  meta: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
});