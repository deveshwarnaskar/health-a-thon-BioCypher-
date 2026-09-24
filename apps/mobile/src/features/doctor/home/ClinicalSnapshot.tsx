import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { doctorPalette, doctorSoftShadow } from "../doctorDesign";
import { SectionHeader, MetricTile, HomeInlineState } from "./DoctorHomeBits";

export function ClinicalSnapshot({
  activePatients,
  needAttention,
  cohortTir,
  hypoAlerts,
  isLoading,
  hasCohortData,
}: {
  activePatients: number;
  needAttention: number;
  cohortTir: number | null;
  hypoAlerts: number;
  isLoading: boolean;
  hasCohortData: boolean;
}) {
  return (
    <View style={styles.section}>
      <SectionHeader title="Today's Clinical Snapshot" />
      {isLoading ? (
        <View style={styles.card}>
          <Text style={styles.loadingText} allowFontScaling>
            Loading cohort clinical telemetry…
          </Text>
        </View>
      ) : (
        <View style={styles.grid}>
          <MetricTile
            icon="people"
            value={String(activePatients)}
            label="Active Cohort"
            subLabel="Enrolled patients"
            badge="Enrolled"
            dotColor={doctorPalette.primary}
          />
          <MetricTile
            icon="alert-circle"
            value={String(needAttention)}
            label="Needs Attention"
            subLabel={needAttention > 0 ? "Requires clinical action" : "All patients stable"}
            badge={needAttention > 0 ? "Priority" : "Normal"}
            dotColor={needAttention > 0 ? "#EF4444" : "#10B981"}
            valueColor={needAttention > 0 ? "#DC2626" : undefined}
          />
          <MetricTile
            icon="water"
            value={cohortTir === null ? "—" : `${cohortTir}%`}
            label="Cohort TIR"
            subLabel={
              cohortTir === null
                ? "Awaiting data"
                : cohortTir >= 70
                ? "ADA Target Met (≥70%)"
                : "Sub-target (<70%)"
            }
            badge={cohortTir !== null ? (cohortTir >= 70 ? "On Target" : "Sub-Target") : undefined}
            dotColor={cohortTir === null ? undefined : cohortTir >= 70 ? "#10B981" : "#F59E0B"}
            valueColor={cohortTir !== null && cohortTir < 70 ? "#D97706" : undefined}
          />
          <MetricTile
            icon="pulse"
            value={String(hypoAlerts)}
            label="Hypo Alerts"
            subLabel={hypoAlerts > 0 ? "Level 1 & 2 events" : "0 events in 14 days"}
            badge={hypoAlerts > 0 ? "Urgent" : "Safe"}
            dotColor={hypoAlerts > 0 ? "#EF4444" : "#10B981"}
            valueColor={hypoAlerts > 0 ? "#DC2626" : undefined}
          />
        </View>
      )}
      {!hasCohortData && !isLoading ? (
        <HomeInlineState
          icon="cloud-offline-outline"
          title="Cohort glycemic data unavailable"
          message="No confirmed glucose observations were found for the analyzed patients yet. Cohort TIR reflects analyzed patients with available data."
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: 12,
  },
  card: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 18,
    ...doctorSoftShadow,
  },
  loadingText: {
    fontSize: 13,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    gap: 10,
  },
});