import React, { useState } from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { Button } from "../../src/components/primitives/Button";
import { TextInput } from "../../src/components/primitives/TextInput";
import { AlertBanner } from "../../src/components/primitives/AlertBanner";
import { useAuth } from "../../src/auth/AuthProvider";
import { colors, radii, spacing, typography } from "../../src/theming/tokens";

const ROLES = [
  {
    label: "Patient",
    value: "patient",
    description: "Track glycemic health, log meals & manage medications",
  },
  {
    label: "Caregiver",
    value: "caregiver",
    description: "Support and monitor a family member's diabetes care",
  },
  {
    label: "Doctor",
    value: "doctor",
    description: "Clinician review queue, AI insights & treatment plans",
  },
] as const;

export default function SignupScreen() {
  const router = useRouter();
  const { state, signUp, isBootstrapping, isAuthenticated } = useAuth();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState<string>("patient");
  const [inviteCode, setInviteCode] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [pendingDoctorNotice, setPendingDoctorNotice] = useState(false);

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

    if (!signUp) {
      setLocalError("Registration is currently unavailable.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await signUp({
        email: cleanEmail,
        password,
        name: name.trim() || undefined,
        phone: phone.trim() || undefined,
        role,
        invite_code: role === "doctor" && inviteCode.trim() ? inviteCode.trim() : undefined,
      });

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
      <View style={styles.scrollContainer}>
        <View style={styles.brand}>
          <Text style={styles.title} allowFontScaling>
            Verification Pending
          </Text>
          <Text style={styles.subtitle} allowFontScaling>
            Your clinician account has been registered successfully.
          </Text>
        </View>

        <AlertBanner
          tone="info"
          message="Clinician verification is required before active clinical queue operations are unlocked. A health facility administrator will review your credentials."
        />

        <View style={styles.guidanceBox}>
          <Text style={styles.guidanceTitle} allowFontScaling>
            What happens next?
          </Text>
          <Text style={styles.guidanceText} allowFontScaling>
            You can sign in and explore the clinician interface. Full clinical review and patient management will activate once your facility administrator verifies your medical license.
          </Text>
        </View>

        <Button
          label="Continue to Clinician Portal"
          onPress={() => {
            setPendingDoctorNotice(false);
            router.replace("/(app)/shell");
          }}
          accessibilityHint="Enters the clinician portal."
        />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.scrollContainer} keyboardShouldPersistTaps="handled">
      <View style={styles.brand}>
        <Text style={styles.title} allowFontScaling>
          Create Account
        </Text>
        <Text style={styles.subtitle} allowFontScaling>
          Join THALI × P.L.A.T.E. to access your glycemic health journey.
        </Text>
      </View>

      {localError ? <AlertBanner tone="critical" message={localError} /> : null}

      <View style={styles.form}>
        <TextInput
          label="Full Name"
          value={name}
          onChangeText={setName}
          placeholder="e.g. Sita Sharma"
          disabled={busy}
          accessibilityLabel="Full name input"
        />

        <TextInput
          label="Email Address"
          value={email}
          onChangeText={setEmail}
          placeholder="e.g. sita@example.com"
          keyboardType="email-address"
          autoCapitalize="none"
          disabled={busy}
          accessibilityLabel="Email address input"
        />

        <TextInput
          label="Phone Number (Optional)"
          value={phone}
          onChangeText={setPhone}
          placeholder="+91 98765 43210"
          keyboardType="phone-pad"
          disabled={busy}
          accessibilityLabel="Phone number input"
        />

        <View style={styles.roleSection}>
          <Text style={styles.roleLabel} allowFontScaling>
            Select Your Role
          </Text>
          <View style={styles.roleGrid}>
            {ROLES.map((r) => {
              const selected = role === r.value;
              return (
                <TouchableOpacity
                  key={r.value}
                  style={[styles.roleCard, selected && styles.roleCardSelected]}
                  onPress={() => setRole(r.value)}
                  disabled={busy}
                  accessibilityRole="radio"
                  accessibilityState={{ selected }}
                  accessibilityLabel={`${r.label}: ${r.description}`}
                >
                  <View style={styles.roleHeaderRow}>
                    <Text
                      style={[styles.roleTitle, selected && styles.roleTitleSelected]}
                      allowFontScaling
                    >
                      {r.label}
                    </Text>
                    {selected ? (
                      <View style={styles.radioActiveDot} />
                    ) : (
                      <View style={styles.radioInactiveDot} />
                    )}
                  </View>
                  <Text
                    style={[styles.roleDescription, selected && styles.roleDescriptionSelected]}
                    allowFontScaling
                  >
                    {r.description}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        {role === "doctor" ? (
          <View style={styles.inviteContainer}>
            <TextInput
              label="Clinician Invite / Facility Code (Optional)"
              value={inviteCode}
              onChangeText={setInviteCode}
              placeholder="e.g. CLINIC-VERIFIED-2026"
              autoCapitalize="characters"
              disabled={busy}
              accessibilityLabel="Clinician invite code input"
            />
            <Text style={styles.inviteHelperText} allowFontScaling>
              Doctors with an approved clinic invite code are immediately verified. Without a code, your account will be registered in pending verification status until administrator approval.
            </Text>
          </View>
        ) : null}

        <TextInput
          label="Password (min 8 chars)"
          value={password}
          onChangeText={setPassword}
          placeholder="••••••••"
          secureTextEntry
          disabled={busy}
          accessibilityLabel="Password input"
        />

        <TextInput
          label="Confirm Password"
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          placeholder="••••••••"
          secureTextEntry
          disabled={busy}
          accessibilityLabel="Confirm password input"
        />

        <Button
          label={busy ? "Creating Account…" : "Register & Sign In"}
          onPress={handleSignup}
          disabled={busy || !email.trim() || !password || !confirmPassword}
          accessibilityHint="Submits account registration."
        />
      </View>

      <View style={styles.bottomSection}>
        <Button
          label="Already have an account? Sign In"
          variant="ghost"
          onPress={() => router.push("/(auth)/login")}
          disabled={busy}
          accessibilityHint="Navigates back to the sign-in screen."
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
  roleSection: {
    gap: spacing.xs,
  },
  roleLabel: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  roleGrid: {
    gap: spacing.xs,
  },
  roleCard: {
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    gap: spacing.xxs,
  },
  roleCardSelected: {
    borderColor: colors.primary,
    backgroundColor: "#F0F7F9",
  },
  roleHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  roleTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  roleTitleSelected: {
    color: colors.primary,
    fontWeight: "700",
  },
  roleDescription: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  roleDescriptionSelected: {
    color: colors.textPrimary,
  },
  radioActiveDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: colors.primary,
  },
  radioInactiveDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: colors.disabled,
  },
  inviteContainer: {
    gap: spacing.xxs,
  },
  inviteHelperText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 16,
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
  bottomSection: {
    marginTop: spacing.xs,
  },
});
