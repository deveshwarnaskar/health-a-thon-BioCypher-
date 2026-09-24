import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { TopAppBar } from "../../src/components/primitives/TopAppBar";
import { Button } from "../../src/components/primitives/Button";
import { RoleAwareShell } from "../../src/navigation/RoleAwareShell";
import { useAuth } from "../../src/auth/AuthProvider";
import { roleLabel, type Role } from "../../src/authz/roles";
import { colors, spacing, typography } from "../../src/theming/tokens";
import { LoadingState } from "../../src/components/primitives/LoadingState";
import { CaregiverExperience } from "../../src/features/caregiver";
import { DoctorWorkstation } from "../../src/features/doctor";
import { DietitianWorkflow } from "../../src/features/meals";
import { FHWWorkflow, CoordinatorWorkflow } from "../../src/features/tasks";
import { PatientExperience } from "../../src/features/patient";
import { useSyncLifecycle } from "../../src/sync/syncLifecycle";

/**
 * Protected, role-aware shell. Role derives exclusively from the verified
 * AuthenticatedContext returned by GET /api/v2/auth/verify. Destinations are
 * placeholders until later vertical slices (Gate 10D-10G) land.
 */
export default function ShellScreen() {
  const { state, signOut } = useAuth();
  // Automatically manages encrypted SQLite initialization & outbox synchronization
  useSyncLifecycle();

  const [selectedDestination, setSelectedDestination] = useState<string | null>(null);
  const [signingOut, setSigningOut] = useState(false);

  if (state.name !== "authenticated") {
    return <LoadingState label="Restoring session…" />;
  }

  const role = state.user.role as Role | null;
  if (!role) {
    return <LoadingState label="Preparing your area…" />;
  }

  if (role === "Patient") {
    return (
      <PatientExperience
        patientId={state.user.patient_id ?? null}
        patientName={state.user.actor_id}
        onSignOut={signOut}
      />
    );
  }

  if (role === "Caregiver") {
    return <CaregiverExperience onSignOut={signOut} />;
  }

  // Doctor / Clinician Workstation (Gate 10F-M / P.L.A.T.E. Clinical Workspace)
  if (role === "Doctor") {
    return (
      <DoctorWorkstation
        initialFlow={selectedDestination as any}
        onSignOut={signOut}
        onExit={() => setSelectedDestination(null)}
      />
    );
  }

  // Gate 10H-M: Dietitian meal & nutrition vertical slice
  if (role === "Dietitian" && selectedDestination === "food") {
    return <DietitianWorkflow flow="food" onHome={() => setSelectedDestination(null)} />;
  }

  if (role === "Dietitian" && selectedDestination === "patients") {
    return <DietitianWorkflow flow="patients" onHome={() => setSelectedDestination(null)} />;
  }

  // Gate 10J-M: Field Health Worker task & field data capture workflow
  if (role === "FieldHealthWorker" && (selectedDestination === "tasks" || selectedDestination === "visits")) {
    return <FHWWorkflow onExit={() => setSelectedDestination(null)} />;
  }

  // Gate 10J-M: Care Coordinator facility queue & task assignment workflow
  if (role === "CareCoordinator" && (selectedDestination === "queue" || selectedDestination === "tasks")) {
    return <CoordinatorWorkflow onExit={() => setSelectedDestination(null)} />;
  }

  return (
    <View style={styles.container}>
      <TopAppBar title="P.L.A.T.E." leadingLabel="Signed-in view" />
      <RoleAwareShell role={role} onDestinationPress={setSelectedDestination} />

      {selectedDestination ? (
        <View style={styles.selectionNote}>
          <Text style={styles.selectionText} allowFontScaling>
            “{selectedDestination}” is a placeholder — workflow lands in a later
            vertical slice.
          </Text>
          <Button
            label="Dismiss"
            variant="outline"
            onPress={() => setSelectedDestination(null)}
          />
        </View>
      ) : null}

      <View style={styles.sectionFooter}>
        <Text style={styles.roleText} allowFontScaling>
          Signed in as {roleLabel(role)}
        </Text>
        <Button
          label={signingOut ? "Signing out…" : "Sign out"}
          variant="ghost"
          disabled={signingOut}
          onPress={async () => {
            setSigningOut(true);
            try {
              await signOut();
            } finally {
              setSigningOut(false);
            }
          }}
          accessibilityHint="Ends this session and returns to the sign-in screen."
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  selectionNote: {
    position: "absolute",
    left: spacing.md,
    right: spacing.md,
    bottom: spacing.xxl,
    backgroundColor: colors.surface,
    borderRadius: 8,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.sm,
  },
  selectionText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
  },
  sectionFooter: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  roleText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
  },
});