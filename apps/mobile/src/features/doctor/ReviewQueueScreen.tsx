import React from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { useAuth } from "../../auth/AuthProvider";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { Button } from "../../components/primitives/Button";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { colors, spacing } from "../../theming/tokens";
import { useReviewQueue } from "./useReviewQueue";
import { QueueItemCard } from "./QueueItemCard";
import type { AIArtifactResponse } from "../../services/schemas/ai";
import type { ApiErrorDetails } from "../../services/api/errors";

export type ReviewQueueScreenProps = {
  onSelect?: (artifact: AIArtifactResponse) => void;
  onBack?: () => void;
  testID?: string;
};

/**
 * Doctor pending-review queue (Gate 10F-M). Lists the PENDING_REVIEW artifacts
 * the backend authorizes for the authenticated member's facility, in the
 * backend's deterministic order. A 403 is a per-resource denial (never a
 * logout); a 401 is handled globally by the session layer.
 */
export function ReviewQueueScreen({ onSelect, onBack, testID }: ReviewQueueScreenProps) {
  const { state } = useAuth();
  const authUser = state.name === "authenticated" ? state.user : null;
  const isDoctorRole = authUser?.role === "Doctor";

  const queue = useReviewQueue({ enabled: isDoctorRole });

  if (!isDoctorRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Review" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="The AI review queue is only available in Doctor mode."
          />
          {onBack ? (
            <Button label="Return to Main Menu" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  if (queue.isError && (queue.error as ApiErrorDetails | undefined)?.httpStatus === 403) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Review" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <View testID="doctor-queue-access-revoked">
            <EmptyState
              title="Access Revoked"
              message="Your ability to review artifacts for this facility was removed or expired. Returning to the main menu."
            />
          </View>
          {onBack ? (
            <Button label="Return to Main Menu" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Review"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
      />

      {queue.isLoading ? <LoadingState label="Loading review queue…" /> : null}

      {!queue.isLoading && queue.isError ? (
        <View style={styles.content}>
          <ErrorState
            title="Could not load review queue"
            message="Unable to connect to the AI review endpoints. Please try again."
            onRetry={() => queue.refetch()}
          />
        </View>
      ) : null}

      {!queue.isLoading && !queue.isError && queue.queue.length === 0 ? (
        <View style={styles.content}>
          <EmptyState
            title="No pending reviews"
            message="There are no AI artifacts waiting for your review right now."
          />
        </View>
      ) : null}

      {!queue.isLoading && !queue.isError && queue.queue.length > 0 ? (
        <ScrollView contentContainerStyle={styles.listContent}>
          {queue.queue.map((artifact) => (
            <QueueItemCard
              key={artifact.artifact_id}
              artifact={artifact}
              onSelect={(selected) => onSelect?.(selected)}
            />
          ))}
        </ScrollView>
      ) : null}
    </View>
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
  },
  listContent: {
    padding: spacing.md,
    gap: spacing.sm,
    paddingBottom: spacing.xxl,
  },
});