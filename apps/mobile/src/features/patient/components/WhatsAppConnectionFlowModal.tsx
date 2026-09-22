import React, { useState } from "react";
import {
  ActivityIndicator,
  Keyboard,
  KeyboardAvoidingView,
  Linking,
  Modal,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  TouchableWithoutFeedback,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { useTranslation } from "../../../i18n/i18n";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  useRequestWhatsAppVerification,
  useVerifyWhatsAppCode,
} from "../useWhatsAppIdentity";

export type WhatsAppConnectionFlowModalProps = {
  visible: boolean;
  onClose: () => void;
  onSuccess?: () => void;
};

type Step = "phone" | "code" | "success";

export function WhatsAppConnectionFlowModal({
  visible,
  onClose,
  onSuccess,
}: WhatsAppConnectionFlowModalProps) {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();

  const [step, setStep] = useState<Step>("phone");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [maskedNumber, setMaskedNumber] = useState<string>("");

  const requestMutation = useRequestWhatsAppVerification();
  const verifyMutation = useVerifyWhatsAppCode();

  const resetState = () => {
    setStep("phone");
    setPhoneNumber("");
    setVerificationCode("");
    setErrorMessage(null);
    setDevCode(null);
    setMaskedNumber("");
  };

  const handleClose = () => {
    Keyboard.dismiss();
    resetState();
    onClose();
  };

  const handleSendCode = async () => {
    Keyboard.dismiss();
    setErrorMessage(null);
    const cleanDigits = phoneNumber.replace(/[^0-9]/g, "");

    if (cleanDigits.length < 10) {
      setErrorMessage("Please enter a valid 10-digit mobile number.");
      return;
    }

    const fullNumber =
      cleanDigits.startsWith("91") && cleanDigits.length > 10
        ? `+${cleanDigits}`
        : `+91${cleanDigits.slice(-10)}`;

    try {
      const res = await requestMutation.mutateAsync({ phoneNumber: fullNumber });
      if (res.dev_code) {
        setDevCode(res.dev_code);
      }
      setStep("code");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to request code";
      setErrorMessage(msg);
    }
  };

  const handleVerifyCode = async () => {
    Keyboard.dismiss();
    setErrorMessage(null);
    const code = verificationCode.trim();
    if (code.length < 4) {
      setErrorMessage("Please enter the verification code.");
      return;
    }

    const cleanDigits = phoneNumber.replace(/[^0-9]/g, "");
    const fullNumber =
      cleanDigits.startsWith("91") && cleanDigits.length > 10
        ? `+${cleanDigits}`
        : `+91${cleanDigits.slice(-10)}`;

    try {
      const res = await verifyMutation.mutateAsync({
        phoneNumber: fullNumber,
        code,
      });
      setMaskedNumber(res.phone_number_masked || `+91 ••••• ${cleanDigits.slice(-4)}`);
      setStep("success");
      onSuccess?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Invalid verification code";
      setErrorMessage(msg);
    }
  };

  const handleOpenWhatsApp = async () => {
    const defaultText = encodeURIComponent("Hi THALI, my WhatsApp is connected! How can I log my blood sugar?");
    const businessPhone = process.env.EXPO_PUBLIC_WHATSAPP_BUSINESS_NUMBER || "919903546271";
    const appUrl = `whatsapp://send?phone=${businessPhone}&text=${defaultText}`;
    const webUrl = `https://wa.me/${businessPhone}?text=${defaultText}`;
    try {
      await Linking.openURL(appUrl);
    } catch {
      try {
        await Linking.openURL(webUrl);
      } catch {
        // Best-effort
      }
    }
  };

  const handleDone = () => {
    handleClose();
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={handleClose}
    >
      <View style={styles.overlay}>
        <TouchableWithoutFeedback onPress={Keyboard.dismiss}>
          <View style={StyleSheet.absoluteFill} />
        </TouchableWithoutFeedback>

        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={[
            styles.keyboardAvoid,
            {
              paddingTop: Math.max(insets.top + spacing.sm, 48),
              paddingBottom: Math.max(insets.bottom + spacing.sm, 24),
            },
          ]}
        >
          <View style={styles.dialogCard} accessibilityRole="alert">
            {/* Stepper Progress Bar */}
            <View style={styles.stepperContainer}>
              <View style={styles.stepperRow}>
                <View
                  style={[
                    styles.stepPill,
                    step === "phone"
                      ? styles.stepPillActive
                      : styles.stepPillCompleted,
                  ]}
                >
                  <Text
                    style={[
                      styles.stepPillText,
                      step === "phone"
                        ? styles.stepPillTextActive
                        : styles.stepPillTextCompleted,
                    ]}
                  >
                    {step !== "phone" ? "✓ " : "1. "}Phone
                  </Text>
                </View>

                <View
                  style={[
                    styles.stepDivider,
                    step !== "phone" && styles.stepDividerActive,
                  ]}
                />

                <View
                  style={[
                    styles.stepPill,
                    step === "code"
                      ? styles.stepPillActive
                      : step === "success"
                      ? styles.stepPillCompleted
                      : styles.stepPillInactive,
                  ]}
                >
                  <Text
                    style={[
                      styles.stepPillText,
                      step === "code"
                        ? styles.stepPillTextActive
                        : step === "success"
                        ? styles.stepPillTextCompleted
                        : styles.stepPillTextInactive,
                    ]}
                  >
                    {step === "success" ? "✓ " : "2. "}Verify
                  </Text>
                </View>

                <View
                  style={[
                    styles.stepDivider,
                    step === "success" && styles.stepDividerActive,
                  ]}
                />

                <View
                  style={[
                    styles.stepPill,
                    step === "success"
                      ? styles.stepPillActive
                      : styles.stepPillInactive,
                  ]}
                >
                  <Text
                    style={[
                      styles.stepPillText,
                      step === "success"
                        ? styles.stepPillTextActive
                        : styles.stepPillTextInactive,
                    ]}
                  >
                    3. Linked
                  </Text>
                </View>
              </View>

              {step !== "success" ? (
                <TouchableOpacity
                  onPress={handleClose}
                  accessibilityRole="button"
                  accessibilityLabel="Close"
                  style={styles.closeButton}
                  activeOpacity={0.7}
                >
                  <Ionicons name="close" size={20} color={colors.textPrimary} />
                </TouchableOpacity>
              ) : null}
            </View>

            {/* Scrollable Form Content */}
            <ScrollView
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={false}
              contentContainerStyle={styles.scrollContent}
              bounces={false}
            >
              {/* STEP 1: Phone Input */}
              {step === "phone" ? (
                <View style={styles.stepContainer}>
                  <View style={styles.titleSection}>
                    <Text style={styles.stepTitle} allowFontScaling>
                      {t("whatsapp.flowStep1Title")}
                    </Text>
                    <Text style={styles.stepSubtitle} allowFontScaling>
                      {t("whatsapp.flowStep1Subtitle")}
                    </Text>
                  </View>

                  <View style={styles.inputCard}>
                    <View style={styles.inputLabelRow}>
                      <Text style={styles.inputLabel} allowFontScaling>
                        {t("whatsapp.phoneLabel")}
                      </Text>
                      <TouchableOpacity
                        onPress={Keyboard.dismiss}
                        style={styles.hideKeypadButton}
                        activeOpacity={0.7}
                      >
                        <Text style={styles.hideKeypadText}>Hide keypad</Text>
                      </TouchableOpacity>
                    </View>

                    <View style={styles.phoneInputRow}>
                      <View style={styles.countryCodeBox}>
                        <Text style={styles.flagEmoji}>🇮🇳</Text>
                        <Text style={styles.countryCodeText}>+91</Text>
                      </View>
                      <TextInput
                        style={styles.phoneTextInput}
                        value={phoneNumber}
                        onChangeText={(val) => {
                          setPhoneNumber(val);
                          if (errorMessage) setErrorMessage(null);
                        }}
                        keyboardType="phone-pad"
                        placeholder="98765 43210"
                        placeholderTextColor={colors.textSecondary}
                        maxLength={13}
                        accessibilityLabel={t("whatsapp.phoneLabel")}
                        returnKeyType="done"
                        onSubmitEditing={handleSendCode}
                      />
                    </View>
                  </View>

                  {errorMessage ? (
                    <View style={styles.errorBanner}>
                      <Ionicons name="alert-circle" size={16} color="#DC2626" style={{ marginRight: 6 }} />
                      <Text style={styles.errorText} allowFontScaling>
                        {errorMessage}
                      </Text>
                    </View>
                  ) : null}

                  <View style={styles.securityNote}>
                    <Ionicons name="lock-closed" size={14} color="#64748B" style={{ marginRight: 6 }} />
                    <Text style={styles.securityNoteText}>
                      We only send clinical updates and reminders to this WhatsApp number.
                    </Text>
                  </View>

                  <TouchableOpacity
                    style={[
                      styles.primaryButton,
                      requestMutation.isPending && styles.buttonDisabled,
                    ]}
                    onPress={handleSendCode}
                    disabled={requestMutation.isPending}
                    accessibilityRole="button"
                    accessibilityLabel={t("whatsapp.sendOtpButton")}
                    activeOpacity={0.85}
                  >
                    {requestMutation.isPending ? (
                      <ActivityIndicator color="#FFFFFF" />
                    ) : (
                      <Text style={styles.primaryButtonText} allowFontScaling>
                        {t("whatsapp.sendOtpButton")} →
                      </Text>
                    )}
                  </TouchableOpacity>
                </View>
              ) : null}

              {/* STEP 2: Code Verification */}
              {step === "code" ? (
                <View style={styles.stepContainer}>
                  <View style={styles.titleSection}>
                    <Text style={styles.stepTitle} allowFontScaling>
                      {t("whatsapp.flowStep2Title")}
                    </Text>
                    <Text style={styles.stepSubtitle} allowFontScaling>
                      {t("whatsapp.flowStep2Subtitle")}
                    </Text>
                  </View>

                  {devCode ? (
                    <View style={styles.devCodeCard}>
                      <View style={styles.devCodeHeader}>
                        <Text style={styles.devCodeTitle}>💡 Test Environment Active</Text>
                        <TouchableOpacity
                          style={styles.devCodeFillBtn}
                          onPress={() => {
                            setVerificationCode(devCode);
                            if (errorMessage) setErrorMessage(null);
                            Keyboard.dismiss();
                          }}
                          activeOpacity={0.7}
                        >
                          <Text style={styles.devCodeFillText}>
                            Auto-fill {devCode}
                          </Text>
                        </TouchableOpacity>
                      </View>
                      <Text style={styles.devCodeSub}>
                        Test verification code:{" "}
                        <Text style={styles.devCodeBold}>{devCode}</Text>
                      </Text>
                    </View>
                  ) : null}

                  <View style={styles.inputCard}>
                    <View style={styles.inputLabelRow}>
                      <Text style={styles.inputLabel} allowFontScaling>
                        {t("whatsapp.codeLabel")}
                      </Text>
                      <TouchableOpacity
                        onPress={() => {
                          setStep("phone");
                          setErrorMessage(null);
                        }}
                        activeOpacity={0.7}
                      >
                        <Text style={styles.changePhoneText}>← Edit number</Text>
                      </TouchableOpacity>
                    </View>

                    <TextInput
                      style={styles.codeInput}
                      value={verificationCode}
                      onChangeText={(val) => {
                        setVerificationCode(val);
                        if (errorMessage) setErrorMessage(null);
                        if (val.trim().length === 6) {
                          Keyboard.dismiss();
                        }
                      }}
                      keyboardType="number-pad"
                      placeholder="••••••"
                      placeholderTextColor={colors.disabled}
                      maxLength={6}
                      accessibilityLabel={t("whatsapp.codeLabel")}
                      returnKeyType="done"
                      onSubmitEditing={handleVerifyCode}
                    />
                  </View>

                  {errorMessage ? (
                    <View style={styles.errorBanner}>
                      <Ionicons name="alert-circle" size={16} color="#DC2626" style={{ marginRight: 6 }} />
                      <Text style={styles.errorText} allowFontScaling>
                        {errorMessage}
                      </Text>
                    </View>
                  ) : null}

                  <TouchableOpacity
                    style={[
                      styles.primaryButton,
                      verifyMutation.isPending && styles.buttonDisabled,
                    ]}
                    onPress={handleVerifyCode}
                    disabled={verifyMutation.isPending}
                    accessibilityRole="button"
                    accessibilityLabel={t("whatsapp.verifyButton")}
                    activeOpacity={0.85}
                  >
                    {verifyMutation.isPending ? (
                      <ActivityIndicator color="#FFFFFF" />
                    ) : (
                      <Text style={styles.primaryButtonText} allowFontScaling>
                        {t("whatsapp.verifyButton")} ✓
                      </Text>
                    )}
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.resendButton}
                    onPress={handleSendCode}
                    disabled={requestMutation.isPending}
                    accessibilityRole="button"
                    accessibilityLabel={t("whatsapp.resendButton")}
                    activeOpacity={0.7}
                  >
                    <Text style={styles.resendButtonText} allowFontScaling>
                      {requestMutation.isPending
                        ? "Sending code…"
                        : t("whatsapp.resendButton")}
                    </Text>
                  </TouchableOpacity>
                </View>
              ) : null}

              {/* STEP 3: Success Confirmation */}
              {step === "success" ? (
                <View style={styles.successContainer}>
                  <View style={styles.successBadgeOuter}>
                    <View style={styles.successBadge}>
                      <Ionicons name="checkmark" size={32} color="#FFFFFF" />
                    </View>
                  </View>

                  <Text style={styles.successTitle} allowFontScaling>
                    {t("whatsapp.flowStep3Title")}
                  </Text>
                  <Text style={styles.successSubtitle} allowFontScaling>
                    {t("whatsapp.flowStep3Subtitle")}
                  </Text>

                  {maskedNumber ? (
                    <View style={styles.numberPill}>
                      <Ionicons name="phone-portrait-outline" size={14} color="#0D9488" style={{ marginRight: 6 }} />
                      <Text style={styles.numberPillText}>{maskedNumber}</Text>
                    </View>
                  ) : null}

                  <View style={styles.featureCardsContainer}>
                    <View style={styles.featureRow}>
                      <View style={[styles.featureIconBadge, { backgroundColor: "rgba(239, 68, 68, 0.12)" }]}>
                        <Ionicons name="water-outline" size={18} color="#DC2626" />
                      </View>
                      <View style={styles.featureContent}>
                        <Text style={styles.featureTitle}>Instant Glucose & Food Logs</Text>
                        <Text style={styles.featureDesc}>
                          Text readings or snap meal photos anytime.
                        </Text>
                      </View>
                    </View>

                    <View style={styles.featureRow}>
                      <View style={[styles.featureIconBadge, { backgroundColor: "rgba(37, 99, 235, 0.12)" }]}>
                        <Ionicons name="notifications-outline" size={18} color="#2563EB" />
                      </View>
                      <View style={styles.featureContent}>
                        <Text style={styles.featureTitle}>Medication Reminders</Text>
                        <Text style={styles.featureDesc}>
                          Receive scheduled nudges right in your chat.
                        </Text>
                      </View>
                    </View>

                    <View style={styles.featureRow}>
                      <View style={[styles.featureIconBadge, { backgroundColor: "rgba(217, 119, 6, 0.12)" }]}>
                        <Ionicons name="mic-outline" size={18} color="#D97706" />
                      </View>
                      <View style={styles.featureContent}>
                        <Text style={styles.featureTitle}>Voice Message Support</Text>
                        <Text style={styles.featureDesc}>
                          Speak in Hindi, Bengali, Tamil, Telugu, Marathi, or Hinglish.
                        </Text>
                      </View>
                    </View>
                  </View>

                  <TouchableOpacity
                    style={[styles.primaryButton, { backgroundColor: "#25D366", flexDirection: "row" }]}
                    onPress={handleOpenWhatsApp}
                    accessibilityRole="button"
                    accessibilityLabel="Open WhatsApp"
                    activeOpacity={0.85}
                  >
                    <Ionicons name="logo-whatsapp" size={20} color="#FFFFFF" style={{ marginRight: 8 }} />
                    <Text style={styles.primaryButtonText} allowFontScaling>
                      Open WhatsApp
                    </Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.doneSecondaryButton}
                    onPress={handleDone}
                    accessibilityRole="button"
                    accessibilityLabel={t("whatsapp.doneButton")}
                    activeOpacity={0.7}
                  >
                    <Text style={styles.doneSecondaryButtonText} allowFontScaling>
                      {t("whatsapp.doneButton")} — Back to Home
                    </Text>
                  </TouchableOpacity>
                </View>
              ) : null}
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(10, 22, 18, 0.72)",
  },
  keyboardAvoid: {
    flex: 1,
    width: "100%",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: spacing.md,
  },
  dialogCard: {
    width: "100%",
    maxWidth: 400,
    backgroundColor: colors.surface,
    borderRadius: 20,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.2,
    shadowRadius: 24,
    elevation: 10,
  },
  stepperContainer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.xs + 2,
  },
  stepperRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  stepPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    backgroundColor: "#F1F5F9",
  },
  stepPillActive: {
    backgroundColor: "#25D366",
  },
  stepPillCompleted: {
    backgroundColor: "#E6F4EA",
  },
  stepPillInactive: {
    backgroundColor: "#F1F5F9",
  },
  stepPillText: {
    fontSize: 11,
    fontWeight: typography.weight.bold,
  },
  stepPillTextActive: {
    color: "#FFFFFF",
  },
  stepPillTextCompleted: {
    color: "#137333",
  },
  stepPillTextInactive: {
    color: colors.textSecondary,
  },
  stepDivider: {
    width: 12,
    height: 2,
    backgroundColor: "#E2E8F0",
  },
  stepDividerActive: {
    backgroundColor: "#25D366",
  },
  closeButton: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#F1F5F9",
    alignItems: "center",
    justifyContent: "center",
  },
  closeButtonText: {
    fontSize: 13,
    color: colors.textSecondary,
    fontWeight: typography.weight.bold,
  },
  scrollContent: {
    paddingVertical: 2,
  },
  stepContainer: {
    gap: spacing.xs + 4,
  },
  titleSection: {
    marginBottom: 2,
  },
  stepTitle: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    marginBottom: 2,
  },
  stepSubtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  inputCard: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: radii.md,
    padding: spacing.sm,
    gap: 6,
  },
  inputLabelRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  inputLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    letterSpacing: 0.5,
  },
  hideKeypadButton: {
    paddingVertical: 2,
    paddingHorizontal: 6,
  },
  hideKeypadText: {
    fontSize: 12,
    color: colors.primary,
    fontWeight: typography.weight.semibold,
  },
  changePhoneText: {
    fontSize: 12,
    color: colors.primary,
    fontWeight: typography.weight.bold,
  },
  phoneInputRow: {
    flexDirection: "row",
    gap: spacing.xs + 2,
    alignItems: "center",
  },
  countryCodeBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: radii.md,
    paddingHorizontal: spacing.sm,
    height: 44,
  },
  flagEmoji: {
    fontSize: 16,
  },
  countryCodeText: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  phoneTextInput: {
    flex: 1,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: radii.md,
    paddingHorizontal: spacing.sm,
    fontSize: 16,
    color: colors.textPrimary,
    fontWeight: typography.weight.semibold,
    height: 44,
    letterSpacing: 0.5,
  },
  codeInput: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1.5,
    borderColor: "#CBD5E1",
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    fontSize: 22,
    color: colors.textPrimary,
    fontWeight: typography.weight.bold,
    textAlign: "center",
    letterSpacing: 10,
    height: 48,
  },
  devCodeCard: {
    backgroundColor: "#EFF6FF",
    borderWidth: 1,
    borderColor: "#BFDBFE",
    borderRadius: radii.md,
    padding: spacing.xs + 2,
    gap: 2,
  },
  devCodeHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  devCodeTitle: {
    fontSize: 12,
    fontWeight: typography.weight.bold,
    color: "#1E40AF",
  },
  devCodeFillBtn: {
    backgroundColor: "#2563EB",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.sm,
  },
  devCodeFillText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: typography.weight.bold,
  },
  devCodeSub: {
    fontSize: 11,
    color: "#1E40AF",
  },
  devCodeBold: {
    fontWeight: typography.weight.bold,
    letterSpacing: 2,
  },
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: "#FEF2F2",
    borderWidth: 1,
    borderColor: "#FECACA",
    borderRadius: radii.md,
    padding: spacing.xs + 2,
  },
  errorIcon: {
    fontSize: 13,
  },
  errorText: {
    flex: 1,
    fontSize: typography.fontSize.caption,
    color: colors.critical,
    fontWeight: typography.weight.semibold,
  },
  securityNote: {
    paddingHorizontal: 2,
  },
  securityNoteText: {
    fontSize: 11,
    color: colors.textSecondary,
    lineHeight: 15,
  },
  primaryButton: {
    backgroundColor: "#25D366",
    borderRadius: radii.md,
    minHeight: 46,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    shadowColor: "#25D366",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 3,
    marginTop: 2,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: typography.weight.bold,
  },
  resendButton: {
    alignItems: "center",
    paddingVertical: 2,
  },
  resendButtonText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    fontWeight: typography.weight.semibold,
  },
  successContainer: {
    alignItems: "center",
    paddingVertical: spacing.xs,
    gap: spacing.xs + 2,
  },
  successBadgeOuter: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#E7F9EE",
    alignItems: "center",
    justifyContent: "center",
  },
  successBadge: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: "#25D366",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#25D366",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  successCheck: {
    fontSize: 22,
    color: "#FFFFFF",
    fontWeight: typography.weight.bold,
  },
  successTitle: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    textAlign: "center",
  },
  successSubtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    textAlign: "center",
    lineHeight: 18,
    paddingHorizontal: spacing.xs,
  },
  numberPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "#F1F5F9",
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#CBD5E1",
  },
  numberPillLock: {
    fontSize: 13,
  },
  numberPillText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    letterSpacing: 1,
  },
  featureCardsContainer: {
    width: "100%",
    backgroundColor: "#F8FAFC",
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.xs + 2,
    gap: 6,
  },
  featureRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs + 2,
  },
  featureIconBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    justifyContent: "center",
  },
  featureIconText: {
    fontSize: 14,
  },
  featureContent: {
    flex: 1,
  },
  featureTitle: {
    fontSize: 12,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  featureDesc: {
    fontSize: 10,
    color: colors.textSecondary,
  },
  doneSecondaryButton: {
    minHeight: 38,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
  },
  doneSecondaryButtonText: {
    color: colors.textSecondary,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
  },
});
