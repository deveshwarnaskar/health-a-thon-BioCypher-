import React, { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { Button } from "../../src/components/primitives/Button";
import { TextInput } from "../../src/components/primitives/TextInput";
import { AlertBanner } from "../../src/components/primitives/AlertBanner";
import { useAuth } from "../../src/auth/AuthProvider";
import { colors, radii, spacing, typography } from "../../src/theming/tokens";

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const { forgotPassword, resetPassword, isBootstrapping } = useAuth();

  const [step, setStep] = useState<"request" | "reset" | "complete">("request");
  const [email, setEmail] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const busy = isBootstrapping || loading;

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

    setLoading(true);
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
      setLoading(false);
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

    setLoading(true);
    try {
      const res = await resetPassword(resetToken.trim(), newPassword);
      setSuccessMsg(res.message);
      setStep("complete");
    } catch (err: any) {
      setErrorMsg(err?.message || "Password reset failed. Token may be expired or invalid.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.scrollContainer} keyboardShouldPersistTaps="handled">
      <View style={styles.brand}>
        <View style={styles.badgeRow}>
          <Text style={styles.stepBadge} allowFontScaling>
            {step === "complete" ? "SUCCESS" : step === "reset" ? "STEP 2 OF 2" : "STEP 1 OF 2"}
          </Text>
        </View>
        <Text style={styles.title} allowFontScaling>
          Password Recovery
        </Text>
        <Text style={styles.subtitle} allowFontScaling>
          {step === "complete"
            ? "Your account password has been updated successfully."
            : step === "reset"
            ? "Enter your reset token and your chosen new password."
            : "Enter your registered email address to receive secure reset instructions."}
        </Text>
      </View>

      {errorMsg ? <AlertBanner tone="critical" message={errorMsg} /> : null}
      {successMsg ? <AlertBanner tone="info" message={successMsg} /> : null}

      {step === "request" && (
        <View style={styles.form}>
          <TextInput
            label="Registered Email"
            value={email}
            onChangeText={setEmail}
            placeholder="patient@thali.dev"
            keyboardType="email-address"
            autoCapitalize="none"
            disabled={busy}
            accessibilityLabel="Email address for password recovery"
          />

          <Button
            label={busy ? "Submitting…" : "Request Reset Token"}
            onPress={handleRequestReset}
            disabled={busy || !email.trim()}
            accessibilityHint="Requests a password reset token for the email."
          />

          <Button
            label="I already have a reset token"
            variant="ghost"
            onPress={() => {
              setErrorMsg(null);
              setStep("reset");
            }}
            disabled={busy}
            accessibilityHint="Proceeds directly to the token entry step."
          />
        </View>
      )}

      {step === "reset" && (
        <View style={styles.form}>
          <TextInput
            label="Reset Token"
            value={resetToken}
            onChangeText={setResetToken}
            placeholder="Paste reset token here"
            autoCapitalize="none"
            disabled={busy}
            accessibilityLabel="Reset token input"
          />

          <TextInput
            label="New Password (min 8 chars)"
            value={newPassword}
            onChangeText={setNewPassword}
            placeholder="••••••••"
            secureTextEntry
            disabled={busy}
            accessibilityLabel="New password input"
          />

          <TextInput
            label="Confirm New Password"
            value={confirmPassword}
            onChangeText={setConfirmPassword}
            placeholder="••••••••"
            secureTextEntry
            disabled={busy}
            accessibilityLabel="Confirm new password input"
          />

          <Button
            label={busy ? "Updating…" : "Update Password"}
            onPress={handlePerformReset}
            disabled={busy || !resetToken.trim() || !newPassword || !confirmPassword}
            accessibilityHint="Resets your account password with the provided token."
          />

          <Button
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
      )}

      {step === "complete" && (
        <View style={styles.form}>
          <Button
            label="Proceed to Sign In"
            onPress={() => router.push("/(auth)/login")}
            accessibilityHint="Navigates to the sign in screen."
          />
        </View>
      )}

      <View style={styles.bottomSection}>
        <Button
          label="Return to Sign In"
          variant="ghost"
          onPress={() => router.push("/(auth)/login")}
          disabled={busy}
          accessibilityHint="Navigates back to sign in screen."
        />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrollContainer: {
    flexGrow: 1,
    backgroundColor: colors.background,
    justifyContent: "center",
    padding: spacing.xl,
    gap: spacing.md,
  },
  brand: {
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  badgeRow: {
    flexDirection: "row",
  },
  stepBadge: {
    fontSize: typography.fontSize.caption,
    fontWeight: "700",
    color: colors.primary,
    backgroundColor: "#E0F2F7",
    paddingVertical: 2,
    paddingHorizontal: spacing.xs,
    borderRadius: radii.sm,
    letterSpacing: 0.5,
  },
  title: {
    fontSize: typography.fontSize.display,
    fontWeight: "700",
    color: colors.primary,
  },
  subtitle: {
    fontSize: typography.fontSize.body,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  form: {
    gap: spacing.md,
  },
  bottomSection: {
    marginTop: spacing.xs,
  },
});
