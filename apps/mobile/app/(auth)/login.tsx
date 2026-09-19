import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Button } from "../../src/components/primitives/Button";
import { AlertBanner } from "../../src/components/primitives/AlertBanner";
import { useAuth } from "../../src/auth/AuthProvider";
import { colors, radii, spacing, typography } from "../../src/theming/tokens";
import type { AuthFlowState } from "../../src/auth/authStateMachine";

/**
 * Client-side entry point into the OIDC Authorization Code + PKCE flow.
 * No embedded password, no demo token, no skip path (Gate 10C §Auth Flow).
 */
export default function LoginScreen() {
  const { state, signIn, recoverPassword, isBootstrapping } = useAuth();

  const busy = isBootstrapping || state.name === "authenticating";

  return (
    <View style={styles.container}>
      <View style={styles.brand}>
        <Text style={styles.title} allowFontScaling>
          THALI
        </Text>
        <Text style={styles.subtitle} allowFontScaling>
          Trusted Healthcare Access — sign in with your clinic&apos;s identity
          provider.
        </Text>
      </View>

      {state.name === "failed" || state.name === "session_expired" ? (
        <AlertBanner tone="critical" message={messageForState(state)} />
      ) : null}

      <Button
        label={busy ? "Opening secure sign-in…" : "Continue with clinic sign-in"}
        onPress={async () => {
          await signIn();
        }}
        disabled={busy}
        accessibilityHint="Starts the OIDC authorization code flow with PKCE."
      />

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
      ) : null}

      <View style={styles.guidanceBox}>
        <Text style={styles.guidanceTitle} allowFontScaling>
          Clinic Enrollment &amp; Access
        </Text>
        <Text style={styles.guidanceText} allowFontScaling>
          Patients and caregivers are enrolled directly by their healthcare provider.
          Workforce staff must use clinic-issued credentials or invitation links.
        </Text>
      </View>

      <Text style={styles.footnote} allowFontScaling>
        Requires a verified identity and clinic trust relationship to proceed.
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
    return "Sign-in could not be completed. Please try again.";
  }

  switch (state.category) {
    case "network":
      return "We couldn't reach the identity service. Check your connection and try again.";
    case "timeout":
      return "Sign-in timed out. Please try again.";
    case "server_unavailable":
      return "The identity service is temporarily unavailable. Please try again shortly.";
    case "oidc_denied":
      return "Sign-in was cancelled by your identity provider. You were not signed in.";
    case "oidc_canceled":
      return "Sign-in was cancelled. You can try again whenever you're ready.";
    case "configuration":
      return "Authentication is not configured for this build. Contact your administrator.";
    default:
      return "Sign-in could not be completed. Please try again.";
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: "center",
    padding: spacing.xl,
    gap: spacing.lg,
  },
  brand: {
    gap: spacing.sm,
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
});