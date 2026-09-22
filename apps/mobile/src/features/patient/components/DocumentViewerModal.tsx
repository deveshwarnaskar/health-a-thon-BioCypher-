import React, { useState } from "react";
import {
  ActivityIndicator,
  Linking,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { PatientDocumentCard } from "./PatientDocumentCard";
import { usePatientDocuments, useUploadPatientDocument } from "../api";
import type { PatientDocument } from "../types";

export type DocumentViewerModalProps = {
  visible: boolean;
  onClose: () => void;
  patientId: string | null;
};

export function DocumentViewerModal({
  visible,
  onClose,
  patientId,
}: DocumentViewerModalProps) {
  const { data: documents = [] } = usePatientDocuments(patientId);
  const uploadDoc = useUploadPatientDocument(patientId);

  const [showUploadForm, setShowUploadForm] = useState(false);
  const [docName, setDocName] = useState("");
  const [docKind, setDocKind] = useState<"lab_report" | "prescription" | "chart_image">("lab_report");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const handleOpenDocument = (doc: PatientDocument) => {
    if (doc.download_url) {
      void Linking.openURL(doc.download_url);
    }
  };

  const handleUpload = async () => {
    if (!docName.trim()) {
      setStatusMessage("Please enter a document title.");
      return;
    }

    try {
      setStatusMessage(null);
      const safeFilename = docName.trim().endsWith(".pdf")
        ? docName.trim()
        : `${docName.trim()}.pdf`;

      // Minimal placeholder PDF/base64 payload
      const mockBase64 = "JVBERi0xLjQKJcTl8uXrCg==";
      await uploadDoc.mutateAsync({
        filename: safeFilename,
        mimeType: "application/pdf",
        contentBase64: mockBase64,
        kind: docKind,
      });

      setDocName("");
      setShowUploadForm(false);
      setStatusMessage("Document queued/uploaded successfully.");
      setTimeout(() => setStatusMessage(null), 3500);
    } catch (err: any) {
      setStatusMessage(err?.message || "Failed to upload document.");
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title} allowFontScaling>
              Documents & Reports
            </Text>
            <Text style={styles.subtitle} allowFontScaling>
              Verified clinical reports and summaries
            </Text>
          </View>
          <TouchableOpacity
            style={styles.closeButton}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Close documents modal"
          >
            <Ionicons name="close" size={22} color={colors.textPrimary} />
          </TouchableOpacity>
        </View>

        <ScrollView contentContainerStyle={styles.content}>
          <View style={styles.securityBox} accessibilityRole="summary">
            <Text style={styles.securityTitle} allowFontScaling>
              Secure Medical Records
            </Text>
            <Text style={styles.securityText} allowFontScaling>
              Documents are encrypted and authorized via time-limited secure links. No clinical documents are publicly exposed.
            </Text>
          </View>

          {statusMessage && (
            <View style={styles.statusBanner}>
              <Text style={styles.statusBannerText} allowFontScaling>
                {statusMessage}
              </Text>
            </View>
          )}

          <View style={styles.actionHeaderRow}>
            <Text style={styles.sectionHeader} allowFontScaling>
              Available Records ({documents.length})
            </Text>
            <TouchableOpacity
              style={styles.uploadToggleBtn}
              onPress={() => setShowUploadForm(!showUploadForm)}
              accessibilityRole="button"
              accessibilityLabel={showUploadForm ? "Cancel upload" : "Upload new document"}
            >
              <Text style={styles.uploadToggleBtnText} allowFontScaling>
                {showUploadForm ? "Cancel" : "+ Upload Document"}
              </Text>
            </TouchableOpacity>
          </View>

          {showUploadForm && (
            <View style={styles.uploadForm}>
              <Text style={styles.formTitle} allowFontScaling>
                Upload Medical Document
              </Text>
              <Text style={styles.label} allowFontScaling>
                Document Title / Filename
              </Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. HbA1c Lab Report - Oct 2024"
                placeholderTextColor={colors.textSecondary}
                value={docName}
                onChangeText={setDocName}
                accessibilityLabel="Document title input"
              />

              <Text style={styles.label} allowFontScaling>
                Document Type
              </Text>
              <View style={styles.kindSelectorRow}>
                {(
                  [
                    { id: "lab_report", label: "Lab Report" },
                    { id: "prescription", label: "Prescription" },
                    { id: "chart_image", label: "Clinical Note" },
                  ] as const
                ).map((item) => (
                  <TouchableOpacity
                    key={item.id}
                    style={[
                      styles.kindOption,
                      docKind === item.id && styles.kindOptionActive,
                    ]}
                    onPress={() => setDocKind(item.id)}
                    accessibilityRole="button"
                    accessibilityState={{ selected: docKind === item.id }}
                  >
                    <Text
                      style={[
                        styles.kindOptionText,
                        docKind === item.id && styles.kindOptionTextActive,
                      ]}
                      allowFontScaling
                    >
                      {item.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              <TouchableOpacity
                style={[
                  styles.submitUploadBtn,
                  uploadDoc.isPending && styles.submitUploadBtnDisabled,
                ]}
                onPress={handleUpload}
                disabled={uploadDoc.isPending}
                accessibilityRole="button"
                accessibilityLabel="Submit document upload"
              >
                {uploadDoc.isPending ? (
                  <ActivityIndicator color={colors.textOnPrimary} size="small" />
                ) : (
                  <Text style={styles.submitUploadBtnText} allowFontScaling>
                    Submit Document
                  </Text>
                )}
              </TouchableOpacity>
            </View>
          )}

          {documents.length === 0 && !showUploadForm ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon} allowFontScaling>
                📄
              </Text>
              <Text style={styles.emptyTitle} allowFontScaling>
                No documents available yet
              </Text>
              <Text style={styles.emptySubtitle} allowFontScaling>
                Clinical summaries, lab reports, and consultation letters will appear here.
              </Text>
            </View>
          ) : (
            documents.map((doc) => (
              <PatientDocumentCard
                key={doc.id}
                document={doc}
                onView={handleOpenDocument}
              />
            ))
          )}
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.surface,
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  closeButton: {
    minWidth: touchTarget.min,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
  },
  closeText: {
    fontSize: 18,
    color: colors.textSecondary,
    fontWeight: "bold",
  },
  content: {
    padding: spacing.md,
  },
  securityBox: {
    backgroundColor: "#F0F7F9",
    borderRadius: radii.md,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  securityTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.primary,
    marginBottom: 2,
  },
  securityText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.xxl,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: spacing.md,
  },
  emptyTitle: {
    fontSize: typography.fontSize.headline,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  emptySubtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.xs,
    textAlign: "center",
    maxWidth: 280,
  },
  statusBanner: {
    backgroundColor: colors.tileAqua,
    padding: spacing.sm,
    borderRadius: radii.md,
    marginBottom: spacing.md,
  },
  statusBannerText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.primary,
    fontWeight: typography.weight.medium,
  },
  actionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  sectionHeader: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  uploadToggleBtn: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  uploadToggleBtnText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.semibold,
    color: colors.primary,
  },
  uploadForm: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  formTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  label: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.medium,
    color: colors.textSecondary,
    marginBottom: 4,
    marginTop: spacing.xs,
  },
  input: {
    backgroundColor: colors.backgroundRaised,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    fontSize: typography.fontSize.bodySmall,
    color: colors.textPrimary,
  },
  kindSelectorRow: {
    flexDirection: "row",
    gap: spacing.xs,
    marginTop: 4,
    marginBottom: spacing.md,
  },
  kindOption: {
    flex: 1,
    paddingVertical: spacing.xs,
    alignItems: "center",
    borderRadius: radii.pill,
    backgroundColor: colors.backgroundRaised,
    borderWidth: 1,
    borderColor: colors.border,
  },
  kindOptionActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  kindOptionText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    fontWeight: typography.weight.medium,
  },
  kindOptionTextActive: {
    color: colors.textOnPrimary,
    fontWeight: typography.weight.bold,
  },
  submitUploadBtn: {
    backgroundColor: colors.primary,
    borderRadius: radii.pill,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.xs,
  },
  submitUploadBtnDisabled: {
    opacity: 0.6,
  },
  submitUploadBtnText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
  },
});
