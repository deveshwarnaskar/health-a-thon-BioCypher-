import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import type { PatientDocument } from "../types";

export type PatientDocumentCardProps = {
  document: PatientDocument;
  onView?: (doc: PatientDocument) => void;
};

export function PatientDocumentCard({ document, onView }: PatientDocumentCardProps) {
  const formattedDate = document.created_at
    ? new Date(document.created_at).toLocaleDateString([], {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : "";

  const sizeKb = document.file_size_bytes
    ? `${Math.round(document.file_size_bytes / 1024)} KB`
    : "PDF Document";

  const isVerified = (document as any).status === "VERIFIED" || (document as any).verification_status === "VERIFIED";
  const kindLabel =
    document.kind === "lab_report"
      ? "Lab Report"
      : document.kind === "prescription"
        ? "Prescription"
        : "Clinical Document";

  return (
    <View style={styles.card} accessibilityRole="none">
      <View style={styles.topRow}>
        <View style={styles.iconContainer}>
          <Ionicons name="document-text" size={20} color="#0D9488" />
        </View>
        <View style={styles.infoColumn}>
          <View style={styles.titleBadgeRow}>
            <Text style={styles.filename} allowFontScaling numberOfLines={1}>
              {document.filename}
            </Text>
            <View style={[styles.statusBadge, isVerified ? styles.statusBadgeVerified : styles.statusBadgePending]}>
              <Ionicons
                name={isVerified ? "checkmark-circle" : "time-outline"}
                size={12}
                color={isVerified ? "#059669" : "#64748B"}
                style={{ marginRight: 3 }}
              />
              <Text style={[styles.statusBadgeText, isVerified ? styles.statusTextVerified : styles.statusTextPending]} allowFontScaling>
                {isVerified ? "Verified" : "Pending"}
              </Text>
            </View>
          </View>
          <Text style={styles.metaText} allowFontScaling>
            {kindLabel} · {formattedDate} · {sizeKb}
          </Text>
        </View>
      </View>

      <TouchableOpacity
        style={styles.viewButton}
        onPress={() => onView?.(document)}
        activeOpacity={0.7}
        accessibilityRole="button"
        accessibilityLabel={`View document: ${document.filename}`}
      >
        <Ionicons name="open-outline" size={15} color="#0D9488" style={{ marginRight: 6 }} />
        <Text style={styles.viewButtonText} allowFontScaling>
          View Document
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    marginBottom: spacing.sm + 2,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 1,
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  iconContainer: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.sm + 2,
  },
  infoColumn: {
    flex: 1,
  },
  titleBadgeRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.xs,
  },
  filename: {
    flex: 1,
    fontSize: 14,
    fontWeight: "700",
    color: "#0F172A",
  },
  statusBadge: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radii.pill,
    borderWidth: 1,
  },
  statusBadgeVerified: {
    backgroundColor: "#ECFDF5",
    borderColor: "#A7F3D0",
  },
  statusBadgePending: {
    backgroundColor: "#F1F5F9",
    borderColor: "#E2E8F0",
  },
  statusBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
  statusTextVerified: {
    color: "#059669",
  },
  statusTextPending: {
    color: "#64748B",
  },
  metaText: {
    fontSize: 11,
    color: "#64748B",
    marginTop: 2,
  },
  viewButton: {
    flexDirection: "row",
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: radii.pill,
    minHeight: 42,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
  },
  viewButtonText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0D9488",
  },
});
