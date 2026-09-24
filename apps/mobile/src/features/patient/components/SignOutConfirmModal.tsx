import React from "react";
import { Modal, StyleSheet, Text, TouchableOpacity, View, ActivityIndicator } from "react-native";
import { Ionicons } from "@expo/vector-icons";
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
          {/* Hero Icon */}
          <View style={styles.iconCircle}>
            <Ionicons name="log-out-outline" size={26} color="#DC2626" />
          </View>

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
              {isSigningOut ? (
                <ActivityIndicator color="#FFFFFF" size="small" />
              ) : (
                <>
                  <Ionicons name="log-out-outline" size={16} color="#FFFFFF" style={{ marginRight: 6 }} />
                  <Text style={styles.confirmText} allowFontScaling>
                    Sign out
                  </Text>
                </>
              )}
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
    backgroundColor: "rgba(15, 23, 42, 0.65)",
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.md,
  },
  dialog: {
    width: "100%",
    maxWidth: 340,
    backgroundColor: colors.surface,
    borderRadius: 24,
    padding: spacing.lg,
    alignItems: "center",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.15,
    shadowRadius: 24,
    elevation: 8,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  iconCircle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "#FEE2E2",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: "#FECACA",
  },
  title: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
    marginBottom: spacing.xs,
    textAlign: "center",
    letterSpacing: -0.3,
  },
  message: {
    fontSize: 13,
    color: "#64748B",
    lineHeight: 19,
    marginBottom: spacing.lg,
    textAlign: "center",
  },
  buttonRow: {
    flexDirection: "row",
    gap: spacing.sm,
    width: "100%",
  },
  cancelButton: {
    flex: 1,
    minHeight: 46,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.pill,
    backgroundColor: "#F1F5F9",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  cancelText: {
    fontSize: 14,
    color: "#475569",
    fontWeight: "600",
  },
  confirmButton: {
    flex: 1,
    minHeight: 46,
    paddingHorizontal: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#DC2626",
    borderRadius: radii.pill,
    shadowColor: "#DC2626",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 2,
  },
  confirmText: {
    fontSize: 14,
    color: "#FFFFFF",
    fontWeight: "700",
  },
  buttonBusy: {
    opacity: 0.7,
  },
});
