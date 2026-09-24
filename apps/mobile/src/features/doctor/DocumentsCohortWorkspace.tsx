import React, { useState } from "react";
import { StyleSheet, Text, View, ScrollView, Pressable, TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { LoadingState } from "../../components/primitives/LoadingState";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ReportViewerModal } from "./ReportViewerModal";
import type { ClinicalDocumentItem } from "./api";
import { spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import type { PatientSummaryResponse } from "../../services/schemas/patients";
import { useDoctorDocuments } from "./useDoctorDocuments";

export type DocumentsCohortWorkspaceProps = {
  patients: PatientSummaryResponse[];
  onOpenPatientById?: (patientId: string) => void;
};

export function DocumentsCohortWorkspace({
  patients,
  onOpenPatientById,
}: DocumentsCohortWorkspaceProps) {
  const [selectedPatientId, setSelectedPatientId] = useState<string>(
    patients[0]?.patient_id ?? ""
  );
  const [selectedDoc, setSelectedDoc] = useState<ClinicalDocumentItem | null>(null);

  const selectedPatient = patients.find((p) => p.patient_id === selectedPatientId);
  const { documents, isLoading, refetch } = useDoctorDocuments(selectedPatientId);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Clinical Document Repository</Text>
          <Text style={styles.subtitle}>
            Presigned secure object storage (MinIO) for lab reports, charts, and clinical records
          </Text>
        </View>
        <Button label="Refresh" variant="outline" onPress={() => refetch()} />
      </View>

      {/* Patient Picker Bar */}
      <View style={styles.patientBar}>
        <Text style={styles.patientBarLabel}>Filter by Patient:</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.patientPills}>
          {patients.map((p) => {
            const isSelected = p.patient_id === selectedPatientId;
            return (
              <Pressable
                key={p.patient_id}
                style={[styles.patientPill, isSelected ? styles.patientPillActive : null]}
                onPress={() => setSelectedPatientId(p.patient_id)}
              >
                <Text
                  style={[styles.patientPillText, isSelected ? styles.patientPillTextActive : null]}
                >
                  {p.name} ({p.uh_id})
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {/* Main Document List */}
      {isLoading ? (
        <LoadingState label="Loading patient documents…" />
      ) : documents.length === 0 ? (
        <EmptyState
          title="No documents uploaded"
          message={`No clinical documents currently recorded for ${
            selectedPatient?.name ?? "this patient"
          }.`}
        />
      ) : (
        <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
          {documents.map((doc) => (
            <View key={doc.id} style={styles.docCard}>
              <View style={styles.docIconPill}>
                <Ionicons name="document-text" size={22} color={doctorPalette.primary} />
              </View>

              <View style={styles.docInfo}>
                <View style={styles.docHeaderRow}>
                  <Text style={styles.docFilename} numberOfLines={1}>
                    {doc.filename}
                  </Text>
                  <Badge label={doc.kind.toUpperCase()} tone="info" />
                </View>

                <Text style={styles.docMeta}>
                  {doc.mime_type} · {Math.round(doc.file_size_bytes / 1024)} KB ·{" "}
                  {new Date(doc.created_at).toLocaleString()}
                </Text>

                {doc.download_url ? (
                  <View style={styles.downloadRow}>
                    <Text style={styles.downloadUrlNotice}>
                      Secure Presigned S3 Access Available
                    </Text>
                  </View>
                ) : null}
              </View>

              <View style={styles.docActionsCol}>
                <TouchableOpacity
                  style={styles.viewDocBtn}
                  onPress={() => setSelectedDoc(doc)}
                  accessibilityRole="button"
                  accessibilityLabel={`View document ${doc.filename}`}
                  activeOpacity={0.8}
                >
                  <Ionicons name="eye-outline" size={15} color="#FFFFFF" />
                  <Text style={styles.viewDocBtnText}>View / Download</Text>
                </TouchableOpacity>

                {onOpenPatientById && selectedPatient ? (
                  <Button
                    label="Patient Record"
                    variant="outline"
                    onPress={() => onOpenPatientById(selectedPatient.patient_id)}
                  />
                ) : null}
              </View>
            </View>
          ))}
        </ScrollView>
      )}

      <ReportViewerModal
        visible={!!selectedDoc}
        document={selectedDoc}
        patientName={selectedPatient?.name}
        uhid={selectedPatient?.uh_id}
        onClose={() => setSelectedDoc(null)}
      />
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
  patientBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    backgroundColor: doctorPalette.surface,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.border,
  },
  patientBarLabel: {
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
    marginRight: 6,
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
  scroll: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.lg,
    gap: spacing.md,
    paddingBottom: 130,
  },
  docCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.md,
    gap: spacing.md,
    flexWrap: "wrap",
    ...doctorSoftShadow,
  },
  docIconPill: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  docInfo: {
    flex: 1,
    gap: 4,
    minWidth: 180,
  },
  docHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  docFilename: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: doctorPalette.ink,
    flex: 1,
  },
  docMeta: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  downloadRow: {
    marginTop: 2,
  },
  downloadUrlNotice: {
    fontSize: 11,
    color: doctorPalette.primary,
    fontWeight: "800",
  },
  docActionsCol: {
    gap: spacing.xs,
    alignItems: "flex-end",
  },
  viewDocBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: doctorPalette.primary,
    paddingHorizontal: spacing.sm,
    paddingVertical: 8,
    borderRadius: doctorRadii.md,
  },
  viewDocBtnText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "700",
  },
});
