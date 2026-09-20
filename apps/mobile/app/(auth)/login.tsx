import React, { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { Button } from "../../src/components/primitives/Button";
import { TextInput } from "../../src/components/primitives/TextInput";
import { AlertBanner } from "../../src/components/primitives/AlertBanner";
import { useAuth } from "../../src/auth/AuthProvider";
import { colors, radii, spacing, typography } from "../../src/theming/tokens";
import type { AuthFlowState } from "../../src/auth/authStateMachine";

/**
 * Mobile login screen for THALI clinical and patient access.
 * Authenticates directly against backend PostgreSQL-backed JWT endpoints (/api/v2/auth/login).
 */
export default function LoginScreen() {
  const router = useRouter();
  const { state, signIn, recoverPassword, isBootstrapping, isAuthenticated } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  if (isAuthenticated || state.name === "authenticated") {
    return <Redirect href="/(app)/shell" />;
  }

  if (state.name === "access_denied" || state.name === "deactivated") {
    return <Redirect href="/(app)/access-denied" />;
  }

  const busy = isBootstrapping || state.name === "authenticating";

  const handleLogin = async () => {
    setLocalError(null);
    if (!email.trim() && !password) {
      await signIn();
      return;
    }
    if (!email.trim()) {
      setLocalError("Please enter your email address.");
      return;
    }
    if (!password) {
      setLocalError("Please enter your password.");
      return;
    }

    try {
      await signIn(email.trim(), password);
    } catch {
      // Errors dispatched to state machine or caught here
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.brand}>
        <Text style={styles.title} allowFontScaling>
          THALI
        </Text>
        <Text style={styles.subtitle} allowFontScaling>
          Trusted Healthcare Access — sign in with your clinic credentials.
        </Text>
      </View>

      {localError ? (
        <AlertBanner tone="critical" message={localError} />
      ) : state.name === "failed" || state.name === "session_expired" ? (
        <AlertBanner tone="critical" message={messageForState(state)} />
      ) : null}

      <View style={styles.form}>
        <TextInput
          label="Email"
          value={email}
          onChangeText={setEmail}
          placeholder="patient@thali.dev"
          keyboardType="email-address"
          autoCapitalize="none"
          disabled={busy}
          accessibilityLabel="Email address input"
        />

        <TextInput
          label="Password"
          value={password}
          onChangeText={setPassword}
          placeholder="••••••••"
          secureTextEntry
          disabled={busy}
          accessibilityLabel="Password input"
        />

        <Button
          label={busy ? "Secure sign-in (in progress)…" : "Continue with clinic sign-in"}
          onPress={handleLogin}
          disabled={busy}
          accessibilityHint="Authenticates your credentials with the THALI service."
        />
      </View>

      {recoverPassword ? (
        <Button
          label="Forgot password / Reset credentials"
          variant="ghost"
          onPress={async () => {
            await recoverPassword();
          }}
          disabled={busy}
          accessibilityHint="Opens identity provider self-service credential recovery."
        />
      ) : (
        <View style={styles.actionsRow}>
          <Pressable
            accessibilityRole="link"
            accessibilityLabel="Forgot password recovery link"
            onPress={() => router.push("/(auth)/forgot-password")}
            disabled={busy}
            style={styles.linkButton}
          >
            <Text style={styles.linkText}>Forgot password?</Text>
          </Pressable>
          <Pressable
            accessibilityRole="link"
            accessibilityLabel="Create account sign up link"
            onPress={() => router.push("/(auth)/signup")}
            disabled={busy}
            style={styles.linkButton}
          >
            <Text style={styles.linkText}>Don&apos;t have an account? Sign Up</Text>
          </Pressable>
        </View>
      )}

      <View style={styles.guidanceBox}>
        <Text style={styles.guidanceTitle} allowFontScaling>
          Clinic Enrollment &amp; Access
        </Text>
        <Text style={styles.guidanceText} allowFontScaling>
          Patients, caregivers, doctors, and nurses use clinic-issued credentials
          configured by your health facility administrator.
        </Text>
      </View>

      <Text style={styles.footnote} allowFontScaling>
        Requires an authorized account and clinic relationship to proceed.
        You will return here automatically if your session expires.
      </Text>
    </View>
  );
}

function messageForState(state: AuthFlowState): string {
  if (state.name === "session_expired") {
    return "Your session expired. Please sign in again to continue.";
  }
  if (state.name !== "failed") {
    return "Sign-in could not be completed. Please check your credentials.";
  }

  switch (state.category) {
    case "network":
      return "We couldn't reach the identity service. Check your connection and try again.";
    case "timeout":
      return "Sign-in timed out. Please try again.";
    case "server_unavailable":
      return "The identity service is temporarily unavailable. Please try again shortly.";
    case "configuration":
      return "Authentication is not configured for this build. Contact your administrator.";
    default:
      return "Sign-in could not be completed. Please check your email and password.";
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: "center",
    padding: spacing.xl,
    gap: spacing.md,
  },
  brand: {
    gap: spacing.xs,
    marginBottom: spacing.xs,
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
  footnote: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    textAlign: "center",
  },
  guidanceBox: {
    backgroundColor: colors.surface,
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.xs,
  },
  guidanceTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  guidanceText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  actionsRow: {
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  linkButton: {
    paddingVertical: spacing.xs,
    alignItems: "center",
  },
  linkText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.primary,
    fontWeight: typography.weight.medium,
  },
});