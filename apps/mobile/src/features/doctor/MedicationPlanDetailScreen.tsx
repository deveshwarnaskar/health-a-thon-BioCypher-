import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useAuth } from "../../auth/AuthProvider";
import { useMedicationPlan } from "./useMedicationPlan";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { Divider } from "../../components/primitives/Divider";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { colors, spacing, typography } from "../../theming/tokens";
import type { ApiErrorDetails } from "../../services/api/errors";

export type MedicationPlanDetailScreenProps = {
  planId: string;
  onBack?: () => void;
  testID?: string;
};

/**
 * ONE clinician-authored medication plan (Gate 10F-B contract → Gate 10F-M).
 * Cross-facility / deactivated-patient / missing plans never resolve (404);
 * the UI treats that as unavailable and never reveals existence.
 */
export function MedicationPlanDetailScreen({ planId, onBack, testID }: MedicationPlanDetailScreenProps) {
  const { state } = useAuth();
  const authUser = state.name === "authenticated" ? state.user : null;
  const isDoctorRole = authUser?.role === "Doctor";

  const detail = useMedicationPlan(planId, { enabled: isDoctorRole });

  if (!isDoctorRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Medication Plan" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
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

  if (detail.isError && (detail.error as ApiErrorDetails | undefined)?.httpStatus === 403) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Medication Plan" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <View testID="doctor-plan-detail-access-revoked">
            <EmptyState
              title="Access Revoked"
              message="Your access to this medication plan was removed or expired. Returning to the plans list."
            />
          </View>
          {onBack ? (
            <Button label="Return to Plans" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  if (detail.isError && (detail.error as ApiErrorDetails | undefined)?.httpStatus === 404) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Medication Plan" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <View testID="doctor-plan-detail-unavailable">
            <EmptyState title="Plan unavailable" message="This medication plan is no longer available." />
          </View>
          {onBack ? (
            <Button label="Return to Plans" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  if (detail.isLoading && !detail.plan) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Medication Plan" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <LoadingState label="Loading plan…" />
      </View>
    );
  }

  if (detail.isError || !detail.plan) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Medication Plan" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <ErrorState title="Could not load plan" message="Please try again." onRetry={() => detail.refetch()} />
        </View>
      </View>
    );
  }

  const plan = detail.plan;

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Medication Plan"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
      />

      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.medication} allowFontScaling>
            {plan.medication}
          </Text>
          {plan.active ? <Badge label="Active" tone="success" /> : <Badge label="Inactive" tone="critical" />}
        </View>
        <Text style={styles.meta} allowFontScaling>
          Patient {plan.patient_id}
        </Text>

        <Divider label="Instruction" />
        <Text style={styles.instruction} allowFontScaling>
          {plan.instruction || "No instruction"}
        </Text>

        <Divider label="Details" />
        <Text style={styles.meta} allowFontScaling>
          Prescribed by {plan.prescribed_by_role === "doctor" ? "Doctor" : plan.prescribed_by_role}
        </Text>
        <Text style={styles.meta} allowFontScaling>
          Created {plan.created_at}
        </Text>
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
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
  },
  medication: {
    flexShrink: 1,
    fontSize: typography.fontSize.headline,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  instruction: {
    fontSize: typography.fontSize.body,
    lineHeight: typography.lineHeight.body,
    color: colors.textPrimary,
  },
  meta: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
});