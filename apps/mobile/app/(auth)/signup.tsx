import React, { useRef, useState } from "react";
import { StyleSheet, Text, TextInput as RNTextInputRef, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import * as SecureStore from "expo-secure-store";
import { AlertBanner } from "../../src/components/primitives/AlertBanner";
import { useAuth } from "../../src/auth/AuthProvider";
import { colors, radii, spacing, typography } from "../../src/theming/tokens";
import {
  AuthButton,
  AuthFooter,
  AuthHeader,
  AuthInput,
  AuthModeTabs,
  AuthPanel,
  AuthScreen,
  PasswordInput,
  PasswordRequirements,
  PendingVerificationCard,
  RoleOption,
  RoleSelector,
} from "../../src/features/auth";

/**
 * THALI Mobile Sign-Up Screen
 * Implements a calm, progressive disclosure registration journey
 * for Patients, Caregivers, and Doctors.
 */
export default function SignupScreen() {
  const router = useRouter();
  const { state, signUp, isBootstrapping, isAuthenticated } = useAuth();

  const [role, setRole] = useState<RoleOption>("patient");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [pendingDoctorNotice, setPendingDoctorNotice] = useState(false);

  const inviteCodeRef = useRef<RNTextInputRef>(null);
  const nameRef = useRef<RNTextInputRef>(null);
  const emailRef = useRef<RNTextInputRef>(null);
  const phoneRef = useRef<RNTextInputRef>(null);
  const passwordRef = useRef<RNTextInputRef>(null);
  const confirmPasswordRef = useRef<RNTextInputRef>(null);

  if ((isAuthenticated || state.name === "authenticated") && !pendingDoctorNotice) {
    return <Redirect href="/(app)/shell" />;
  }

  const busy = isBootstrapping || submitting || state.name === "authenticating";

  const handleSignup = async () => {
    setLocalError(null);
    const cleanEmail = email.trim().toLowerCase();

    if (!cleanEmail || !cleanEmail.includes("@")) {
      setLocalError("Please enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setLocalError("Password must be at least 8 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setLocalError("Passwords do not match. Please re-enter.");
      return;
    }

    const cleanPhone = phone.trim();

    if (!signUp) {
      setLocalError("Registration is currently unavailable.");
      return;
    }

    const trimmedName = name.trim();
    setSubmitting(true);
    try {
      const signupPayload: any = {
        email: cleanEmail,
        password,
        name: trimmedName || undefined,
        role,
      };
      if (cleanPhone) {
        signupPayload.phone = cleanPhone;
      }
      if (role === "doctor" && inviteCode.trim()) {
        signupPayload.invite_code = inviteCode.trim();
      }
      const res = await signUp(signupPayload);

      if (trimmedName) {
        try {
          await SecureStore.setItemAsync("thali.patient.signup_name", trimmedName);
        } catch {}
      }

      try {
        await SecureStore.setItemAsync("thali.patient.signup_phone", cleanPhone);
      } catch {}

      if (role === "doctor" && res && res.user_status === "pending_verification") {
        setPendingDoctorNotice(true);
      }
    } catch (err: any) {
      setLocalError(
        err?.message ||
          (typeof err === "string" ? err : "Registration failed. Please check your details.")
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (pendingDoctorNotice) {
    return (
      <AuthScreen>
        <AuthHeader
          title="Verification Pending"
          subtitle="Your account has been registered successfully."
          badge="CLINICIAN ENROLLMENT"
        />

        <AuthPanel>
          <PendingVerificationCard role={role} />

          <AuthButton
            label="Continue to Clinician Portal"
            onPress={() => {
              setPendingDoctorNotice(false);
              router.replace("/(app)/shell");
            }}
            accessibilityHint="Enters the clinician portal with pending verification status."
          />

          <AuthFooter />
        </AuthPanel>
      </AuthScreen>
    );
  }

  return (
    <AuthScreen>
      <AuthHeader
        title="Create Account"
        subtitle="Join THALI × P.L.A.T.E. to access your glycemic health journey."
      />

      <AuthPanel>
        <AuthModeTabs
          activeMode="signup"
          disabled={busy}
          onSelectMode={(mode) => {
            if (mode === "login") {
              router.replace("/(auth)/login");
            }
          }}
        />

        {localError ? <AlertBanner tone="critical" message={localError} /> : null}

        <View style={styles.formContainer}>
          {/* STEP 1: Role Selection */}
          <RoleSelector
            selectedRole={role}
            onSelectRole={setRole}
            disabled={busy}
          />

          {/* Role-Specific Guidance */}
          {role === "caregiver" ? (
            <View style={styles.roleNoticeBox}>
              <Text style={styles.roleNoticeTitle} allowFontScaling>
                Caregiver Connection
              </Text>
              <Text style={styles.roleNoticeText} allowFontScaling>
                After creating your account, you&apos;ll need to be connected to a patient before you can access their care information.
              </Text>
            </View>
          ) : null}

          {role === "doctor" ? (
            <View style={styles.doctorInviteBox}>
              <View style={styles.doctorNoticeHeader}>
                <Text style={styles.doctorNoticeTitle} allowFontScaling>
                  Clinical verification
                </Text>
                <Text style={styles.doctorNoticeText} allowFontScaling>
                  Doctor accounts require authorization before clinical access is enabled. If you have an authorized facility code, enter it below.
                </Text>
              </View>
              <AuthInput
                label="Clinical invite code (Optional)"
                value={inviteCode}
                onChangeText={setInviteCode}
                placeholder="e.g. CLINIC-VERIFIED-2026"
                autoCapitalize="characters"
                inputRef={inviteCodeRef}
                returnKeyType="next"
                onSubmitEditing={() => nameRef.current?.focus()}
                blurOnSubmit={false}
                disabled={busy}
                accessibilityLabel="Clinician invite code input"
                hint="Without an approved code, your account will be registered in pending verification status."
              />
            </View>
          ) : null}

          {/* STEP 2: Personal Details */}
          <View style={styles.stepSection}>
            <Text style={styles.stepTitle} allowFontScaling>
              Your details
            </Text>

            <AuthInput
              label="Full name"
              value={name}
              onChangeText={setName}
              placeholder="e.g. Sita Sharma"
              autoCapitalize="words"
              textContentType="name"
              inputRef={nameRef}
              returnKeyType="next"
              onSubmitEditing={() => emailRef.current?.focus()}
              blurOnSubmit={false}
              disabled={busy}
              accessibilityLabel="Full name input"
            />

            <AuthInput
              label="Email address"
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              keyboardType="email-address"
              autoCapitalize="none"
              autoComplete="email"
              textContentType="emailAddress"
              inputRef={emailRef}
              returnKeyType="next"
              onSubmitEditing={() => phoneRef.current?.focus()}
              blurOnSubmit={false}
              disabled={busy}
              accessibilityLabel="Email address input"
            />

            <AuthInput
              label="Phone number"
              value={phone}
              onChangeText={setPhone}
              placeholder="+91 98765 43210"
              keyboardType="phone-pad"
              textContentType="telephoneNumber"
              inputRef={phoneRef}
              returnKeyType="next"
              onSubmitEditing={() => passwordRef.current?.focus()}
              blurOnSubmit={false}
              disabled={busy}
              accessibilityLabel="Phone number input"
            />
          </View>

          {/* STEP 3: Password */}
          <View style={styles.stepSection}>
            <Text style={styles.stepTitle} allowFontScaling>
              Secure your account
            </Text>

            <PasswordInput
              label="Password"
              value={password}
              onChangeText={setPassword}
              placeholder="At least 8 characters"
              inputRef={passwordRef}
              returnKeyType="next"
              onSubmitEditing={() => confirmPasswordRef.current?.focus()}
              blurOnSubmit={false}
              disabled={busy}
              accessibilityLabel="Password input"
            />

            <PasswordInput
              label="Confirm password"
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              placeholder="Re-enter password"
              inputRef={confirmPasswordRef}
              returnKeyType="done"
              onSubmitEditing={handleSignup}
              disabled={busy}
              accessibilityLabel="Confirm password input"
            />

            <PasswordRequirements
              password={password}
              confirmPassword={confirmPassword}
            />
          </View>

          {/* Submit Button */}
          <AuthButton
            label="Sign up"
            loadingLabel="Creating account..."
            onPress={handleSignup}
            disabled={busy || !email.trim() || !password || !confirmPassword}
            busy={busy}
            accessibilityLabel={busy ? "Creating account..." : "Register & Sign In"}
            accessibilityHint="Submits your account registration to THALI."
          />
        </View>

        {/* Navigation to Sign In */}
        <AuthButton
          label="Already have an account? Sign In"
          variant="ghost"
          onPress={() => router.replace("/(auth)/login")}
          disabled={busy}
          accessibilityHint="Navigates back to the sign in screen."
        />

        <AuthFooter />
      </AuthPanel>
    </AuthScreen>
  );
}

const styles = StyleSheet.create({
  formContainer: {
    gap: spacing.lg,
  },
  stepSection: {
    gap: spacing.md,
  },
  stepTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "700",
    color: "#0F172A",
    letterSpacing: 0.3,
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    paddingBottom: spacing.xs,
  },
  roleNoticeBox: {
    backgroundColor: "#FDF8F3",
    padding: spacing.md,
    borderRadius: radii.md,
    borderLeftWidth: 3,
    borderLeftColor: colors.assistive,
    borderWidth: 1,
    borderColor: "#FCE7D6",
    gap: 4,
  },
  roleNoticeTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "600",
    color: "#9A3412",
  },
  roleNoticeText: {
    fontSize: typography.fontSize.caption,
    color: "#78350F",
    lineHeight: 18,
  },
  doctorInviteBox: {
    backgroundColor: "#F0F8FA",
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1.5,
    borderColor: "#B8DEE7",
    gap: spacing.sm,
  },
  doctorNoticeHeader: {
    gap: 4,
  },
  doctorNoticeTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "700",
    color: colors.primary,
  },
  doctorNoticeText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
});
