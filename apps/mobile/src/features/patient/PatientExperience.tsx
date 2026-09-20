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
import { useAuth } from "../../auth/AuthProvider";
import { usePatientNotifications } from "./api";
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
  const handleSelectRecordOption = (type?: "glucose" | "meal" | "medication" | "task") => {
    if (type === "glucose") {
      setActiveWorkflow("glucose");
    } else if (type === "meal") {
      setActiveWorkflow("meal");
    } else if (type === "medication") {
      setShowMedicationsModal(true);
    } else if (type === "task") {
      setCurrentTab("tasks");
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
    <SafeAreaView style={styles.safeArea}>
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
            onOpenNotifications={() => setShowNotificationsDrawer(true)}
            onOpenAssist={() => setShowAssistModal(true)}
            onSignOut={onSignOut}
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
            onOpenAssist={() => setShowAssistModal(true)}
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
    backgroundColor: colors.surface,
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
