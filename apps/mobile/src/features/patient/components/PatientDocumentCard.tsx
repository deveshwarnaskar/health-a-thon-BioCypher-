import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
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

  return (
    <View style={styles.card} accessibilityRole="none">
      <View style={styles.topRow}>
        <View style={styles.iconContainer}>
          <Text style={styles.fileIcon} allowFontScaling>
            📄
          </Text>
        </View>
        <View style={styles.infoColumn}>
          <Text style={styles.filename} allowFontScaling numberOfLines={1}>
            {document.filename}
          </Text>
          <Text style={styles.metaText} allowFontScaling>
            {formattedDate} · {sizeKb}
          </Text>
        </View>
      </View>

      <TouchableOpacity
        style={styles.viewButton}
        onPress={() => onView?.(document)}
        activeOpacity={0.8}
        accessibilityRole="button"
        accessibilityLabel={`View document: ${document.filename}`}
      >
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
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.07,
    shadowRadius: 16,
    elevation: 2,
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  iconContainer: {
    width: 36,
    height: 36,
    borderRadius: radii.pill,
    backgroundColor: colors.tileAqua,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.sm,
  },
  fileIcon: {
    fontSize: 18,
  },
  infoColumn: {
    flex: 1,
  },
  filename: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  metaText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  viewButton: {
    backgroundColor: colors.backgroundRaised,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    borderRadius: radii.pill,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
  },
  viewButtonText: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.semibold,
    color: colors.primary,
  },
});
