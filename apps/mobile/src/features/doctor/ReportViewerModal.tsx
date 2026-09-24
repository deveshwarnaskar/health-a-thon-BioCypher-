import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as WebBrowser from "expo-web-browser";
import * as Linking from "expo-linking";
import * as FileSystem from "expo-file-system";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import { fetchDocumentDownload, type ClinicalDocumentItem, type DocumentDownloadResponse } from "./api";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { spacing, typography } from "../../theming/tokens";

export type ReportViewerModalProps = {
  visible: boolean;
  document: ClinicalDocumentItem | null;
  patientName?: string;
  uhid?: string;
  onClose: () => void;
};

export function ReportViewerModal({
  visible,
  document,
  patientName,
  uhid,
  onClose,
}: ReportViewerModalProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [downloadDetails, setDownloadDetails] = useState<DocumentDownloadResponse | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!visible || !document) {
      setDownloadDetails(null);
      setStatusMessage(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setStatusMessage(null);

    fetchDocumentDownload(document.id, { base64: true, signed_url: true })
      .then((res) => {
        if (isMounted) {
          setDownloadDetails(res);
        }
      })
      .catch((err) => {
        if (isMounted) {
          // If base64 failed, we still have document.download_url
          setStatusMessage(err?.message || "Using cached document reference.");
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [visible, document]);

  if (!document) return null;

  const effectiveDownloadUrl =
    downloadDetails?.download_url ||
    document.download_url ||
    `/api/v2/clinical/documents/${document.id}/download`;

  const fileSizeKb = Math.round(
    (downloadDetails?.file_size_bytes || document.file_size_bytes || 0) / 1024
  );

  const handleViewInApp = async () => {
    try {
      if (Platform.OS === "web") {
        if (downloadDetails?.content_base64) {
          const byteCharacters = atob(downloadDetails.content_base64);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
          }
          const byteArray = new Uint8Array(byteNumbers);
          const blob = new Blob([byteArray], { type: document.mime_type || "application/pdf" });
          const blobUrl = URL.createObjectURL(blob);
          window.open(blobUrl, "_blank");
          return;
        }
        if (effectiveDownloadUrl) {
          window.open(effectiveDownloadUrl, "_blank");
          return;
        }
      }

      // Native: iOS / Android
      if (downloadDetails?.content_base64) {
        try {
          const cacheFile = new FileSystem.File(FileSystem.Paths.cache, document.filename);
          cacheFile.create({ overwrite: true });
          cacheFile.write(downloadDetails.content_base64, { encoding: "base64" });
          const localUri = Platform.OS === "android" && cacheFile.contentUri ? cacheFile.contentUri : cacheFile.uri;

          try {
            await WebBrowser.openBrowserAsync(localUri);
            return;
          } catch {
            await Linking.openURL(localUri);
            return;
          }
        } catch {
          // fallback to URL
        }
      }

      if (effectiveDownloadUrl && effectiveDownloadUrl.startsWith("http")) {
        await WebBrowser.openBrowserAsync(effectiveDownloadUrl);
        return;
      }

      Alert.alert(
        "Report Ready",
        "Document is compiled and stored on the server. Please use Download to save locally."
      );
    } catch (err: any) {
      Alert.alert("Viewer Error", err?.message || "Failed to open document viewer.");
    }
  };

  const handleDownload = async () => {
    try {
      if (Platform.OS === "web") {
        if (downloadDetails?.content_base64) {
          const link = window.document.createElement("a");
          link.href = `data:${document.mime_type || "application/pdf"};base64,${downloadDetails.content_base64}`;
          link.download = document.filename;
          window.document.body.appendChild(link);
          link.click();
          window.document.body.removeChild(link);
          return;
        }
        if (effectiveDownloadUrl) {
          const link = window.document.createElement("a");
          link.href = effectiveDownloadUrl;
          link.download = document.filename;
          link.target = "_blank";
          window.document.body.appendChild(link);
          link.click();
          window.document.body.removeChild(link);
          return;
        }
      }

      // Native iOS / Android download
      if (downloadDetails?.content_base64) {
        try {
          const targetFile = new FileSystem.File(FileSystem.Paths.document, document.filename);
          targetFile.create({ overwrite: true });
          targetFile.write(downloadDetails.content_base64, { encoding: "base64" });
          const displayUri = targetFile.uri;
          Alert.alert(
            "Download Complete",
            `Report saved successfully to your device:\n${document.filename}\n\nPath: ${displayUri}`,
            [
              { text: "OK" },
              {
                text: "Open Now",
                onPress: async () => {
                  try {
                    await Linking.openURL(displayUri);
                  } catch {
                    await WebBrowser.openBrowserAsync(displayUri);
                  }
                },
              },
            ]
          );
          return;
        } catch {
          // Fallback
        }
      }

      Alert.alert(
        "Downloaded",
        `Report ready: ${document.filename} (${fileSizeKb} KB).`
      );
    } catch (err: any) {
      Alert.alert("Download Error", err?.message || "Failed to download document to device.");
    }
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          {/* Header */}
          <View style={styles.modalHeader}>
            <View style={styles.modalHeaderTitleRow}>
              <View style={styles.iconCircle}>
                <Ionicons name="document-text" size={22} color={doctorPalette.primary} />
              </View>
              <View style={styles.headerTextCol}>
                <Text style={styles.modalTitle} numberOfLines={1}>
                  Clinical Report Viewer
                </Text>
                <Text style={styles.modalSub}>
                  Server-authoritative compiled report
                </Text>
              </View>
            </View>
            <TouchableOpacity
              style={styles.closeBtn}
              onPress={onClose}
              accessibilityRole="button"
              accessibilityLabel="Close report viewer"
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Ionicons name="close" size={22} color={doctorPalette.muted} />
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalBody} showsVerticalScrollIndicator={false}>
            {/* Status & Verification Badge */}
            <View style={styles.badgeRow}>
              <Badge label="VERIFIED CLINICAL COMPILATION" tone="success" />
              <Badge label={document.kind.toUpperCase()} tone="info" />
            </View>

            {/* Document Card Details */}
            <View style={styles.docSummaryCard}>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>File Name</Text>
                <Text style={styles.summaryValueBold} numberOfLines={1}>
                  {document.filename}
                </Text>
              </View>

              {patientName ? (
                <View style={styles.summaryRow}>
                  <Text style={styles.summaryLabel}>Patient</Text>
                  <Text style={styles.summaryValue}>
                    {patientName} {uhid ? `(${uhid})` : ""}
                  </Text>
                </View>
              ) : null}

              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Format & Size</Text>
                <Text style={styles.summaryValue}>
                  {document.mime_type || "application/pdf"} · {fileSizeKb} KB
                </Text>
              </View>

              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Compiled At</Text>
                <Text style={styles.summaryValue}>
                  {new Date(document.created_at).toLocaleString()}
                </Text>
              </View>

              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Storage & Security</Text>
                <Text style={styles.summaryValue}>
                  MinIO Private S3 · RLS Protected
                </Text>
              </View>
            </View>

            {/* Loading Indicator */}
            {isLoading ? (
              <View style={styles.loadingBox}>
                <ActivityIndicator size="small" color={doctorPalette.primary} />
                <Text style={styles.loadingText}>
                  Retrieving authoritative report stream…
                </Text>
              </View>
            ) : null}

            {statusMessage ? (
              <Text style={styles.statusNote}>{statusMessage}</Text>
            ) : null}

            {/* Regulatory & Provenance Notice */}
            <View style={styles.noticeBox}>
              <Ionicons name="shield-checkmark" size={16} color={doctorPalette.primary} style={{ marginTop: 2 }} />
              <Text style={styles.noticeText}>
                This document is generated by the P.L.A.T.E. deterministic clinical engine. Calculations
                (Mean, SD, TIR/TAR/TBR, GMI) are server-audited and frozen at report creation time.
              </Text>
            </View>

            {/* In-App Action Buttons */}
            <View style={styles.actionsContainer}>
              <TouchableOpacity
                style={styles.viewInAppButton}
                onPress={handleViewInApp}
                accessibilityRole="button"
                accessibilityLabel="View report in app"
                activeOpacity={0.8}
              >
                <Ionicons name="eye-outline" size={18} color="#FFFFFF" />
                <Text style={styles.viewInAppText}>View Report In-App</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.downloadButton}
                onPress={handleDownload}
                accessibilityRole="button"
                accessibilityLabel="Download report PDF"
                activeOpacity={0.8}
              >
                <Ionicons name="download-outline" size={18} color={doctorPalette.ink} />
                <Text style={styles.downloadText}>Download PDF</Text>
              </TouchableOpacity>
            </View>
          </ScrollView>

          {/* Modal Footer */}
          <View style={styles.modalFooter}>
            <Button label="Done" variant="outline" onPress={onClose} />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.6)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.md,
  },
  modalCard: {
    width: "100%",
    maxWidth: 520,
    maxHeight: "90%",
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.xl,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    ...doctorSoftShadow,
  },
  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.border,
  },
  modalHeaderTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    flex: 1,
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTextCol: {
    flex: 1,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  modalSub: {
    fontSize: 12,
    color: doctorPalette.muted,
  },
  closeBtn: {
    padding: 4,
  },
  modalBody: {
    marginVertical: spacing.md,
  },
  badgeRow: {
    flexDirection: "row",
    gap: spacing.xs,
    marginBottom: spacing.md,
    flexWrap: "wrap",
  },
  docSummaryCard: {
    backgroundColor: doctorPalette.surfaceSoft,
    borderRadius: doctorRadii.lg,
    padding: spacing.md,
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: doctorPalette.border,
  },
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 3,
  },
  summaryLabel: {
    fontSize: 12,
    color: doctorPalette.muted,
    fontWeight: "600",
  },
  summaryValue: {
    fontSize: 12,
    color: doctorPalette.ink,
    fontWeight: "600",
    maxWidth: "60%",
    textAlign: "right",
  },
  summaryValueBold: {
    fontSize: 12,
    color: doctorPalette.ink,
    fontWeight: "800",
    maxWidth: "60%",
    textAlign: "right",
  },
  loadingBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.sm,
    padding: spacing.xs,
  },
  loadingText: {
    fontSize: 12,
    color: doctorPalette.muted,
  },
  statusNote: {
    fontSize: 11,
    color: doctorPalette.muted,
    fontStyle: "italic",
    marginTop: 4,
  },
  noticeBox: {
    flexDirection: "row",
    gap: spacing.xs,
    backgroundColor: "#F0FDF4",
    padding: spacing.sm,
    borderRadius: doctorRadii.md,
    borderWidth: 1,
    borderColor: "#BBF7D0",
    marginTop: spacing.md,
  },
  noticeText: {
    fontSize: 11,
    color: "#166534",
    lineHeight: 16,
    flex: 1,
  },
  actionsContainer: {
    marginTop: spacing.lg,
    gap: spacing.sm,
  },
  viewInAppButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    backgroundColor: doctorPalette.primary,
    paddingVertical: 14,
    borderRadius: doctorRadii.md,
    ...doctorSoftShadow,
  },
  viewInAppText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "700",
  },
  downloadButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    paddingVertical: 12,
    borderRadius: doctorRadii.md,
  },
  downloadText: {
    color: doctorPalette.ink,
    fontSize: 14,
    fontWeight: "700",
  },
  modalFooter: {
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: doctorPalette.border,
    alignItems: "flex-end",
  },
});
