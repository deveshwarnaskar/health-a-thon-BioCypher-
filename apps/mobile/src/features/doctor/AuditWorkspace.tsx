import React from "react";
import { StyleSheet, Text, View, ScrollView, Pressable } from "react-native";
import { Badge } from "../../components/primitives/Badge";
import { spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import type { PatientSummaryResponse } from "../../services/schemas/patients";

export type AuditWorkspaceProps = {
  patients: PatientSummaryResponse[];
  onSelectPatient: (patient: PatientSummaryResponse) => void;
};

export function AuditWorkspace({ patients, onSelectPatient }: AuditWorkspaceProps) {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>Clinical Audit & Provenance Trail</Text>
        <Text style={styles.subtitle}>
          Regulatory compliance, immutable transactional history, and clinical authorization logs
        </Text>
      </View>

      {/* Pipeline Diagram Card */}
      <View style={styles.pipelineCard}>
        <Text style={styles.pipelineTitle}>P.L.A.T.E. ARCHITECTURAL LIFECYCLE</Text>
        <View style={styles.stepsRow}>
          {[
            "Capture",
            "Validate",
            "Normalize",
            "Calculate",
            "Contextualize",
            "Evidence",
            "Review",
            "Audit",
          ].map((step, idx) => (
            <View key={step} style={styles.stepBox}>
              <Text style={styles.stepNum}>{idx + 1}</Text>
              <Text style={styles.stepName}>{step}</Text>
            </View>
          ))}
        </View>
        <Text style={styles.pipelineDescription}>
          Zero blind overwrites. Deterministic mathematical calculations happen BEFORE any assistive
          AI contextualization. AI cannot diagnose, titrate, or prescribe autonomously.
        </Text>
      </View>

      {/* Cohort Audit Compliance List */}
      <View style={styles.tableCard}>
        <Text style={styles.tableTitle}>Patient Record Audit Status</Text>
        <View style={styles.tableHeader}>
          <Text style={[styles.th, { flex: 2 }]}>PATIENT NAME</Text>
          <Text style={[styles.th, { flex: 1.2 }]}>UHID</Text>
          <Text style={[styles.th, { flex: 1.5 }]}>IMMUTABILITY</Text>
          <Text style={[styles.th, { flex: 1.2, textAlign: "right" }]}>TIMELINE</Text>
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
            <View style={[styles.cell, { flex: 1.2 }]}>
              <Text style={styles.patientUhid}>{p.uh_id}</Text>
            </View>
            <View style={[styles.cell, { flex: 1.5 }]}>
              <Badge label="CANONICAL RLS" tone="success" />
            </View>
            <View style={[styles.cell, { flex: 1.2, justifyContent: "flex-end" }]}>
              <Text style={styles.inspectText}>Inspect</Text>
            </View>
          </Pressable>
        ))}
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
    paddingBottom: spacing.xxl,
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
  pipelineCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.md,
    gap: spacing.md,
    ...doctorSoftShadow,
  },
  pipelineTitle: {
    fontSize: 11,
    fontWeight: "800",
    color: doctorPalette.primary,
    letterSpacing: 0,
  },
  stepsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  stepBox: {
    backgroundColor: doctorPalette.surfaceBlue,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.9)",
    borderRadius: doctorRadii.md,
    paddingHorizontal: 10,
    paddingVertical: 6,
    alignItems: "center",
    minWidth: 72,
  },
  stepNum: {
    fontSize: 10,
    fontWeight: "800",
    color: doctorPalette.primary,
  },
  stepName: {
    fontSize: 11,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  pipelineDescription: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
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
    flexWrap: "wrap",
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
  inspectText: {
    fontSize: typography.fontSize.caption,
    fontWeight: "800",
    color: doctorPalette.primary,
  },
});
