import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";

export type DeleteAccountModalProps = {
  visible: boolean;
  onCancel: () => void;
  onConfirmDelete: (phone: string) => Promise<void>;
  registeredPhone?: string | null;
};

/**
 * Normalizes phone numbers by stripping all non-digit characters.
 */
function normalizePhone(p: string | null | undefined): string {
  if (!p) return "";
  return p.replace(/\D/g, "");
}

/**
 * Checks if two phone numbers match, accounting for country codes or formatting.
 */
function checkPhonesMatch(entered: string, registered: string): boolean {
  const nEntered = normalizePhone(entered);
  const nRegistered = normalizePhone(registered);
  if (!nEntered || !nRegistered) return false;
  if (nEntered === nRegistered) return true;
  if (nEntered.length >= 10 && nRegistered.length >= 10) {
    return nEntered.slice(-10) === nRegistered.slice(-10);
  }
  return false;
}

export function DeleteAccountModal({
  visible,
  onCancel,
  onConfirmDelete,
  registeredPhone,
}: DeleteAccountModalProps) {
  const [phoneInput, setPhoneInput] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (visible) {
      setPhoneInput("");
      setIsDeleting(false);
      setErrorMessage(null);
    }
  }, [visible]);

  const handleDelete = async () => {
    setErrorMessage(null);
    const trimmedInput = phoneInput.trim();

    if (!trimmedInput) {
      setErrorMessage("Please enter your registered phone number.");
      return;
    }

    if (registeredPhone && registeredPhone.trim()) {
      const match = checkPhonesMatch(trimmedInput, registeredPhone);
      if (!match) {
        setErrorMessage(
          "Phone number does not match your registered phone number. Please try again."
        );
        return;
      }
    } else {
      const digits = normalizePhone(trimmedInput);
      if (digits.length < 7) {
        setErrorMessage("Please enter a valid phone number to confirm deletion.");
        return;
      }
    }

    setIsDeleting(true);
    try {
      await onConfirmDelete(trimmedInput);
    } catch (err: any) {
      setErrorMessage(
        err?.message ||
          (typeof err === "string" ? err : "Failed to delete account. Please try again.")
      );
      setIsDeleting(false);
    }
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={isDeleting ? undefined : onCancel}
    >
      <KeyboardAvoidingView
        style={styles.overlay}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <View style={styles.dialog} accessibilityRole="alert">
          {/* Warning Icon Header */}
          <View style={styles.iconCircle}>
            <Ionicons name="trash-outline" size={28} color="#DC2626" />
          </View>

          <Text style={styles.title} allowFontScaling>
            Delete Account?
          </Text>

          <View style={styles.warningBanner}>
            <Ionicons name="warning-outline" size={16} color="#DC2626" style={{ marginTop: 1 }} />
            <Text style={styles.warningBannerText} allowFontScaling>
              Permanent and irreversible action. All your glycemic logs, meals, medications, and clinical records will be permanently erased.
            </Text>
          </View>

          <Text style={styles.promptText} allowFontScaling>
            To confirm deletion, please enter the phone number you used during the signup process:
          </Text>

          {/* Phone Input Box */}
          <View style={styles.inputContainer}>
            <Ionicons
              name="call-outline"
              size={18}
              color="#64748B"
              style={styles.inputIcon}
            />
            <TextInput
              style={styles.textInput}
              placeholder="e.g. +91 98765 43210"
              placeholderTextColor="#94A3B8"
              value={phoneInput}
              onChangeText={(text) => {
                setPhoneInput(text);
                if (errorMessage) setErrorMessage(null);
              }}
              keyboardType="phone-pad"
              autoCapitalize="none"
              autoCorrect={false}
              editable={!isDeleting}
              accessibilityLabel="Confirm phone number input"
              accessibilityHint="Type your registered phone number to confirm account deletion"
            />
          </View>

          {/* Error Message */}
          {errorMessage ? (
            <View style={styles.errorBox}>
              <Ionicons name="alert-circle" size={15} color="#DC2626" style={{ marginRight: 6 }} />
              <Text style={styles.errorText} allowFontScaling>
                {errorMessage}
              </Text>
            </View>
          ) : null}

          {/* Action Buttons */}
          <View style={styles.buttonRow}>
            <TouchableOpacity
              style={styles.cancelButton}
              onPress={onCancel}
              disabled={isDeleting}
              accessibilityRole="button"
              accessibilityLabel="Cancel delete account"
              activeOpacity={0.7}
            >
              <Text style={styles.cancelText} allowFontScaling>
                Cancel
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.deleteButton,
                (!phoneInput.trim() || isDeleting) && styles.buttonDisabled,
              ]}
              onPress={handleDelete}
              disabled={isDeleting || !phoneInput.trim()}
              accessibilityRole="button"
              accessibilityLabel="Confirm delete account"
              activeOpacity={0.8}
            >
              {isDeleting ? (
                <View style={styles.buttonContent}>
                  <ActivityIndicator color="#FFFFFF" size="small" />
                  <Text style={[styles.deleteText, { marginLeft: 8 }]} allowFontScaling>
                    Deleting...
                  </Text>
                </View>
              ) : (
                <View style={styles.buttonContent}>
                  <Ionicons name="trash-outline" size={16} color="#FFFFFF" style={{ marginRight: 6 }} />
                  <Text style={styles.deleteText} allowFontScaling>
                    Delete Account
                  </Text>
                </View>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.7)",
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.md,
  },
  dialog: {
    width: "100%",
    maxWidth: 360,
    backgroundColor: colors.surface,
    borderRadius: 24,
    padding: spacing.lg,
    alignItems: "center",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 16 },
    shadowOpacity: 0.2,
    shadowRadius: 28,
    elevation: 10,
    borderWidth: 1,
    borderColor: "#FECACA",
  },
  iconCircle: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: "#FEE2E2",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm + 2,
    borderWidth: 1.5,
    borderColor: "#FCA5A5",
  },
  title: {
    fontSize: 20,
    fontWeight: "800",
    color: "#0F172A",
    marginBottom: spacing.xs,
    textAlign: "center",
    letterSpacing: -0.4,
  },
  warningBanner: {
    flexDirection: "row",
    backgroundColor: "#FEF2F2",
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "#FECACA",
    padding: spacing.sm,
    gap: 8,
    marginVertical: spacing.xs + 2,
    width: "100%",
  },
  warningBannerText: {
    flex: 1,
    fontSize: 12,
    color: "#991B1B",
    lineHeight: 17,
    fontWeight: "500",
  },
  promptText: {
    fontSize: 13,
    color: "#475569",
    lineHeight: 19,
    marginVertical: spacing.xs,
    width: "100%",
    fontWeight: "500",
  },
  inputContainer: {
    flexDirection: "row",
    alignItems: "center",
    width: "100%",
    borderWidth: 1.5,
    borderColor: "#CBD5E1",
    borderRadius: 14,
    backgroundColor: "#F8FAFC",
    paddingHorizontal: spacing.sm,
    height: 48,
    marginTop: spacing.xs,
  },
  inputIcon: {
    marginRight: 8,
  },
  textInput: {
    flex: 1,
    fontSize: 15,
    color: "#0F172A",
    fontWeight: "600",
  },
  errorBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FFF1F2",
    borderWidth: 1,
    borderColor: "#FECDD3",
    borderRadius: 10,
    paddingVertical: 8,
    paddingHorizontal: 10,
    marginTop: spacing.xs + 2,
    width: "100%",
  },
  errorText: {
    flex: 1,
    fontSize: 12,
    color: "#DC2626",
    fontWeight: "600",
    lineHeight: 16,
  },
  buttonRow: {
    flexDirection: "row",
    gap: spacing.sm,
    width: "100%",
    marginTop: spacing.md,
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
  deleteButton: {
    flex: 1.3,
    minHeight: 46,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#DC2626",
    borderRadius: radii.pill,
    shadowColor: "#DC2626",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 3,
  },
  deleteText: {
    fontSize: 14,
    color: "#FFFFFF",
    fontWeight: "700",
  },
  buttonContent: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  buttonDisabled: {
    opacity: 0.55,
    shadowOpacity: 0,
    elevation: 0,
  },
});
