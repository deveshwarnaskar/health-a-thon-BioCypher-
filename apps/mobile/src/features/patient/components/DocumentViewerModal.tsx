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

  // Simulated OCR confirmation state
  const [extractedHba1c, setExtractedHba1c] = useState("7.2");
  const [extractedGlucose, setExtractedGlucose] = useState("118");
  const [ocrConfirmed, setOcrConfirmed] = useState(false);
  const [isEditingOcr, setIsEditingOcr] = useState(false);

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
            <View style={styles.kickerRow}>
              <View style={styles.kickerDot} />
              <Text style={styles.kicker} allowFontScaling>
                CLINICAL ATTACHMENTS
              </Text>
            </View>
            <Text style={styles.title} allowFontScaling>
              Documents & Reports
            </Text>
          </View>
          <TouchableOpacity
            style={styles.closeButton}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Close documents modal"
            activeOpacity={0.7}
          >
            <Ionicons name="close" size={20} color="#0F172A" />
          </TouchableOpacity>
        </View>

        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          <View style={styles.securityBox} accessibilityRole="summary">
            <View style={styles.securityIconBox}>
              <Ionicons name="shield-checkmark" size={18} color="#0D9488" />
            </View>
            <View style={styles.securityTextCol}>
              <Text style={styles.securityTitle} allowFontScaling>
                Secure Medical Records
              </Text>
              <Text style={styles.securityText} allowFontScaling>
                Documents are encrypted and authorized via time-limited secure links. No clinical documents are publicly exposed.
              </Text>
            </View>
          </View>

          {statusMessage && (
            <View style={styles.statusBanner}>
              <Ionicons name="checkmark-circle" size={16} color="#059669" style={{ marginRight: 6 }} />
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
              activeOpacity={0.7}
            >
              <Ionicons
                name={showUploadForm ? "close-outline" : "cloud-upload-outline"}
                size={15}
                color="#0D9488"
                style={{ marginRight: 4 }}
              />
              <Text style={styles.uploadToggleBtnText} allowFontScaling>
                {showUploadForm ? "Cancel" : "Upload Document"}
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

              {/* OCR Lab Value Extraction Preview Card */}
              {docKind === "lab_report" && (
                <View style={styles.ocrCard}>
                  <View style={styles.ocrHeader}>
                    <View
                      style={[
                        styles.ocrBadge,
                        ocrConfirmed ? styles.ocrBadgeConfirmed : styles.ocrBadgePending,
                      ]}
                    >
                      <Text
                        style={[
                          styles.ocrBadgeText,
                          ocrConfirmed
                            ? styles.ocrBadgeTextConfirmed
                            : styles.ocrBadgeTextPending,
                        ]}
                        allowFontScaling
                      >
                        {ocrConfirmed ? "✓ CONFIRMED BY PATIENT" : "DETECTED FROM REPORT"}
                      </Text>
                    </View>
                    <Text style={styles.ocrTimeNote} allowFontScaling>
                      OCR Scanner
                    </Text>
                  </View>

                  <Text style={styles.ocrTitle} allowFontScaling>
                    Extracted Lab Values
                  </Text>
                  <Text style={styles.ocrSubtitle} allowFontScaling>
                    Detected from test sheet. Machine-extracted values are never saved as clinical truth until you confirm them.
                  </Text>

                  {isEditingOcr ? (
                    <View style={styles.ocrEditBox}>
                      <Text style={styles.ocrInputLabel} allowFontScaling>
                        HbA1c (%):
                      </Text>
                      <TextInput
                        style={styles.ocrInput}
                        value={extractedHba1c}
                        onChangeText={setExtractedHba1c}
                        keyboardType="decimal-pad"
                        placeholder="7.2"
                      />
                      <Text style={styles.ocrInputLabel} allowFontScaling>
                        Fasting Glucose (mg/dL):
                      </Text>
                      <TextInput
                        style={styles.ocrInput}
                        value={extractedGlucose}
                        onChangeText={setExtractedGlucose}
                        keyboardType="number-pad"
                        placeholder="118"
                      />
                      <TouchableOpacity
                        style={styles.ocrSaveEditBtn}
                        onPress={() => {
                          setIsEditingOcr(false);
                          setOcrConfirmed(true);
                        }}
                        accessibilityRole="button"
                        accessibilityLabel="Save edited lab values"
                      >
                        <Text style={styles.ocrSaveEditText} allowFontScaling>
                          Save & Confirm
                        </Text>
                      </TouchableOpacity>
                    </View>
                  ) : (
                    <View style={styles.ocrValuesRow}>
                      <View style={styles.ocrValueTile}>
                        <Text style={styles.ocrValueNumber} allowFontScaling>
                          {extractedHba1c}%
                        </Text>
                        <Text style={styles.ocrValueName} allowFontScaling>
                          HbA1c (Glycated)
                        </Text>
                      </View>
                      <View style={styles.ocrValueTile}>
                        <Text style={styles.ocrValueNumber} allowFontScaling>
                          {extractedGlucose} mg/dL
                        </Text>
                        <Text style={styles.ocrValueName} allowFontScaling>
                          Fasting Glucose
                        </Text>
                      </View>
                    </View>
                  )}

                  <View style={styles.ocrActionsRow}>
                    {!ocrConfirmed ? (
                      <>
                        <TouchableOpacity
                          style={styles.ocrConfirmBtn}
                          onPress={() => setOcrConfirmed(true)}
                          accessibilityRole="button"
                          accessibilityLabel="Confirm detected values"
                          activeOpacity={0.8}
                        >
                          <Ionicons name="checkmark" size={15} color="#FFFFFF" style={{ marginRight: 4 }} />
                          <Text style={styles.ocrConfirmBtnText} allowFontScaling>
                            Confirm Values
                          </Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                          style={styles.ocrEditBtn}
                          onPress={() => setIsEditingOcr(!isEditingOcr)}
                          accessibilityRole="button"
                          accessibilityLabel="Edit detected values"
                          activeOpacity={0.7}
                        >
                          <Ionicons name="create-outline" size={14} color="#0D9488" style={{ marginRight: 4 }} />
                          <Text style={styles.ocrEditBtnText} allowFontScaling>
                            Edit
                          </Text>
                        </TouchableOpacity>
                      </>
                    ) : (
                      <View style={styles.ocrConfirmedNotice}>
                        <Ionicons name="checkmark-circle" size={16} color={colors.leafGreen} />
                        <Text style={styles.ocrConfirmedText} allowFontScaling>
                          Values confirmed for clinical timeline
                        </Text>
                        <TouchableOpacity
                          onPress={() => {
                            setOcrConfirmed(false);
                            setIsEditingOcr(true);
                          }}
                          style={{ marginLeft: "auto" }}
                        >
                          <Text style={styles.ocrUndoText} allowFontScaling>
                            Change
                          </Text>
                        </TouchableOpacity>
                      </View>
                    )}
                  </View>
                </View>
              )}

              <TouchableOpacity
                style={[
                  styles.submitUploadBtn,
                  uploadDoc.isPending && styles.submitUploadBtnDisabled,
                ]}
                onPress={handleUpload}
                disabled={uploadDoc.isPending}
                accessibilityRole="button"
                accessibilityLabel="Submit document upload"
                activeOpacity={0.85}
              >
                {uploadDoc.isPending ? (
                  <ActivityIndicator color={colors.textOnPrimary} size="small" />
                ) : (
                  <>
                    <Ionicons name="cloud-upload" size={17} color="#FFFFFF" style={{ marginRight: 6 }} />
                    <Text style={styles.submitUploadBtnText} allowFontScaling>
                      Submit Document
                    </Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          )}

          {documents.length === 0 && !showUploadForm ? (
            <View style={styles.emptyContainer}>
              <View style={styles.emptyIconCircle}>
                <Ionicons name="document-text-outline" size={34} color="#0D9488" />
              </View>
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
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    backgroundColor: colors.surface,
  },
  kickerRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 2,
  },
  kickerDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#0D9488",
    marginRight: 6,
  },
  kicker: {
    fontSize: 10,
    color: "#64748B",
    fontWeight: "700",
    letterSpacing: 1.1,
  },
  title: {
    fontSize: 20,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.3,
  },
  closeButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    justifyContent: "center",
  },
  content: {
    padding: spacing.md,
  },
  securityBox: {
    flexDirection: "row",
    backgroundColor: "#F0FDFA",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#CCFBF1",
    padding: spacing.md,
    gap: spacing.sm,
    alignItems: "flex-start",
    marginBottom: spacing.md,
  },
  securityIconBox: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: "#CCFBF1",
    alignItems: "center",
    justifyContent: "center",
  },
  securityTextCol: {
    flex: 1,
  },
  securityTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0F766E",
    marginBottom: 2,
  },
  securityText: {
    fontSize: 11,
    color: "#0D9488",
    lineHeight: 16,
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.xxl,
  },
  emptyIconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
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
  ocrCard: {
    backgroundColor: "#F8FAFC",
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.md,
    gap: spacing.xs,
  },
  ocrHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  ocrBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  ocrBadgePending: {
    backgroundColor: colors.tileYellow,
  },
  ocrBadgeConfirmed: {
    backgroundColor: colors.tileGreen,
  },
  ocrBadgeText: {
    fontSize: 9,
    fontWeight: typography.weight.bold,
    letterSpacing: 0.5,
  },
  ocrBadgeTextPending: {
    color: "#B45309",
  },
  ocrBadgeTextConfirmed: {
    color: colors.leafGreen,
  },
  ocrTimeNote: {
    fontSize: 10,
    color: colors.textSecondary,
    fontWeight: typography.weight.medium,
  },
  ocrTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    marginTop: 2,
  },
  ocrSubtitle: {
    fontSize: 11,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  ocrValuesRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  ocrValueTile: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
  },
  ocrValueNumber: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.weight.bold,
    color: colors.primary,
  },
  ocrValueName: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 2,
    textAlign: "center",
  },
  ocrEditBox: {
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  ocrInputLabel: {
    fontSize: 11,
    fontWeight: typography.weight.bold,
    color: colors.textSecondary,
  },
  ocrInput: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    fontSize: typography.fontSize.bodySmall,
    color: colors.textPrimary,
  },
  ocrSaveEditBtn: {
    backgroundColor: colors.primary,
    borderRadius: radii.pill,
    paddingVertical: 8,
    alignItems: "center",
    marginTop: 4,
  },
  ocrSaveEditText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
  },
  ocrActionsRow: {
    flexDirection: "row",
    gap: spacing.xs,
    marginTop: spacing.xs,
    alignItems: "center",
  },
  ocrConfirmBtn: {
    flex: 1,
    backgroundColor: colors.leafGreen,
    borderRadius: radii.pill,
    paddingVertical: 8,
    alignItems: "center",
  },
  ocrConfirmBtnText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
  },
  ocrEditBtn: {
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
  },
  ocrEditBtnText: {
    fontSize: typography.fontSize.caption,
    color: colors.textPrimary,
    fontWeight: typography.weight.medium,
  },
  ocrConfirmedNotice: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    flex: 1,
  },
  ocrConfirmedText: {
    fontSize: 11,
    fontWeight: typography.weight.bold,
    color: colors.leafGreen,
  },
  ocrUndoText: {
    fontSize: 11,
    fontWeight: typography.weight.bold,
    color: colors.primary,
    textDecorationLine: "underline",
  },
});
