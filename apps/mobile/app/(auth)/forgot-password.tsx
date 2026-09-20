import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { AlertBanner } from "../../src/components/primitives/AlertBanner";
import { useAuth } from "../../src/auth/AuthProvider";
import { colors, radii, spacing, typography } from "../../src/theming/tokens";
import {
  AuthButton,
  AuthFooter,
  AuthHeader,
  AuthInput,
  AuthScreen,
  PasswordInput,
  PasswordRequirements,
} from "../../src/features/auth";

type RecoveryStep = "request" | "check_email" | "reset" | "complete";

/**
 * THALI Password Recovery Screen
 * Implements a 4-step secure recovery state machine:
 * Request -> Check Email -> Set New Password -> Confirmation
 */
export default function ForgotPasswordScreen() {
  const router = useRouter();
  const { forgotPassword, resetPassword, isBootstrapping } = useAuth();

  const [step, setStep] = useState<RecoveryStep>("request");
  const [email, setEmail] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const busy = isBootstrapping || submitting;

  const handleRequestReset = async () => {
    setErrorMsg(null);
    setSuccessMsg(null);
    const cleanEmail = email.trim().toLowerCase();

    if (!cleanEmail || !cleanEmail.includes("@")) {
      setErrorMsg("Please enter a valid email address.");
      return;
    }

    if (!forgotPassword) {
      setErrorMsg("Password recovery is unavailable in this environment.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await forgotPassword(cleanEmail);
      setSuccessMsg(res.message);
      if (res.reset_token) {
        setResetToken(res.reset_token);
      }
      setStep("reset");
    } catch (err: any) {
      setErrorMsg(err?.message || "Unable to request password reset. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const handlePerformReset = async () => {
    setErrorMsg(null);
    if (!resetToken.trim()) {
      setErrorMsg("Please provide the reset token.");
      return;
    }
    if (newPassword.length < 8) {
      setErrorMsg("New password must be at least 8 characters long.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setErrorMsg("Passwords do not match.");
      return;
    }

    if (!resetPassword) {
      setErrorMsg("Password recovery is unavailable.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await resetPassword(resetToken.trim(), newPassword);
      setSuccessMsg(res.message);
      setStep("complete");
    } catch (err: any) {
      setErrorMsg(err?.message || "Password reset failed. Token may be expired or invalid.");
    } finally {
      setSubmitting(false);
    }
  };

  const stepBadge =
    step === "complete" ? "SUCCESS" : step === "reset" ? "STEP 2 OF 2" : "STEP 1 OF 2";

  return (
    <AuthScreen>
      {step === "request" && (
        <>
          <AuthHeader
            badge={stepBadge}
            title="Reset your password"
            subtitle="Enter the email address associated with your THALI account. If an account exists, we'll send instructions to reset your password."
          />

          {errorMsg ? <AlertBanner tone="critical" message={errorMsg} /> : null}
          {successMsg ? <AlertBanner tone="info" message={successMsg} /> : null}

          <View style={styles.formContainer}>
            <AuthInput
              label="Registered Email"
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              keyboardType="email-address"
              autoCapitalize="none"
              autoComplete="email"
              textContentType="emailAddress"
              disabled={busy}
              accessibilityLabel="Email address for password recovery"
            />

            <AuthButton
              label="Send reset link"
              loadingLabel="Sending..."
              onPress={handleRequestReset}
              disabled={busy || !email.trim()}
              busy={busy}
              accessibilityLabel="Request Reset Token"
              accessibilityHint="Requests a password reset token for your account."
            />

            <AuthButton
              label="I already have a reset token"
              variant="outline"
              onPress={() => {
                setErrorMsg(null);
                setStep("reset");
              }}
              disabled={busy}
              accessibilityHint="Proceeds directly to the token entry step."
            />
          </View>
        </>
      )}

      {step === "reset" && (
        <>
          <AuthHeader
            badge={stepBadge}
            title="Create a new password"
            subtitle="Choose a new password for your THALI account."
          />

          {errorMsg ? <AlertBanner tone="critical" message={errorMsg} /> : null}
          {successMsg ? <AlertBanner tone="info" message={successMsg} /> : null}

          <View style={styles.formContainer}>
            <AuthInput
              label="Reset Token"
              value={resetToken}
              onChangeText={setResetToken}
              placeholder="Paste your reset token here"
              autoCapitalize="none"
              disabled={busy}
              accessibilityLabel="Reset token input"
              hint="Enter the token received in your password reset email."
            />

            <PasswordInput
              label="New password"
              value={newPassword}
              onChangeText={setNewPassword}
              placeholder="At least 8 characters"
              disabled={busy}
              accessibilityLabel="New password input"
            />

            <PasswordInput
              label="Confirm new password"
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              placeholder="Re-enter new password"
              disabled={busy}
              accessibilityLabel="Confirm new password input"
            />

            <PasswordRequirements
              password={newPassword}
              confirmPassword={confirmPassword}
            />

            <AuthButton
              label="Update password"
              loadingLabel="Updating..."
              onPress={handlePerformReset}
              disabled={busy || !resetToken.trim() || !newPassword || !confirmPassword}
              busy={busy}
              accessibilityLabel="Update Password"
              accessibilityHint="Resets your account password with the provided token."
            />

            <AuthButton
              label="Back to Email Request"
              variant="ghost"
              onPress={() => {
                setErrorMsg(null);
                setStep("request");
              }}
              disabled={busy}
              accessibilityHint="Returns to the email request step."
            />
          </View>
        </>
      )}

      {step === "complete" && (
        <>
          <AuthHeader
            badge={stepBadge}
            title="Password updated"
            subtitle="Your password has been changed successfully. You can now sign in with your new credentials."
          />

          <View style={styles.successCard}>
            <Text style={styles.successCardTitle} allowFontScaling>
              Security Notice
            </Text>
            <Text style={styles.successCardBody} allowFontScaling>
              Your account password has been updated successfully. Existing sessions have been revoked for your protection.
            </Text>
          </View>

          <AuthButton
            label="Sign in"
            onPress={() => router.push("/(auth)/login")}
            accessibilityLabel="Proceed to Sign In"
            accessibilityHint="Navigates to the sign-in screen."
          />
        </>
      )}

      <AuthButton
        label="Return to Sign In"
        variant="ghost"
        onPress={() => router.push("/(auth)/login")}
        disabled={busy}
        accessibilityHint="Navigates back to sign in screen."
      />

      <AuthFooter />
    </AuthScreen>
  );
}

const styles = StyleSheet.create({
  formContainer: {
    gap: spacing.md,
  },
  successCard: {
    backgroundColor: "#F4FAF6",
    borderRadius: radii.md,
    borderWidth: 1.5,
    borderColor: "#C3E6D2",
    padding: spacing.md,
    gap: spacing.xxs,
  },
  successCardTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "700",
    color: "#1E7E34",
  },
  successCardBody: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
});
