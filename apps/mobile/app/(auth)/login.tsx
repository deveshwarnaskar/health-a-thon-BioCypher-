import React, { useRef, useState } from "react";
import { Pressable, StyleSheet, Text, type TextInput as RNTextInputRef, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { AlertBanner } from "../../src/components/primitives/AlertBanner";
import { useAuth } from "../../src/auth/AuthProvider";
import { colors, spacing, typography } from "../../src/theming/tokens";
import type { AuthFlowState } from "../../src/auth/authStateMachine";
import {
  AuthButton,
  AuthFooter,
  AuthHeader,
  AuthInput,
  AuthModeTabs,
  AuthPanel,
  AuthScreen,
  PasswordInput,
} from "../../src/features/auth";

/**
 * THALI Mobile Sign-In Screen
 * Provides professional, clinical-grade authentication directly against backend JWT endpoints.
 */
export default function LoginScreen() {
  const router = useRouter();
  const { state, signIn, isBootstrapping, isAuthenticated } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const passwordRef = useRef<RNTextInputRef>(null);

  if (isAuthenticated || state.name === "authenticated") {
    return <Redirect href="/(app)/shell" />;
  }

  if (state.name === "access_denied" || state.name === "deactivated") {
    return <Redirect href="/access-denied" />;
  }

  const busy = isBootstrapping || state.name === "authenticating";

  const handleLogin = async () => {
    setLocalError(null);
    const cleanEmail = email.trim();

    if (!cleanEmail) {
      setLocalError("Please enter your email address.");
      return;
    }
    if (!cleanEmail.includes("@")) {
      setLocalError("Please enter a valid email address.");
      return;
    }
    if (!password) {
      setLocalError("Please enter your password.");
      return;
    }

    try {
      await signIn(cleanEmail.toLowerCase(), password);
    } catch {
      // Errors dispatched to auth state machine
    }
  };

  return (
    <AuthScreen>
      <AuthHeader
        title="Welcome Back"
        subtitle="Sign in to continue to your THALI × P.L.A.T.E. account."
      />

      <AuthPanel>
        <AuthModeTabs
          activeMode="login"
          disabled={busy}
          onSelectMode={(mode) => {
            if (mode === "signup") {
              router.replace("/(auth)/signup");
            }
          }}
        />

        {localError ? (
          <AlertBanner tone="critical" message={localError} />
        ) : state.name === "failed" || state.name === "session_expired" ? (
          <AlertBanner tone="critical" message={messageForState(state)} />
        ) : null}

        <View style={styles.formContainer}>
          <AuthInput
            label="Email address"
            value={email}
            onChangeText={setEmail}
            placeholder="you@example.com"
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
            textContentType="emailAddress"
            returnKeyType="next"
            onSubmitEditing={() => passwordRef.current?.focus()}
            blurOnSubmit={false}
            disabled={busy}
            accessibilityLabel="Email address input"
          />

          <View style={styles.passwordFieldWrapper}>
            <PasswordInput
              label="Password"
              value={password}
              onChangeText={setPassword}
              placeholder="Enter your password"
              inputRef={passwordRef}
              returnKeyType="done"
              onSubmitEditing={handleLogin}
              disabled={busy}
              accessibilityLabel="Password input"
            />

            <View style={styles.forgotPasswordRow}>
              <Pressable
                accessibilityRole="link"
                accessibilityLabel="Forgot password recovery link"
                accessibilityHint="Navigates to the password recovery screen"
                onPress={() => router.replace("/(auth)/forgot-password")}
                disabled={busy}
                style={styles.forgotButton}
              >
                <Text style={styles.forgotText} allowFontScaling>
                  Forgot password?
                </Text>
              </Pressable>
            </View>
          </View>

          <AuthButton
            label="Sign in"
            loadingLabel="Signing in..."
            onPress={handleLogin}
            disabled={busy}
            busy={busy}
            accessibilityLabel={busy ? "Secure sign-in (in progress)…" : "Continue with clinic sign-in"}
            accessibilityHint="Authenticates your credentials with the THALI × P.L.A.T.E. service."
          />
        </View>

        <View style={styles.signupNavRow}>
          <Text style={styles.signupPromptText} allowFontScaling>
            Don&apos;t have an account?{" "}
          </Text>
          <Pressable
            accessibilityRole="link"
            accessibilityLabel="Create account sign up link"
            accessibilityHint="Navigates to the account registration screen"
            onPress={() => router.replace("/(auth)/signup")}
            disabled={busy}
            style={styles.signupLink}
          >
            <Text style={styles.signupActionText} allowFontScaling>
              Create account
            </Text>
          </Pressable>
        </View>

        <AuthFooter />
      </AuthPanel>
    </AuthScreen>
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
  }

  if (typeof state.error === "string" && state.error.trim().length > 0) {
    return state.error;
  }
  if (state.error && typeof (state.error as any).message === "string") {
    return (state.error as any).message;
  }

  return "Your email or password is incorrect.";
}

const styles = StyleSheet.create({
  formContainer: {
    gap: spacing.md,
  },
  passwordFieldWrapper: {
    gap: spacing.xs,
  },
  forgotPasswordRow: {
    alignItems: "flex-end",
  },
  forgotButton: {
    paddingVertical: spacing.xxs,
  },
  forgotText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.primary,
    fontWeight: "600",
  },
  signupNavRow: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: spacing.xs,
  },
  signupPromptText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
  },
  signupLink: {
    paddingVertical: spacing.xxs,
  },
  signupActionText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.primary,
    fontWeight: "700",
  },
});
