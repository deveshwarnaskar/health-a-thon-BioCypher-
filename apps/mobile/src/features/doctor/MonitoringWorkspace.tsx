import React from "react";
import { StyleSheet, Text, View, ScrollView, Pressable } from "react-native";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import type { PatientSummaryResponse } from "../../services/schemas/patients";

export type MonitoringWorkspaceProps = {
  patients: PatientSummaryResponse[];
  onSelectPatient: (patient: PatientSummaryResponse) => void;
};

export function MonitoringWorkspace({ patients, onSelectPatient }: MonitoringWorkspaceProps) {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>Longitudinal Population Monitoring</Text>
        <Text style={styles.subtitle}>
          Facility-wide metabolic tracking, observation coverage, and clinical follow-up priority
        </Text>
      </View>

      {/* Summary KPI Banner */}
      <View style={styles.kpiRow}>
        <View style={styles.kpiCard}>
          <Text style={styles.kpiNumber}>{patients.length}</Text>
          <Text style={styles.kpiLabel}>Monitored Cohort</Text>
        </View>
        <View style={styles.kpiCard}>
          <Text style={[styles.kpiNumber, { color: "#47B741" }]}>
            {patients.filter((p) => p.active).length}
          </Text>
          <Text style={styles.kpiLabel}>Active Telemetry</Text>
        </View>
        <View style={styles.kpiCard}>
          <Text style={[styles.kpiNumber, { color: doctorPalette.primary }]}>ADA/EASD</Text>
          <Text style={styles.kpiLabel}>Standard Target Set</Text>
        </View>
      </View>

      {/* Invariant Banner */}
      <View style={styles.safetyCard}>
        <Text style={styles.safetyTitle}>DETERMINISTIC INTELLIGENCE GOVERNANCE</Text>
        <Text style={styles.safetyText}>
          All glycemic indicators (TIR %, TAR %, TBR %, Mean, SD, CV %, GMI %) are calculated
          deterministically from canonical timestamped readings. AI services provide context and
          guidance drafts without clinical autonomy.
        </Text>
      </View>

      {/* Patient Monitoring Table */}
      <View style={styles.tableCard}>
        <Text style={styles.tableTitle}>Patient Longitudinal Surveillance</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={{ minWidth: 600 }}>
            <View style={styles.tableHeader}>
              <Text style={[styles.th, { flex: 2 }]}>PATIENT</Text>
              <Text style={[styles.th, { flex: 1 }]}>UHID</Text>
              <Text style={[styles.th, { flex: 1.2 }]}>STATUS</Text>
              <Text style={[styles.th, { flex: 1.5 }]}>TARGET PROFILE</Text>
              <Text style={[styles.th, { flex: 1.2, textAlign: "right" }]}>INSPECT</Text>
            </View>

            {patients.map((p) => (
              <Pressable
                key={p.patient_id}
                style={styles.tableRow}
                onPress={() => onSelectPatient(p)}
              >
                <View style={[styles.cell, { flex: 2 }]}>
                  <Text style={styles.patientName}>{p.name}</Text>
                </View>
                <View style={[styles.cell, { flex: 1 }]}>
                  <Text style={styles.patientUhid}>{p.uh_id}</Text>
                </View>
                <View style={[styles.cell, { flex: 1.2 }]}>
                  <Badge
                    label={p.active ? "Monitoring Active" : "Suspended"}
                    tone={p.active ? "success" : "neutral"}
                  />
                </View>
                <View style={[styles.cell, { flex: 1.5 }]}>
                  <Text style={styles.targetText}>General (70–180 mg/dL)</Text>
                </View>
                <View style={[styles.cell, { flex: 1.2, justifyContent: "flex-end" }]}>
                  <Button
                    label="Metrics →"
                    variant="outline"
                    onPress={() => onSelectPatient(p)}
                  />
                </View>
              </Pressable>
            ))}
          </View>
        </ScrollView>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
    paddingBottom: 130,
  },
  header: {
    gap: 4,
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
  kpiRow: {
    flexDirection: "row",
    gap: spacing.md,
    flexWrap: "wrap",
  },
  kpiCard: {
    flex: 1,
    minWidth: 160,
    backgroundColor: doctorPalette.surface,
    padding: spacing.md,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    alignItems: "center",
    gap: 4,
    ...doctorSoftShadow,
  },
  kpiNumber: {
    fontSize: typography.fontSize.display,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  kpiLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  safetyCard: {
    backgroundColor: doctorPalette.surfaceBlue,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.9)",
    padding: spacing.md,
    borderRadius: doctorRadii.lg,
    gap: 4,
    ...doctorSoftShadow,
  },
  safetyTitle: {
    fontSize: 10,
    fontWeight: "800",
    color: doctorPalette.primary,
    letterSpacing: 0,
  },
  safetyText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.ink,
    lineHeight: 18,
  },
  tableCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.md,
    gap: spacing.sm,
    ...doctorSoftShadow,
  },
  tableTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "800",
    color: doctorPalette.ink,
    marginBottom: spacing.xs,
  },
  tableHeader: {
    flexDirection: "row",
    paddingVertical: spacing.xs,
    borderBottomWidth: 2,
    borderBottomColor: doctorPalette.border,
  },
  th: {
    fontSize: 11,
    fontWeight: "800",
    color: doctorPalette.quiet,
  },
  tableRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.border,
    gap: spacing.xs,
  },
  cell: {
    flexDirection: "row",
    alignItems: "center",
  },
  patientName: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  patientUhid: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  targetText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
});
