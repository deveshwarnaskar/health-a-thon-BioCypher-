import React, { useState } from "react";
import { StyleSheet, Text, View, ScrollView, Pressable } from "react-native";
import { Button } from "../../components/primitives/Button";
import { Badge } from "../../components/primitives/Badge";
import { LoadingState } from "../../components/primitives/LoadingState";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { generateClinicalReport, type ClinicalDocumentItem } from "./api";
import { spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import type { PatientSummaryResponse } from "../../services/schemas/patients";

export type ReportsWorkspaceProps = {
  patients: PatientSummaryResponse[];
  onSelectPatient: (patient: PatientSummaryResponse) => void;
};

export function ReportsWorkspace({ patients, onSelectPatient }: ReportsWorkspaceProps) {
  const [selectedPatientId, setSelectedPatientId] = useState<string>(
    patients[0]?.patient_id ?? ""
  );
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedDoc, setGeneratedDoc] = useState<ClinicalDocumentItem | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const selectedPatient = patients.find((p) => p.patient_id === selectedPatientId);

  const handleGenerate = async () => {
    if (!selectedPatientId) return;
    setIsGenerating(true);
    setErrorMsg(null);
    setGeneratedDoc(null);
    try {
      const idempotencyKey = `report-cohort-${selectedPatientId}-${Date.now()}`;
      const doc = await generateClinicalReport(
        {
          patient_id: selectedPatientId,
          report_type: "clinical_summary",
          format: "pdf",
        },
        idempotencyKey
      );
      setGeneratedDoc(doc);
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to generate report on server.");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>Clinical Report Generator & Archive</Text>
        <Text style={styles.subtitle}>
          Server-authoritative PDF/PNG clinical reports compiled deterministically with MinIO storage
        </Text>
      </View>

      {/* Generator Card */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Generate Patient Clinical Summary</Text>
        <Text style={styles.cardSubtitle}>
          Select an active patient to compile a comprehensive longitudinal clinical report
        </Text>

        <View style={styles.patientSelectorRow}>
          <Text style={styles.selectorLabel}>Target Patient:</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.patientPills}>
            {patients.map((p) => {
              const isSelected = p.patient_id === selectedPatientId;
              return (
                <Pressable
                  key={p.patient_id}
                  style={[styles.patientPill, isSelected ? styles.patientPillActive : null]}
                  onPress={() => {
                    setSelectedPatientId(p.patient_id);
                    setGeneratedDoc(null);
                    setErrorMsg(null);
                  }}
                >
                  <Text style={[styles.patientPillText, isSelected ? styles.patientPillTextActive : null]}>
                    {p.name} ({p.uh_id})
                  </Text>
                </Pressable>
              );
            })}
          </ScrollView>
        </View>

        {selectedPatient ? (
          <View style={styles.generationBox}>
            <View style={styles.metaRow}>
              <Text style={styles.metaText}>
                Selected: <Text style={styles.boldText}>{selectedPatient.name}</Text> · UHID:{" "}
                <Text style={styles.boldText}>{selectedPatient.uh_id}</Text>
              </Text>
              <Badge
                label={selectedPatient.active ? "Eligible" : "Inactive"}
                tone={selectedPatient.active ? "success" : "neutral"}
              />
            </View>

            <View style={styles.buttonRow}>
              <Button
                label={isGenerating ? "Generating Server Report…" : "Generate Official Report (PDF)"}
                variant="primary"
                disabled={isGenerating || !selectedPatient.active}
                onPress={handleGenerate}
              />
              <Button
                label="View Patient Record"
                variant="outline"
                onPress={() => onSelectPatient(selectedPatient)}
              />
            </View>
          </View>
        ) : null}

        {isGenerating ? <LoadingState label="Compiling deterministic observations and report…" /> : null}

        {errorMsg ? (
          <AlertBanner
            tone="critical"
            title="Report Generation Failed"
            message={errorMsg}
          />
        ) : null}

        {generatedDoc ? (
          <View style={styles.resultCard}>
            <Text style={styles.resultTitle}>Report Successfully Generated</Text>
            <Text style={styles.resultText}>Filename: {generatedDoc.filename}</Text>
            <Text style={styles.resultText}>
              File Size: {Math.round(generatedDoc.file_size_bytes / 1024)} KB · Format: {generatedDoc.mime_type}
            </Text>
            <Text style={styles.resultText}>
              Generated at: {new Date(generatedDoc.created_at).toLocaleString()}
            </Text>
            {generatedDoc.download_url ? (
              <View style={styles.downloadBox}>
                <Text style={styles.downloadNotice}>
                  Presigned Download URL available. Authoritative clinical document stored securely.
                </Text>
              </View>
            ) : null}
          </View>
        ) : null}
      </View>

      {/* Compliance Notice */}
      <View style={styles.noticeCard}>
        <Text style={styles.noticeTitle}>Report Provenance & Regulatory Compliance</Text>
        <Text style={styles.noticeText}>
          All clinical summary documents generated through P.L.A.T.E. are compiled directly by the
          authoritative backend ReportBuilder service, signed with timestamp provenance, and archived
          under hospital record-retention policy.
        </Text>
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
  card: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.md,
    gap: spacing.md,
    ...doctorSoftShadow,
  },
  cardTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  cardSubtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.muted,
  },
  patientSelectorRow: {
    gap: spacing.xs,
  },
  selectorLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: "700",
    color: doctorPalette.muted,
  },
  patientPills: {
    flexDirection: "row",
  },
  patientPill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    marginRight: spacing.xs,
  },
  patientPillActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.surfaceLime,
  },
  patientPillText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
    fontWeight: "700",
  },
  patientPillTextActive: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  generationBox: {
    backgroundColor: doctorPalette.surfaceSoft,
    borderRadius: doctorRadii.md,
    padding: spacing.md,
    gap: spacing.md,
  },
  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
    flexWrap: "wrap",
  },
  metaText: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.ink,
  },
  boldText: {
    fontWeight: "700",
  },
  buttonRow: {
    flexDirection: "row",
    gap: spacing.md,
    alignItems: "center",
    flexWrap: "wrap",
  },
  resultCard: {
    backgroundColor: doctorPalette.limeSoft,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.9)",
    borderRadius: doctorRadii.lg,
    padding: spacing.md,
    gap: 4,
  },
  resultTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  resultText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  downloadBox: {
    marginTop: spacing.xs,
    padding: spacing.xs,
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.md,
  },
  downloadNotice: {
    fontSize: 11,
    color: doctorPalette.primary,
    fontWeight: "800",
  },
  noticeCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.md,
    gap: 4,
    ...doctorSoftShadow,
  },
  noticeTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: "800",
    color: doctorPalette.muted,
  },
  noticeText: {
    fontSize: 11,
    color: doctorPalette.muted,
    lineHeight: 16,
  },
});
