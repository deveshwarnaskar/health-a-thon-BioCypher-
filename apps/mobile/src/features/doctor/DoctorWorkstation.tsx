import React, { useState } from "react";
import { StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors } from "../../theming/tokens";
import { doctorPalette } from "./doctorDesign";
import { useAuth } from "../../auth/AuthProvider";
import { OfflineBanner } from "../../components/primitives/OfflineBanner";
import { DoctorScreenHeader } from "./DoctorScreenHeader";
import { DoctorBottomNav } from "./DoctorBottomNav";
import {
  DoctorHomeTab,
  DoctorPatientsTab,
  DoctorReviewTab,
  DoctorTasksTab,
  DoctorWorkspaceHubTab,
} from "./tabs";
import { PatientClinicalWorkspace } from "./PatientClinicalWorkspace";
import { CreateMedicationPlanScreen } from "./CreateMedicationPlanScreen";
import { MonitoringWorkspace } from "./MonitoringWorkspace";
import { ReportsWorkspace } from "./ReportsWorkspace";
import { MedicationCohortWorkspace } from "./MedicationCohortWorkspace";
import { DocumentsCohortWorkspace } from "./DocumentsCohortWorkspace";
import { CommunicationWorkspace } from "./CommunicationWorkspace";
import { AuditWorkspace } from "./AuditWorkspace";
import { usePatients } from "./usePatients";
import { useReviewQueue } from "./useReviewQueue";
import { useCareTasks } from "./useCareTasks";
import type { PatientSummaryResponse } from "../../services/schemas/patients";
import type { DoctorDestinationKey } from "./DoctorSidebar";

export type DoctorWorkstationProps = {
  initialFlow?: DoctorDestinationKey | "cohort" | null;
  onSignOut?: () => void;
  onExit?: () => void;
  testID?: string;
};

import {
  resolveInitialDoctorState,
  getSubWorkspaceTitle,
  getTabTitle,
  type DoctorTab,
  type DoctorSubWorkspaceKey,
} from "./doctorNavigation";

export {
  resolveInitialDoctorState,
  getSubWorkspaceTitle,
  getTabTitle,
  type DoctorTab,
  type DoctorSubWorkspaceKey,
};

export function DoctorWorkstation({
  initialFlow = "overview",
  onSignOut,
  onExit,
  testID = "doctor-workstation",
}: DoctorWorkstationProps) {
  const { state, signOut } = useAuth();
  const user = state.name === "authenticated" ? state.user : null;

  const initial = resolveInitialDoctorState(initialFlow);
  const [currentTab, setCurrentTab] = useState<DoctorTab>(initial.tab);
  const [activeSubWorkspace, setActiveSubWorkspace] = useState<DoctorSubWorkspaceKey | null>(
    initial.sub
  );
  const [selectedPatient, setSelectedPatient] = useState<PatientSummaryResponse | null>(null);
  const [authoringPlanForPatient, setAuthoringPlanForPatient] =
    useState<PatientSummaryResponse | null>(null);

  const { patients, isLoading: isLoadingPatients, refetch: refetchPatients } = usePatients();
  const { artifactCount: reviewCount, refetch: refetchQueue } = useReviewQueue();
  const { taskCount, refetch: refetchTasks } = useCareTasks();

  const handleGlobalRefresh = async () => {
    await Promise.all([refetchPatients(), refetchQueue(), refetchTasks()]);
  };

  const handleOpenPatientById = (patientId: string) => {
    const found = patients.find((p) => p.patient_id === patientId);
    if (found) {
      setSelectedPatient(found);
    } else {
      setSelectedPatient({
        patient_id: patientId,
        uh_id: `UH-${patientId.slice(0, 6)}`,
        name: `Patient ${patientId.slice(0, 6)}`,
        facility_id: user?.facility_id ?? "facility-1",
        active: true,
        created_at: new Date().toISOString(),
      });
    }
  };

  // Full-screen flow: Create Medication Plan
  if (authoringPlanForPatient) {
    return (
      <SafeAreaView edges={["top", "left", "right"]} style={styles.safeArea}>
        <CreateMedicationPlanScreen
          patient={authoringPlanForPatient}
          onCancel={() => setAuthoringPlanForPatient(null)}
          onCreated={() => {
            setAuthoringPlanForPatient(null);
            setCurrentTab("workspace");
            setActiveSubWorkspace("plans");
          }}
        />
      </SafeAreaView>
    );
  }

  // Full-screen flow: Patient Clinical Longitudinal Workspace
  if (selectedPatient) {
    return (
      <SafeAreaView edges={["top", "left", "right"]} style={styles.safeArea}>
        <PatientClinicalWorkspace
          key={selectedPatient.patient_id}
          patient={selectedPatient}
          onBack={() => setSelectedPatient(null)}
        />
      </SafeAreaView>
    );
  }

  const doctorDisplayName =
    user?.name ||
    (user?.email ? user.email.split("@")[0] : null) ||
    (user?.actor_id && !/^[0-9a-f]{8}-[0-9a-f]{4}/i.test(user.actor_id) ? user.actor_id : "Doctor");

  return (
    <SafeAreaView edges={["top", "left", "right"]} style={styles.safeArea} testID={testID}>
      <OfflineBanner />

      {/* Doctor Screen Header */}
      <DoctorScreenHeader
        doctorName={doctorDisplayName}
        facilityId={user?.facility_id ?? "Facility 1"}
        showGreeting={currentTab === "dashboard" && !activeSubWorkspace}
        title={activeSubWorkspace ? getSubWorkspaceTitle(activeSubWorkspace) : getTabTitle(currentTab)}
        subtitle={
          activeSubWorkspace
            ? "Specialized clinical workstation view"
            : currentTab === "patients"
            ? `${patients.length} Registered Patient${patients.length === 1 ? "" : "s"} · Clinical Surveillance`
            : undefined
        }
        pendingReviewCount={reviewCount}
        onPressReviews={() => {
          setSelectedPatient(null);
          setActiveSubWorkspace(null);
          setCurrentTab("review");
        }}
        onSignOut={onSignOut || signOut}
        onBack={activeSubWorkspace ? () => setActiveSubWorkspace(null) : undefined}
      />

      {/* Main Tab / Sub-Workspace Body */}
      <View style={styles.body}>
        {activeSubWorkspace === "monitoring" ? (
          <MonitoringWorkspace
            patients={patients}
            onSelectPatient={(p) => setSelectedPatient(p)}
          />
        ) : activeSubWorkspace === "reports" ? (
          <ReportsWorkspace
            patients={patients}
            onSelectPatient={(p) => setSelectedPatient(p)}
          />
        ) : activeSubWorkspace === "plans" ? (
          <MedicationCohortWorkspace
            patients={patients}
            onOpenPatientById={handleOpenPatientById}
            onAuthorPlanForPatient={(p) => setAuthoringPlanForPatient(p)}
          />
        ) : activeSubWorkspace === "documents" ? (
          <DocumentsCohortWorkspace
            patients={patients}
            onOpenPatientById={handleOpenPatientById}
          />
        ) : activeSubWorkspace === "messages" ? (
          <CommunicationWorkspace
            patients={patients}
            onOpenPatientById={handleOpenPatientById}
          />
        ) : activeSubWorkspace === "audit" ? (
          <AuditWorkspace
            patients={patients}
            onSelectPatient={(p) => setSelectedPatient(p)}
          />
        ) : currentTab === "dashboard" ? (
          <DoctorHomeTab
            doctorName={doctorDisplayName}
            doctorAccountId={user?.actor_id}
            doctorDisplayName={doctorDisplayName}
            facilityId={user?.facility_id}
            patients={patients}
            reviewCount={reviewCount}
            taskCount={taskCount}
            isLoading={isLoadingPatients}
            onRefresh={handleGlobalRefresh}
            onSelectPatient={(p) => setSelectedPatient(p)}
            onNavigateToPatients={() => setCurrentTab("patients")}
            onNavigateToReview={() => setCurrentTab("review")}
            onNavigateToTasks={() => setCurrentTab("tasks")}
            onNavigateToWorkspaceHub={() => setCurrentTab("workspace")}
            onNavigateToSubWorkspace={(sub) => {
              setCurrentTab("workspace");
              setActiveSubWorkspace(sub);
            }}
            onSignOut={onSignOut || signOut}
          />
        ) : currentTab === "patients" ? (
          <DoctorPatientsTab
            patients={patients}
            isLoading={isLoadingPatients}
            onRefresh={handleGlobalRefresh}
            onSelectPatient={(p) => setSelectedPatient(p)}
          />
        ) : currentTab === "review" ? (
          <DoctorReviewTab onOpenPatientById={handleOpenPatientById} />
        ) : currentTab === "tasks" ? (
          <DoctorTasksTab
            patients={patients}
            onOpenPatientById={handleOpenPatientById}
          />
        ) : currentTab === "workspace" ? (
          <DoctorWorkspaceHubTab
            doctorName={doctorDisplayName}
            facilityId={user?.facility_id}
            onSelectWorkspace={(sub) => setActiveSubWorkspace(sub)}
            onSignOut={onSignOut || signOut}
          />
        ) : null}
      </View>

      {/* Floating 5-Tab Doctor Navigation */}
      <DoctorBottomNav
        currentTab={currentTab}
        onSelectTab={(tab) => {
          setActiveSubWorkspace(null);
          setCurrentTab(tab);
        }}
        badgeCount={{
          reviews: reviewCount,
          tasks: taskCount,
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: doctorPalette.appBackground,
  },
  fullscreenContainer: {
    flex: 1,
    backgroundColor: doctorPalette.appBackground,
  },
  body: {
    flex: 1,
    backgroundColor: doctorPalette.appBackground,
  },
});
