import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useAuth } from "../../auth/AuthProvider";
import { usePatientDetail } from "./usePatientDetail";
import { useClinicianFeed } from "./useClinicianFeed";
import { useMedicationPlans } from "./useMedicationPlans";
import { usePatientDocuments } from "../patient/api";
import {
  calculateGlycemicMetrics,
  calculatePersonalBaseline,
  calculateTemporalAlignment,
  calculateDataCoverage,
  type GlucoseInputObservation,
  type MealInputObservation,
} from "../../services/clinical/deterministicIntelligence";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { AppCard } from "../../components/primitives/AppCard";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { Divider } from "../../components/primitives/Divider";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { colors, radii, spacing, typography } from "../../theming/tokens";
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
  const docs = usePatientDocuments(patientId, { enabled: isDoctorRole });

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
  const feedItems = feed.feed?.items || [];

  const glucoseItems: GlucoseInputObservation[] = feedItems
    .filter(
      (item): item is ClinicianGlucoseObservation & { kind: "glucose" } =>
        item.kind === "glucose" && item.value_mg_dl != null
    )
    .map((g) => ({
      id: g.observation_id,
      value_mg_dl: g.value_mg_dl!,
      taken_at: g.taken_at,
      tag: g.tag,
    }));

  const mealItems: MealInputObservation[] = feedItems
    .filter(
      (item): item is ClinicianMealObservation & { kind: "meal" } =>
        item.kind === "meal"
    )
    .map((m) => ({
      id: m.observation_id,
      description: m.description,
      recorded_at: m.recorded_at,
      portion_label: m.portion_label,
      carbs_grams: m.carbs_grams,
    }));

  const metrics = calculateGlycemicMetrics(glucoseItems, 14);
  const baseline = calculatePersonalBaseline(glucoseItems, 14);
  const coverage = calculateDataCoverage(glucoseItems, mealItems, 14);
  const temporalAlignments = calculateTemporalAlignment(mealItems, glucoseItems, 240);
  const patientDocs = docs.data || [];

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

        <Divider label="P.L.A.T.E. Glycemic Analytics" />
        <View style={styles.analyticsCard}>
          <View style={styles.analyticsHeaderRow}>
            <Text style={styles.analyticsTitle} allowFontScaling>
              14-Day Deterministic Glycemic Summary
            </Text>
            <Badge
              label={coverage.isContinuous ? "Adequate Coverage" : "Sparse Data"}
              tone={coverage.isContinuous ? "success" : "warning"}
            />
          </View>

          <View style={styles.metricsGrid}>
            <View style={styles.metricCell}>
              <Text style={styles.metricLabel} allowFontScaling>Time in Range</Text>
              <Text style={styles.metricValue} allowFontScaling>
                {metrics.timeInRangePct != null ? `${metrics.timeInRangePct}%` : "—"}
              </Text>
              <Text style={styles.metricSubtext} allowFontScaling>70–180 mg/dL</Text>
            </View>

            <View style={styles.metricCell}>
              <Text style={styles.metricLabel} allowFontScaling>Time Below Range</Text>
              <Text style={styles.metricValue} allowFontScaling>
                {metrics.timeBelowRangePct != null ? `${metrics.timeBelowRangePct}%` : "—"}
              </Text>
              <Text style={styles.metricSubtext} allowFontScaling>&lt;70 mg/dL</Text>
            </View>

            <View style={styles.metricCell}>
              <Text style={styles.metricLabel} allowFontScaling>Time Above Range</Text>
              <Text style={styles.metricValue} allowFontScaling>
                {metrics.timeAboveRangePct != null ? `${metrics.timeAboveRangePct}%` : "—"}
              </Text>
              <Text style={styles.metricSubtext} allowFontScaling>&gt;180 mg/dL</Text>
            </View>

            <View style={styles.metricCell}>
              <Text style={styles.metricLabel} allowFontScaling>Mean Glucose</Text>
              <Text style={styles.metricValue} allowFontScaling>
                {metrics.meanMgDl != null ? `${metrics.meanMgDl} mg/dL` : "—"}
              </Text>
              <Text style={styles.metricSubtext} allowFontScaling>
                SD: {metrics.standardDeviationMgDl != null ? `±${metrics.standardDeviationMgDl}` : "—"}
              </Text>
            </View>

            <View style={styles.metricCell}>
              <Text style={styles.metricLabel} allowFontScaling>Glycemic Var (CV)</Text>
              <Text style={styles.metricValue} allowFontScaling>
                {metrics.coefficientOfVariationPct != null ? `${metrics.coefficientOfVariationPct}%` : "—"}
              </Text>
              <Text style={styles.metricSubtext} allowFontScaling>Target: &lt;36%</Text>
            </View>

            <View style={styles.metricCell}>
              <Text style={styles.metricLabel} allowFontScaling>GMI</Text>
              <Text style={styles.metricValue} allowFontScaling>
                {metrics.gmiPct != null ? `${metrics.gmiPct}%` : "—"}
              </Text>
              <Text style={styles.metricSubtext} allowFontScaling>
                Est. A1c: {metrics.estimatedA1cPct != null ? `${metrics.estimatedA1cPct}%` : "—"}
              </Text>
            </View>
          </View>

          <Text style={styles.analyticsInterpretation} allowFontScaling>
            {metrics.interpretationSummary}
          </Text>

          <View style={styles.baselineDivider} />

          <Text style={styles.baselineSectionTitle} allowFontScaling>
            Personal Rolling Baseline & Data Presence
          </Text>
          <Text style={styles.baselineNote} allowFontScaling>
            • {baseline.descriptiveNote}
          </Text>
          <Text style={styles.baselineNote} allowFontScaling>
            • Coverage: {coverage.coverageText} ({coverage.glucoseReadingCount} glucose, {coverage.mealRecordCount} meals).
          </Text>
        </View>

        <Divider label="Temporal Food & Glucose Alignments" />
        {temporalAlignments.length === 0 ? (
          <Text style={styles.emptyInlineText} allowFontScaling>
            No aligned meal and post-meal readings within 4 hours.
          </Text>
        ) : (
          <View style={styles.feed}>
            {temporalAlignments.slice(0, 4).map((align, idx) => (
              <View key={idx} style={styles.alignmentCard}>
                <View style={styles.alignmentHeader}>
                  <Text style={styles.alignmentMealName} allowFontScaling>
                    {align.mealDescription}
                  </Text>
                  <Badge label={align.windowLabel} tone="info" />
                </View>
                <Text style={styles.alignmentValue} allowFontScaling>
                  Associated Glucose: {align.glucoseMgDl} mg/dL
                </Text>
                <Text style={styles.alignmentNote} allowFontScaling>
                  {align.relationshipNote}
                </Text>
              </View>
            ))}
          </View>
        )}

        <Divider label="Clinical Documents & Reports" />
        {docs.isLoading ? <LoadingState label="Loading patient documents…" /> : null}
        {!docs.isLoading && patientDocs.length === 0 ? (
          <Text style={styles.emptyInlineText} allowFontScaling>
            No clinical documents or reports available for this patient.
          </Text>
        ) : null}
        {!docs.isLoading && patientDocs.length > 0 ? (
          <View style={styles.feed}>
            {patientDocs.map((d) => {
              const isVerified =
                (d as any).status === "VERIFIED" ||
                (d as any).verification_status === "VERIFIED";
              return (
                <View key={d.id} style={styles.documentRowCard}>
                  <View style={styles.documentIconContainer}>
                    <Text style={styles.docIconText} allowFontScaling>
                      📄
                    </Text>
                  </View>
                  <View style={styles.documentInfo}>
                    <Text style={styles.documentTitle} allowFontScaling numberOfLines={1}>
                      {d.filename}
                    </Text>
                    <Text style={styles.meta} allowFontScaling>
                      {d.kind} · {d.file_size_bytes ? `${Math.round(d.file_size_bytes / 1024)} KB` : "Document"}
                    </Text>
                  </View>
                  <Badge
                    label={isVerified ? "Verified" : "Pending"}
                    tone={isVerified ? "success" : "neutral"}
                  />
                </View>
              );
            })}
          </View>
        ) : null}

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
  analyticsCard: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    padding: spacing.md,
    gap: spacing.sm,
  },
  analyticsHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  analyticsTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    flex: 1,
    marginRight: spacing.xs,
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginVertical: spacing.xs,
  },
  metricCell: {
    flexBasis: "31%",
    flexGrow: 1,
    backgroundColor: colors.backgroundRaised,
    borderRadius: radii.md,
    padding: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
  },
  metricLabel: {
    fontSize: 10,
    fontWeight: typography.weight.semibold,
    color: colors.textSecondary,
    textTransform: "uppercase",
  },
  metricValue: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
    color: colors.primary,
    marginTop: 2,
  },
  metricSubtext: {
    fontSize: 10,
    color: colors.textSecondary,
    marginTop: 1,
  },
  analyticsInterpretation: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    fontStyle: "italic",
    lineHeight: 16,
  },
  baselineDivider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.xxs,
  },
  baselineSectionTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  baselineNote: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  emptyInlineText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    fontStyle: "italic",
    paddingVertical: spacing.xs,
  },
  alignmentCard: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    padding: spacing.sm,
    gap: 4,
  },
  alignmentHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  alignmentMealName: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  alignmentValue: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.primary,
    fontWeight: typography.weight.semibold,
  },
  alignmentNote: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  documentRowCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    padding: spacing.sm,
    gap: spacing.sm,
  },
  documentIconContainer: {
    width: 32,
    height: 32,
    borderRadius: radii.pill,
    backgroundColor: colors.tileAqua,
    alignItems: "center",
    justifyContent: "center",
  },
  docIconText: {
    fontSize: 16,
  },
  documentInfo: {
    flex: 1,
  },
  documentTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.semibold,
    color: colors.textPrimary,
  },
});