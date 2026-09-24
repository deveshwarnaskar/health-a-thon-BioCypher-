import React, { useState } from "react";
import { FlatList, RefreshControl, StyleSheet, View } from "react-native";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { TabSwitcher } from "../../components/primitives/TabSwitcher";
import { LoadingState } from "../../components/primitives/LoadingState";
import { EmptyState } from "../../components/primitives/EmptyState";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { colors, spacing } from "../../theming/tokens";
import { CareTaskCard } from "./CareTaskCard";
import { CareTaskDetailScreen } from "./CareTaskDetailScreen";
import { useCareTasks } from "./useCareTasks";
import { GlucoseEntryForm } from "../glucose/GlucoseEntryForm";
import { useIngestGlucose } from "../glucose/useIngestGlucose";
import { PatientMealScreen } from "../meals/PatientMealScreen";
import type { ApiErrorDetails } from "../../services/api/errors";

export type FHWWorkflowProps = {
  onExit?: () => void;
  testID?: string;
};

type ViewState =
  | { name: "list" }
  | { name: "detail"; taskId: string }
  | { name: "recordGlucose"; patientId: string; taskId: string }
  | { name: "logMeal"; patientId: string; taskId: string };

const STATUS_TABS = [
  { key: "all", label: "All" },
  { key: "open", label: "Open" },
  { key: "in_progress", label: "In Progress" },
  { key: "completed", label: "Completed" },
];

export function FHWWorkflow({ onExit, testID }: FHWWorkflowProps) {
  const [currentView, setCurrentView] = useState<ViewState>({ name: "list" });
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [fieldMessage, setFieldMessage] = useState<string | null>(null);

  const statusParam = selectedStatus === "all" ? undefined : selectedStatus;
  const {
    data: taskList,
    isLoading,
    isRefetching,
    error,
    refetch,
  } = useCareTasks({
    assigned_to_me: true,
    status: statusParam,
  });

  // Glucose ingest hook for FHW home-visit capture
  const activePatientId =
    currentView.name === "recordGlucose" ? currentView.patientId : null;
  const ingestGlucose = useIngestGlucose({
    patientId: activePatientId,
    onSuccess: () => {
      setFieldMessage("Blood glucose reading recorded successfully.");
      if (currentView.name === "recordGlucose") {
        setCurrentView({ name: "detail", taskId: currentView.taskId });
      }
    },
    onError: (err) => {
      const apiErr = err as ApiErrorDetails | undefined;
      setFieldMessage(apiErr?.message || "Failed to record glucose reading.");
    },
  });

  if (currentView.name === "recordGlucose") {
    return (
      <View style={styles.container} testID={testID ? `${testID}-record-glucose` : "fhw-record-glucose"}>
        <TopAppBar
          title="Field Glucose Capture"
          onBack={() => setCurrentView({ name: "detail", taskId: currentView.taskId })}
        />
        <View style={styles.fieldCaptureContainer}>
          {fieldMessage ? (
            <AlertBanner
              title="Notice"
              message={fieldMessage}
              tone="warning"
            />
          ) : null}
          <GlucoseEntryForm
            onSubmit={(data) => ingestGlucose.mutate(data)}
            isSubmitting={ingestGlucose.isPending}
            testID="fhw-glucose-form"
          />
        </View>
      </View>
    );
  }

  if (currentView.name === "logMeal") {
    return (
      <View style={styles.container} testID={testID ? `${testID}-log-meal` : "fhw-log-meal"}>
        <PatientMealScreen
          patientId={currentView.patientId}
          onBack={() => setCurrentView({ name: "detail", taskId: currentView.taskId })}
          testID="fhw-meal-screen"
        />
      </View>
    );
  }

  if (currentView.name === "detail") {
    return (
      <CareTaskDetailScreen
        taskId={currentView.taskId}
        isFhw={true}
        onBack={() => {
          setFieldMessage(null);
          setCurrentView({ name: "list" });
        }}
        onRecordGlucose={(patientId) =>
          setCurrentView({
            name: "recordGlucose",
            patientId,
            taskId: currentView.taskId,
          })
        }
        onLogMeal={(patientId) =>
          setCurrentView({
            name: "logMeal",
            patientId,
            taskId: currentView.taskId,
          })
        }
        testID={testID ? `${testID}-detail` : "fhw-task-detail"}
      />
    );
  }

  const tasks = taskList?.items ?? [];

  return (
    <View style={styles.container} testID={testID ?? "fhw-workflow"}>
      <TopAppBar title="My Tasks" onBack={onExit} />

      <View style={styles.tabsWrapper}>
        <TabSwitcher
          items={STATUS_TABS}
          selected={selectedStatus}
          onSelect={setSelectedStatus}
        />
      </View>

      {fieldMessage ? (
        <View style={styles.bannerWrapper}>
          <AlertBanner
            title="Update"
            message={fieldMessage}
            tone="success"
          />
        </View>
      ) : null}

      {isLoading ? (
        <LoadingState label="Loading assigned tasks…" testID="fhw-tasks-loading" />
      ) : error ? (
        <View style={styles.errorWrapper}>
          <AlertBanner
            title="Error Loading Tasks"
            message={(error as ApiErrorDetails)?.message || "Failed to load assigned tasks."}
            tone="critical"
          />
        </View>
      ) : tasks.length === 0 ? (
        <EmptyState
          title="No Tasks Found"
          message={
            selectedStatus === "all"
              ? "You have no care tasks assigned at this time."
              : `No tasks in '${selectedStatus}' state.`
          }
          testID="fhw-tasks-empty"
        />
      ) : (
        <FlatList
          data={tasks}
          keyExtractor={(item) => item.care_task_id}
          renderItem={({ item }) => (
            <CareTaskCard
              task={item}
              onPress={(selected) =>
                setCurrentView({ name: "detail", taskId: selected.care_task_id })
              }
              testID={`fhw-task-card-${item.care_task_id}`}
            />
          )}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={isRefetching} onRefresh={refetch} />
          }
          testID="fhw-tasks-list"
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  tabsWrapper: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    backgroundColor: colors.surface,
  },
  bannerWrapper: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.xs,
  },
  listContent: {
    padding: spacing.md,
  },
  errorWrapper: {
    padding: spacing.md,
  },
  fieldCaptureContainer: {
    flex: 1,
    padding: spacing.md,
  },
});
