import React, { useState } from "react";
import { StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors } from "../../theming/tokens";
import { OfflineBanner } from "../../components/primitives/OfflineBanner";
import { BottomNav } from "./components/BottomNav";
import { HomeTab } from "./tabs/HomeTab";
import { RecordTab } from "./tabs/RecordTab";
import { TimelineTab } from "./tabs/TimelineTab";
import { TasksTab } from "./tabs/TasksTab";
import { YouTab } from "./tabs/YouTab";
import { PatientGlucoseScreen } from "../glucose";
import { PatientMealScreen } from "../meals";
import { MedicationListModal } from "./components/MedicationListModal";
import { DocumentViewerModal } from "./components/DocumentViewerModal";
import { NotificationDrawer } from "./components/NotificationDrawer";
import { ThaliAssistModal } from "./components/ThaliAssistModal";
import { WhatsAppConnectModal } from "./components/WhatsAppConnectModal";
import { WhatsAppConnectionFlowModal } from "./components/WhatsAppConnectionFlowModal";
import {
  ActivityEntryModal,
  WeightEntryModal,
  BloodPressureEntryModal,
  SymptomsEntryModal,
  SleepEntryModal,
} from "./components/flows";
import {
  CareProfileModal,
  CareTeamModal,
  ConnectedDevicesModal,
  PrivacySecurityModal,
} from "./components/account";
import { MyReportsModal } from "./components/reports";
import type { RecordOptionKey } from "./tabs/RecordTab";
import { useWhatsAppIdentity } from "./useWhatsAppIdentity";
import { useAuth } from "../../auth/AuthProvider";
import {
  usePatientNotifications,
  useSaveActivity,
  useSaveWeight,
  useSaveBloodPressure,
  useSaveSymptoms,
  useSaveSleep,
} from "./api";
import { useCareTasks } from "../tasks/useCareTasks";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "../../store/query";
import type { PatientTab } from "./types";
import type { NotificationResponse } from "../../services/schemas/notifications";

export type PatientExperienceProps = {
  patientId?: string | null;
  patientName?: string;
  onSignOut: () => Promise<void>;
  onNavigateDestination?: (dest: string) => void;
};

function PatientExperienceContent({
  patientId: propPatientId,
  patientName: propPatientName,
  onSignOut,
  onNavigateDestination,
}: PatientExperienceProps) {
  const { state } = useAuth();
  const authUser = state.name === "authenticated" ? state.user : null;
  const resolvedPatientId = propPatientId ?? authUser?.patient_id ?? null;
  const resolvedName = propPatientName || "Patient";

  // Tab state
  const [currentTab, setCurrentTab] = useState<PatientTab>("home");

  // Contextual modal/flow states
  const [activeWorkflow, setActiveWorkflow] = useState<"glucose" | "meal" | null>(null);
  const [showMedicationsModal, setShowMedicationsModal] = useState(false);
  const [showDocumentsModal, setShowDocumentsModal] = useState(false);
  const [showNotificationsDrawer, setShowNotificationsDrawer] = useState(false);
  const [showAssistModal, setShowAssistModal] = useState(false);
  const [showWhatsAppFlowModal, setShowWhatsAppFlowModal] = useState(false);
  const [hasDismissedOnboardingSession, setHasDismissedOnboardingSession] = useState(false);

  // Secondary observation entry states
  const [showActivityModal, setShowActivityModal] = useState(false);
  const [showWeightModal, setShowWeightModal] = useState(false);
  const [showBloodPressureModal, setShowBloodPressureModal] = useState(false);
  const [showSymptomsModal, setShowSymptomsModal] = useState(false);
  const [showSleepModal, setShowSleepModal] = useState(false);

  // Account & reports modal states
  const [showCareProfileModal, setShowCareProfileModal] = useState(false);
  const [showReportsModal, setShowReportsModal] = useState(false);
  const [showCareTeamModal, setShowCareTeamModal] = useState(false);
  const [showConnectedDevicesModal, setShowConnectedDevicesModal] = useState(false);
  const [showPrivacyModal, setShowPrivacyModal] = useState(false);

  // Secondary save mutations
  const saveActivityMutation = useSaveActivity({
    onSuccess: () => setShowActivityModal(false),
  });
  const saveWeightMutation = useSaveWeight({
    onSuccess: () => setShowWeightModal(false),
  });
  const saveBloodPressureMutation = useSaveBloodPressure({
    onSuccess: () => setShowBloodPressureModal(false),
  });
  const saveSymptomsMutation = useSaveSymptoms({
    onSuccess: () => setShowSymptomsModal(false),
  });
  const saveSleepMutation = useSaveSleep({
    onSuccess: () => setShowSleepModal(false),
  });

  // WhatsApp connection state
  const {
    data: whatsAppIdentity,
    isLoading: isWALoading,
    isOffline: isWAOffline,
  } = useWhatsAppIdentity({ enabled: !!authUser });

  // Every time a user signs in, prompt the onboarding modal until connected.
  // Within an active session, dismissing with "Maybe later" lets the user browse freely.
  const isWhatsAppConnected = whatsAppIdentity?.status === "connected";
  const showWhatsAppOnboarding =
    !!authUser &&
    !isWhatsAppConnected &&
    !hasDismissedOnboardingSession &&
    !isWALoading &&
    !isWAOffline;

  // Badge data
  const { data: notifications = [] } = usePatientNotifications(resolvedPatientId);
  const { data: tasksData } = useCareTasks({ patient_id: resolvedPatientId ?? undefined });

  const unreadCount = notifications.filter(
    (n) => n.status !== "delivered" && n.status !== "cancelled"
  ).length;

  const pendingTasksCount = (tasksData?.items || []).filter(
    (t) => t.status !== "completed"
  ).length;

  // Record Hub selection handler
  const handleSelectRecordOption = (type?: RecordOptionKey) => {
    if (type === "glucose") {
      setActiveWorkflow("glucose");
    } else if (type === "meal") {
      setActiveWorkflow("meal");
    } else if (type === "medication") {
      setShowMedicationsModal(true);
    } else if (type === "task") {
      setCurrentTab("tasks");
    } else if (type === "activity") {
      setShowActivityModal(true);
    } else if (type === "weight") {
      setShowWeightModal(true);
    } else if (type === "blood_pressure") {
      setShowBloodPressureModal(true);
    } else if (type === "symptoms") {
      setShowSymptomsModal(true);
    } else if (type === "sleep") {
      setShowSleepModal(true);
    } else if (type === "documents") {
      setShowDocumentsModal(true);
    }
  };

  // Notification selection routing
  const handleSelectNotification = (n: NotificationResponse) => {
    setShowNotificationsDrawer(false);
    if (n.notification_type === "reminder" || n.template_name.includes("medication")) {
      setShowMedicationsModal(true);
    } else if (n.notification_type === "task_assigned" || n.template_name.includes("task")) {
      setCurrentTab("tasks");
    } else {
      setCurrentTab("timeline");
    }
  };

  // If a full-screen workflow is active (Glucose or Meal):
  if (activeWorkflow === "glucose") {
    return (
      <View style={styles.fullscreenContainer}>
        <PatientGlucoseScreen
          patientId={resolvedPatientId ?? undefined}
          onBack={() => setActiveWorkflow(null)}
        />
      </View>
    );
  }

  if (activeWorkflow === "meal") {
    return (
      <View style={styles.fullscreenContainer}>
        <PatientMealScreen
          patientId={resolvedPatientId ?? undefined}
          onBack={() => setActiveWorkflow(null)}
        />
      </View>
    );
  }

  return (
    <SafeAreaView edges={["top", "left", "right"]} style={styles.safeArea}>
      <OfflineBanner />

      <View style={styles.body}>
        {currentTab === "home" ? (
          <HomeTab
            patientId={resolvedPatientId}
            patientName={resolvedName}
            onNavigateToRecord={handleSelectRecordOption}
            onNavigateToTimeline={() => setCurrentTab("timeline")}
            onNavigateToTasks={() => setCurrentTab("tasks")}
            onNavigateToMedications={() => setShowMedicationsModal(true)}
            onNavigateToReports={() => setShowReportsModal(true)}
            onOpenNotifications={() => setShowNotificationsDrawer(true)}
            onOpenAssist={() => setShowAssistModal(true)}
            onSignOut={onSignOut}
            onConnectWhatsApp={() => setShowWhatsAppFlowModal(true)}
          />
        ) : null}

        {currentTab === "record" ? (
          <RecordTab
            onSelectOption={handleSelectRecordOption}
            onOpenAssist={() => setShowAssistModal(true)}
          />
        ) : null}

        {currentTab === "timeline" ? (
          <TimelineTab
            patientId={resolvedPatientId}
            onOpenAssist={() => setShowAssistModal(true)}
          />
        ) : null}

        {currentTab === "tasks" ? (
          <TasksTab
            patientId={resolvedPatientId}
            onOpenAssist={() => setShowAssistModal(true)}
          />
        ) : null}

        {currentTab === "you" ? (
          <YouTab
            patientName={resolvedName}
            uhid={authUser?.actor_id ? `UHID-${authUser.actor_id.slice(0, 8).toUpperCase()}` : undefined}
            onSignOut={onSignOut}
            onNavigateToMedications={() => setShowMedicationsModal(true)}
            onNavigateToDocuments={() => setShowDocumentsModal(true)}
            onNavigateToNotifications={() => setShowNotificationsDrawer(true)}
            onNavigateToCareProfile={() => setShowCareProfileModal(true)}
            onNavigateToReports={() => setShowReportsModal(true)}
            onNavigateToCareTeam={() => setShowCareTeamModal(true)}
            onNavigateToConnectedDevices={() => setShowConnectedDevicesModal(true)}
            onNavigateToPrivacySecurity={() => setShowPrivacyModal(true)}
            onOpenAssist={() => setShowAssistModal(true)}
            onConnectWhatsApp={() => setShowWhatsAppFlowModal(true)}
          />
        ) : null}
      </View>

      {/* Global 5-Destination Bottom Navigation */}
      <BottomNav
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        badgeCount={{
          tasks: pendingTasksCount,
          notifications: unreadCount,
        }}
      />

      {/* Contextual Modals */}
      <MedicationListModal
        visible={showMedicationsModal}
        onClose={() => setShowMedicationsModal(false)}
        patientId={resolvedPatientId}
      />

      <DocumentViewerModal
        visible={showDocumentsModal}
        onClose={() => setShowDocumentsModal(false)}
        patientId={resolvedPatientId}
      />

      <NotificationDrawer
        visible={showNotificationsDrawer}
        onClose={() => setShowNotificationsDrawer(false)}
        notifications={notifications}
        onSelectNotification={handleSelectNotification}
      />

      <ThaliAssistModal
        visible={showAssistModal}
        onClose={() => setShowAssistModal(false)}
        onNavigateToRecords={() => setCurrentTab("timeline")}
        onNavigateToMeal={() => setActiveWorkflow("meal")}
        onNavigateToReports={() => setShowReportsModal(true)}
        patientId={resolvedPatientId}
      />

      {/* Secondary Observation Entry Modals */}
      <ActivityEntryModal
        visible={showActivityModal}
        onClose={() => setShowActivityModal(false)}
        onSave={async (data) => {
          await saveActivityMutation.mutateAsync({ ...data, patientId: resolvedPatientId || "me" });
        }}
      />

      <WeightEntryModal
        visible={showWeightModal}
        onClose={() => setShowWeightModal(false)}
        onSave={async (data) => {
          await saveWeightMutation.mutateAsync({ ...data, patientId: resolvedPatientId || "me" });
        }}
      />

      <BloodPressureEntryModal
        visible={showBloodPressureModal}
        onClose={() => setShowBloodPressureModal(false)}
        onSave={async (data) => {
          await saveBloodPressureMutation.mutateAsync({ ...data, patientId: resolvedPatientId || "me" });
        }}
      />

      <SymptomsEntryModal
        visible={showSymptomsModal}
        onClose={() => setShowSymptomsModal(false)}
        onSave={async (data) => {
          await saveSymptomsMutation.mutateAsync({ ...data, patientId: resolvedPatientId || "me" });
        }}
      />

      <SleepEntryModal
        visible={showSleepModal}
        onClose={() => setShowSleepModal(false)}
        onSave={async (data) => {
          await saveSleepMutation.mutateAsync({ ...data, patientId: resolvedPatientId || "me" });
        }}
      />

      {/* Account & Clinical Overview Modals */}
      <CareProfileModal
        visible={showCareProfileModal}
        onClose={() => setShowCareProfileModal(false)}
        patientName={resolvedName}
      />

      <MyReportsModal
        visible={showReportsModal}
        onClose={() => setShowReportsModal(false)}
        patientId={resolvedPatientId}
        patientName={resolvedName}
      />

      <CareTeamModal
        visible={showCareTeamModal}
        onClose={() => setShowCareTeamModal(false)}
      />

      <ConnectedDevicesModal
        visible={showConnectedDevicesModal}
        onClose={() => setShowConnectedDevicesModal(false)}
      />

      <PrivacySecurityModal
        visible={showPrivacyModal}
        onClose={() => setShowPrivacyModal(false)}
        patientId={resolvedPatientId}
        uhid={authUser?.actor_id ? `UHID-${authUser.actor_id.slice(0, 8).toUpperCase()}` : undefined}
        onSignOut={onSignOut}
      />

      {/* WhatsApp Connection Onboarding Modal */}
      <WhatsAppConnectModal
        visible={showWhatsAppOnboarding}
        onConnect={() => {
          setHasDismissedOnboardingSession(true);
          setShowWhatsAppFlowModal(true);
        }}
        onDismiss={() => {
          setHasDismissedOnboardingSession(true);
        }}
      />

      {/* WhatsApp Interactive Connection Flow Modal */}
      <WhatsAppConnectionFlowModal
        visible={showWhatsAppFlowModal}
        onClose={() => setShowWhatsAppFlowModal(false)}
        onSuccess={() => {
          setHasDismissedOnboardingSession(true);
        }}
      />
    </SafeAreaView>
  );
}

export function PatientExperience(props: PatientExperienceProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <PatientExperienceContent {...props} />
    </QueryClientProvider>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  fullscreenContainer: {
    flex: 1,
    backgroundColor: colors.background,
  },
  body: {
    flex: 1,
    backgroundColor: colors.background,
  },
});
