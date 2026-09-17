import React, { useState } from "react";
import { FlatList, RefreshControl, StyleSheet, View } from "react-native";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { TabSwitcher } from "../../components/primitives/TabSwitcher";
import { Button } from "../../components/primitives/Button";
import { LoadingState } from "../../components/primitives/LoadingState";
import { EmptyState } from "../../components/primitives/EmptyState";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { colors, spacing } from "../../theming/tokens";
import { CareTaskCard } from "./CareTaskCard";
import { CareTaskDetailScreen } from "./CareTaskDetailScreen";
import { CreateCareTaskModal } from "./CreateCareTaskModal";
import { ReassignCareTaskModal } from "./ReassignCareTaskModal";
import { useCareTasks } from "./useCareTasks";
import type { ApiErrorDetails } from "../../services/api/errors";

export type CoordinatorWorkflowProps = {
  onExit?: () => void;
  testID?: string;
};

type ViewState =
  | { name: "queue" }
  | { name: "detail"; taskId: string };

const STATUS_TABS = [
  { key: "all", label: "All" },
  { key: "open", label: "Open" },
  { key: "in_progress", label: "In Progress" },
  { key: "completed", label: "Completed" },
];

export function CoordinatorWorkflow({ onExit, testID }: CoordinatorWorkflowProps) {
  const [currentView, setCurrentView] = useState<ViewState>({ name: "queue" });
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [reassignTaskId, setReassignTaskId] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  const statusParam = selectedStatus === "all" ? undefined : selectedStatus;
  const {
    data: taskList,
    isLoading,
    isRefetching,
    error,
    refetch,
  } = useCareTasks({
    status: statusParam,
  });

  if (currentView.name === "detail") {
    return (
      <View style={styles.container}>
        <CareTaskDetailScreen
          taskId={currentView.taskId}
          isCoordinator={true}
          onBack={() => setCurrentView({ name: "queue" })}
          onReassign={(taskId) => setReassignTaskId(taskId)}
          testID={testID ? `${testID}-detail` : "coordinator-task-detail"}
        />
        {reassignTaskId ? (
          <ReassignCareTaskModal
            visible={Boolean(reassignTaskId)}
            taskId={reassignTaskId}
            onClose={() => setReassignTaskId(null)}
            onSuccess={() => {
              setFeedbackMessage("Task reassigned successfully.");
              setReassignTaskId(null);
            }}
            testID="coordinator-reassign-modal"
          />
        ) : null}
      </View>
    );
  }

  const tasks = taskList?.items ?? [];

  return (
    <View style={styles.container} testID={testID ?? "coordinator-workflow"}>
      <TopAppBar title="Facility Task Queue" onBack={onExit} />

      <View style={styles.topBarActions}>
        <Button
          label="Create Task"
          variant="primary"
          onPress={() => setShowCreateModal(true)}
          testID="coordinator-create-task-button"
        />
      </View>

      <View style={styles.tabsWrapper}>
        <TabSwitcher
          items={STATUS_TABS}
          selected={selectedStatus}
          onSelect={setSelectedStatus}
        />
      </View>

      {feedbackMessage ? (
        <View style={styles.bannerWrapper}>
          <AlertBanner
            title="Success"
            message={feedbackMessage}
            tone="success"
          />
        </View>
      ) : null}

      {isLoading ? (
        <LoadingState label="Loading facility task queue…" testID="coordinator-queue-loading" />
      ) : error ? (
        <View style={styles.errorWrapper}>
          <AlertBanner
            title="Error Loading Queue"
            message={(error as ApiErrorDetails)?.message || "Failed to load facility tasks."}
            tone="critical"
          />
        </View>
      ) : tasks.length === 0 ? (
        <EmptyState
          title="No Tasks in Queue"
          message={
            selectedStatus === "all"
              ? "The facility queue currently has no active care tasks."
              : `No tasks in '${selectedStatus}' state.`
          }
          testID="coordinator-queue-empty"
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
              testID={`coordinator-task-card-${item.care_task_id}`}
            />
          )}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={isRefetching} onRefresh={refetch} />
          }
          testID="coordinator-tasks-list"
        />
      )}

      <CreateCareTaskModal
        visible={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSuccess={() => {
          setFeedbackMessage("New care task created successfully.");
          void refetch();
        }}
        testID="coordinator-create-modal"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  topBarActions: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.xs,
    paddingBottom: spacing.xxs,
    backgroundColor: colors.surface,
  },
  tabsWrapper: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
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
});
