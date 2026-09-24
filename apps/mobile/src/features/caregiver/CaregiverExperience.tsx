import React, { useState } from "react";
import { StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { CaregiverProvider, useCaregiverContext } from "./context/CaregiverContext";
import { CaregiverScreenHeader } from "./components/CaregiverScreenHeader";
import { CaregiverBottomNav, type CaregiverTab } from "./components/CaregiverBottomNav";
import { CaregiverPatientSwitcher } from "./components/CaregiverPatientSwitcher";
import { CaregiverHomeTab } from "./tabs/CaregiverHomeTab";
import { CaregiverRecordTab } from "./tabs/CaregiverRecordTab";
import { CaregiverYouTab } from "./tabs/CaregiverYouTab";
import { colors } from "../../theming/tokens";

export type CaregiverExperienceProps = {
  initialPatientId?: string | null;
  onSignOut?: () => void | Promise<void>;
  testID?: string;
};

/**
 * Internal shell content within the CaregiverProvider context.
 * Owns navigation state for Gate C1 tabs (Home, Record, You).
 */
function CaregiverShellContent({
  onSignOut,
  testID,
}: {
  onSignOut?: () => void | Promise<void>;
  testID?: string;
}) {
  const [currentTab, setCurrentTab] = useState<CaregiverTab>("home");
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const { linkedPatients } = useCaregiverContext();

  return (
    <SafeAreaView edges={["top", "left", "right"]} style={styles.container} testID={testID}>
      <CaregiverScreenHeader />

      <View style={styles.body}>
        {currentTab === "home" ? (
          <CaregiverHomeTab
            onNavigateToRecord={() => setCurrentTab("record")}
            onOpenPatientSwitcher={linkedPatients.length > 1 ? () => setSwitcherOpen(true) : undefined}
          />
        ) : null}

        {currentTab === "record" ? (
          <CaregiverRecordTab onBack={() => setCurrentTab("home")} />
        ) : null}

        {currentTab === "you" ? (
          <CaregiverYouTab onSignOut={onSignOut} />
        ) : null}
      </View>

      <CaregiverBottomNav currentTab={currentTab} onSelectTab={setCurrentTab} />

      {linkedPatients.length > 1 ? (
        <CaregiverPatientSwitcher
          visible={switcherOpen}
          onClose={() => setSwitcherOpen(false)}
        />
      ) : null}
    </SafeAreaView>
  );
}

/**
 * Root Caregiver Experience for role === "Caregiver" (Gate C1).
 * Composed of CaregiverProvider wrapping CaregiverShellContent.
 */
export function CaregiverExperience({
  initialPatientId,
  onSignOut,
  testID = "caregiver-experience",
}: CaregiverExperienceProps) {
  return (
    <CaregiverProvider initialPatientId={initialPatientId}>
      <CaregiverShellContent onSignOut={onSignOut} testID={testID} />
    </CaregiverProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  body: {
    flex: 1,
    backgroundColor: colors.background,
  },
});
