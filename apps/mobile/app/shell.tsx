import React, { useState } from "react";
import { Redirect, router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { TopAppBar } from "../src/components/primitives/TopAppBar";
import { Button } from "../src/components/primitives/Button";
import { RoleAwareShell } from "../src/navigation/RoleAwareShell";
import { useUiStore } from "../src/store/uiStore";
import { colors, spacing, typography } from "../src/theming/tokens";

/**
 * Role-aware shell route. No auth in Gate 10B: mode is UI-only state; when
 * Gate 10C lands, this route derives the mode from AuthenticatedContext roles
 * instead of the dev placeholder.
 */
export default function ShellScreen() {
  const activeRoleMode = useUiStore((state) => state.activeRoleMode);
  const [selectedDestination, setSelectedDestination] = useState<string | null>(null);

  if (!activeRoleMode) {
    return <Redirect href="/" />;
  }

  return (
    <View style={styles.container}>
      <TopAppBar
        title="P.L.A.T.E. Preview"
        onBack={() => router.replace("/")}
        leadingLabel="Back to mode selection"
      />
      <RoleAwareShell
        role={activeRoleMode}
        onDestinationPress={setSelectedDestination}
      />
      {selectedDestination ? (
        <View style={styles.selectionNote}>
          <Text style={styles.selectionText} allowFontScaling>
            “{selectedDestination}” is a placeholder — workflow lands in a later
            vertical slice.
          </Text>
          <Button label="Dismiss" variant="outline" onPress={() => setSelectedDestination(null)} />
        </View>
      ) : null}
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
    bottom: spacing.lg,
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
});