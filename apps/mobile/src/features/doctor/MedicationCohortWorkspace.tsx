import React, { useState } from "react";
import { StyleSheet, Text, View, ScrollView, Pressable } from "react-native";
import { useMedicationPlans } from "./useMedicationPlans";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { LoadingState } from "../../components/primitives/LoadingState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { EmptyState } from "../../components/primitives/EmptyState";
import { spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import type { PatientSummaryResponse } from "../../services/schemas/patients";
import type { MedicationPlanResponse } from "../../services/schemas/medication";

export type MedicationCohortWorkspaceProps = {
  patients: PatientSummaryResponse[];
  onOpenPatientById?: (patientId: string) => void;
  onAuthorPlanForPatient?: (patient: PatientSummaryResponse) => void;
};

export function MedicationCohortWorkspace({
  patients,
  onOpenPatientById,
  onAuthorPlanForPatient,
}: MedicationCohortWorkspaceProps) {
  const { plans, planCount, isLoading, isError, refetch } = useMedicationPlans();
  const [activeFilter, setActiveFilter] = useState<"all" | "active" | "inactive">("all");

  const filteredPlans = plans.filter((p) => {
    if (activeFilter === "active") return p.active;
    if (activeFilter === "inactive") return !p.active;
    return true;
  });

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Medication Regimens & Authorizations</Text>
          <Text style={styles.subtitle}>
            Clinician-authored pharmacotherapy plans across facility cohort ({planCount} total)
          </Text>
        </View>
        <Button label="Refresh Plans" variant="outline" onPress={() => refetch()} />
      </View>

      {/* Safety Invariant Notice */}
      <View style={styles.invariantBox}>
        <Text style={styles.invariantTitle}>MEDICATION SAFETY INVARIANT</Text>
        <Text style={styles.invariantText}>
          AI does not titrate, prescribe, or discontinue medications. To alter a regimen,
          the clinician authors a new plan which supersedes previous authorizations in accordance
          with the longitudinal audit trail.
        </Text>
      </View>

      {/* Filter Chips */}
      <View style={styles.filterRow}>
        {(["all", "active", "inactive"] as const).map((filter) => (
          <Pressable
            key={filter}
            style={[styles.filterChip, activeFilter === filter ? styles.filterChipActive : null]}
            onPress={() => setActiveFilter(filter)}
          >
            <Text style={[styles.filterText, activeFilter === filter ? styles.filterTextActive : null]}>
              {filter === "all"
                ? `All Plans (${planCount})`
                : filter === "active"
                ? `Active (${plans.filter((p) => p.active).length})`
                : `Inactive (${plans.filter((p) => !p.active).length})`}
            </Text>
          </Pressable>
        ))}
      </View>

      {/* Main List */}
      {isLoading ? (
        <LoadingState label="Loading medication regimens…" />
      ) : isError ? (
        <ErrorState
          title="Could not load medication plans"
          message="Failed to retrieve facility medication plans."
          onRetry={() => refetch()}
        />
      ) : filteredPlans.length === 0 ? (
        <EmptyState
          title="No medication plans"
          message="No plans match the selected filter."
        />
      ) : (
        <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
          {filteredPlans.map((plan) => {
            const patientObj = patients.find((p) => p.patient_id === plan.patient_id);
            return (
              <View key={plan.medication_plan_id} style={styles.card}>
                <View style={styles.cardHeader}>
                  <View style={styles.cardHeaderLeft}>
                    <Text style={styles.medicationName}>{plan.medication}</Text>
                    <Badge
                      label={plan.active ? "ACTIVE" : "INACTIVE"}
                      tone={plan.active ? "success" : "neutral"}
                    />
                  </View>
                  <Text style={styles.planDate}>
                    {new Date(plan.created_at).toLocaleDateString()}
                  </Text>
                </View>

                <Text style={styles.instructionText}>
                  {plan.instruction || "No specific instructions provided."}
                </Text>

                <View style={styles.cardFooter}>
                  <View style={styles.patientInfoRow}>
                    <Text style={styles.patientInfoLabel}>Patient:</Text>
                    <Text style={styles.patientInfoName}>
                      {patientObj ? patientObj.name : `ID: ${plan.patient_id.slice(0, 8)}…`}
                    </Text>
                    {patientObj ? (
                      <Text style={styles.uhidText}>({patientObj.uh_id})</Text>
                    ) : null}
                  </View>

                  <View style={styles.actionButtons}>
                    {patientObj && onAuthorPlanForPatient ? (
                      <Button
                        label="Author Replacement Plan"
                        variant="outline"
                        onPress={() => onAuthorPlanForPatient(patientObj)}
                      />
                    ) : null}

                    {onOpenPatientById ? (
                      <Button
                        label="Open Patient Workspace →"
                        variant="primary"
                        onPress={() => onOpenPatientById(plan.patient_id)}
                      />
                    ) : null}
                  </View>
                </View>
              </View>
            );
          })}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  title: {
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  subtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.muted,
    fontWeight: "600",
  },
  invariantBox: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.xs,
    backgroundColor: doctorPalette.criticalSoft,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.9)",
    padding: spacing.md,
    borderRadius: doctorRadii.lg,
    gap: 2,
    ...doctorSoftShadow,
  },
  invariantTitle: {
    fontSize: 10,
    fontWeight: "800",
    color: "#BE185D",
    letterSpacing: 0.5,
  },
  invariantText: {
    fontSize: 11,
    color: "#9D174D",
    lineHeight: 16,
  },
  filterRow: {
    flexDirection: "row",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    backgroundColor: doctorPalette.surface,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.border,
    marginTop: spacing.sm,
    flexWrap: "wrap",
  },
  filterChip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
  },
  filterChipActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.surfaceLime,
  },
  filterText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
    fontWeight: "700",
  },
  filterTextActive: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.lg,
    gap: spacing.md,
    paddingBottom: 130,
  },
  card: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.md,
    gap: spacing.sm,
    ...doctorSoftShadow,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  cardHeaderLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  medicationName: {
    fontSize: typography.fontSize.body,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  planDate: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  instructionText: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.ink,
    lineHeight: 20,
  },
  cardFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: doctorPalette.border,
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  patientInfoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  patientInfoLabel: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  patientInfoName: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  uhidText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  actionButtons: {
    flexDirection: "row",
    gap: spacing.xs,
    flexWrap: "wrap",
  },
});
