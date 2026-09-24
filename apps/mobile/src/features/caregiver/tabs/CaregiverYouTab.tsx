import React, { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useAuth } from "../../../auth/AuthProvider";
import { useCaregiverContext } from "../context/CaregiverContext";
import { AppCard } from "../../../components/primitives/AppCard";
import { Button } from "../../../components/primitives/Button";
import { colors, spacing, typography } from "../../../theming/tokens";

export type CaregiverYouTabProps = {
  onSignOut?: () => void | Promise<void>;
  testID?: string;
};

/**
 * Caregiver You Tab (Gate C1).
 * Displays verified account information (role, number of linked patients, active patient)
 * and provides a sign out action using the existing authentication implementation.
 */
export function CaregiverYouTab({ onSignOut, testID = "caregiver-you-tab" }: CaregiverYouTabProps) {
  const { state, signOut } = useAuth();
  const { linkedPatients, activePatient } = useCaregiverContext();
  const [signingOut, setSigningOut] = useState(false);

  const authUser = state.name === "authenticated" ? state.user : null;

  const handleSignOut = async () => {
    setSigningOut(true);
    try {
      if (onSignOut) {
        await onSignOut();
      } else {
        await signOut();
      }
    } finally {
      setSigningOut(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} testID={testID}>
      <View style={styles.header}>
        <Text style={styles.title} allowFontScaling>
          Account
        </Text>
        <Text style={styles.subtitle} allowFontScaling>
          Caregiver session and authorization details
        </Text>
      </View>

      <AppCard accessibilityLabel="Caregiver details">
        <View style={styles.row}>
          <Text style={styles.label} allowFontScaling>
            Role
          </Text>
          <Text style={styles.value} allowFontScaling>
            {authUser?.role ?? "Caregiver"}
          </Text>
        </View>

        <View style={styles.divider} />

        <View style={styles.row}>
          <Text style={styles.label} allowFontScaling>
            Linked Patients
          </Text>
          <Text style={styles.value} allowFontScaling>
            {linkedPatients.length}
          </Text>
        </View>

        <View style={styles.divider} />

        <View style={styles.row}>
          <Text style={styles.label} allowFontScaling>
            Active Patient
          </Text>
          <Text style={styles.value} allowFontScaling>
            {activePatient ? activePatient.name : "None selected"}
          </Text>
        </View>
      </AppCard>

      <View style={styles.signOutSection}>
        <Button
          label={signingOut ? "Signing out…" : "Sign out"}
          variant="outline"
          disabled={signingOut}
          onPress={handleSignOut}
          accessibilityLabel="Sign out of caregiver session"
        />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    gap: spacing.md,
    paddingBottom: spacing.xxl,
  },
  header: {
    gap: spacing.xxs,
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.xs,
  },
  label: {
    fontSize: typography.fontSize.body,
    color: colors.textSecondary,
  },
  value: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.xs,
  },
  signOutSection: {
    marginTop: spacing.md,
  },
});
