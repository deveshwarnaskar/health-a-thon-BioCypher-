import React, { useState } from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { Button } from "../../src/components/primitives/Button";
import { TextInput } from "../../src/components/primitives/TextInput";
import { AlertBanner } from "../../src/components/primitives/AlertBanner";
import { useAuth } from "../../src/auth/AuthProvider";
import { colors, radii, spacing, typography } from "../../src/theming/tokens";

const ROLES = [
  { label: "Patient", value: "patient" },
  { label: "Caregiver", value: "caregiver" },
  { label: "Doctor", value: "doctor" },
  { label: "Nurse", value: "nurse" },
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
  const [localError, setLocalError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated || state.name === "authenticated") {
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
      await signUp({
        email: cleanEmail,
        password,
        name: name.trim() || undefined,
        phone: phone.trim() || undefined,
        role,
      });
    } catch (err: any) {
      setLocalError(
        err?.message ||
          (typeof err === "string" ? err : "Registration failed. Please check your details.")
      );
    } finally {
      setSubmitting(false);
    }
  };

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
                  style={[styles.roleChip, selected && styles.roleChipSelected]}
                  onPress={() => setRole(r.value)}
                  disabled={busy}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                >
                  <Text
                    style={[styles.roleChipText, selected && styles.roleChipTextSelected]}
                    allowFontScaling
                  >
                    {r.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

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
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  roleChip: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  roleChipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  roleChipText: {
    fontSize: typography.fontSize.caption,
    fontWeight: "500",
    color: colors.textSecondary,
  },
  roleChipTextSelected: {
    color: "#ffffff",
    fontWeight: "600",
  },
  bottomSection: {
    marginTop: spacing.xs,
  },
});
