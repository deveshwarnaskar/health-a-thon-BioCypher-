import React from "react";
import { Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";

export type SignOutConfirmModalProps = {
  visible: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  isSigningOut?: boolean;
};

export function SignOutConfirmModal({
  visible,
  onCancel,
  onConfirm,
  isSigningOut = false,
}: SignOutConfirmModalProps) {
  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onCancel}
    >
      <View style={styles.overlay}>
        <View style={styles.dialog} accessibilityRole="alert">
          <Text style={styles.title} allowFontScaling>
            Sign out of THALI?
          </Text>
          <Text style={styles.message} allowFontScaling>
            Your un-synced entries are safely stored on this device. You can sign back in at any time with your credentials.
          </Text>

          <View style={styles.buttonRow}>
            <TouchableOpacity
              style={styles.cancelButton}
              onPress={onCancel}
              disabled={isSigningOut}
              accessibilityRole="button"
              accessibilityLabel="Cancel sign out"
              activeOpacity={0.7}
            >
              <Text style={styles.cancelText} allowFontScaling>
                Cancel
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.confirmButton, isSigningOut && styles.buttonBusy]}
              onPress={onConfirm}
              disabled={isSigningOut}
              accessibilityRole="button"
              accessibilityLabel="Confirm sign out"
              activeOpacity={0.8}
            >
              <Text style={styles.confirmText} allowFontScaling>
                {isSigningOut ? "Signing out…" : "Sign out"}
              </Text>
            </TouchableOpacity>
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
    padding: spacing.md,
  },
  dialog: {
    width: "100%",
    maxWidth: 340,
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.lg,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 10,
    elevation: 6,
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  message: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    lineHeight: 20,
    marginBottom: spacing.lg,
  },
  buttonRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: spacing.sm,
  },
  cancelButton: {
    minHeight: touchTarget.min,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.md,
  },
  cancelText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    fontWeight: typography.weight.medium,
  },
  confirmButton: {
    minHeight: touchTarget.min,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.critical,
    borderRadius: radii.md,
  },
  confirmText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textOnPrimary,
    fontWeight: typography.weight.semibold,
  },
  buttonBusy: {
    opacity: 0.6,
  },
});
