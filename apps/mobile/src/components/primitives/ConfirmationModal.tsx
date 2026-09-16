import React from "react";
import { Modal, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { Button } from "./Button";

export type ConfirmationModalProps = {
  visible: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  confirmVariant?: "primary" | "danger";
};

export function ConfirmationModal({
  visible,
  title,
  message,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onCancel,
  confirmVariant = "primary",
}: ConfirmationModalProps) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={styles.overlay}>
        <View
          style={styles.card}
          accessible
          accessibilityRole="alert"
          accessibilityLabel={`${title}. ${message}`}
        >
          <Text style={styles.title} allowFontScaling>
            {title}
          </Text>
          <Text style={styles.message} allowFontScaling>
            {message}
          </Text>
          <View style={styles.actions}>
            <Button label={cancelLabel} onPress={onCancel} variant="outline" />
            <Button label={confirmLabel} onPress={onConfirm} variant={confirmVariant} />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: colors.overlay,
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.lg,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.lg,
    gap: spacing.md,
    alignItems: "stretch",
    maxWidth: 420,
    width: "100%",
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  message: {
    fontSize: typography.fontSize.body,
    color: colors.textSecondary,
  },
  actions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: spacing.sm,
  },
});