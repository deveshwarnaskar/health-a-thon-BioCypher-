import React, { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../auth/AuthProvider";
import { useArtifactDetail } from "./useArtifactDetail";
import { useReviewArtifact } from "./useReviewArtifact";
import { ReviewDecisionForm } from "./ReviewDecisionForm";
import { doctorKeys } from "./doctorKeys";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { Divider } from "../../components/primitives/Divider";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { colors, spacing, typography } from "../../theming/tokens";
import type { ApiErrorDetails } from "../../services/api/errors";
import type { ReviewAIArtifactResponse } from "../../services/schemas/ai";

export type ArtifactDetailScreenProps = {
  artifactId: string;
  onBack?: () => void;
  testID?: string;
};

/**
 * AI artifact detail + review (Gate 10F-M). Displays the sealed artifact DTO
 * (summary, kind, state, patient reference, created_at) and the review
 * decision controls. The client never transitions artifact state locally —
 * only the backend review confirmation counts as success. A 403 is a
 * per-resource denial; a 401 is handled globally.
 */
export function ArtifactDetailScreen({ artifactId, onBack, testID }: ArtifactDetailScreenProps) {
  const { state } = useAuth();
  const queryClient = useQueryClient();
  const [success, setSuccess] = useState<ReviewAIArtifactResponse | null>(null);
  const [revoked, setRevoked] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const authUser = state.name === "authenticated" ? state.user : null;
  const isDoctorRole = authUser?.role === "Doctor";

  const detail = useArtifactDetail(artifactId, { enabled: isDoctorRole });

  const review = useReviewArtifact({
    artifactId,
    onSuccess: (data) => {
      setErrorMessage(null);
      setRevoked(false);
      setSuccess(data);
    },
    onError: (error) => {
      const apiError = error as ApiErrorDetails | undefined;
      if (apiError?.httpStatus === 403) {
        // Review capability revoked mid-session: this review boundary closed.
        // NEVER a logout — invalidate the queue and move to a safe revoked view
        // (not a logout, no fabricated success).
        void queryClient.invalidateQueries({ queryKey: doctorKeys.reviewQueue() });
        void queryClient.invalidateQueries({ queryKey: doctorKeys.artifact(artifactId) });
        setSuccess(null);
        setErrorMessage(null);
        setRevoked(true);
        return;
      }
      if (apiError?.httpStatus === 409) {
        setErrorMessage("A conflicting review is already in progress for this artifact. Please refresh and try again.");
      } else if (apiError?.httpStatus === 422) {
        setErrorMessage("The review could not be validated. Check the decision and the corrected summary, then try again.");
      } else if (apiError?.httpStatus === 429) {
        const retry = apiError.retryAfterSeconds;
        setErrorMessage(
          retry
            ? `Too many requests. Please wait ${retry} seconds before reviewing again.`
            : "Too many requests. Please wait a moment before trying again."
        );
      } else if (apiError?.kind === "NETWORK_ERROR") {
        setErrorMessage("Unable to connect. Your review has not been submitted.");
      } else {
        setErrorMessage(apiError?.message ?? "The review could not be submitted. Please try again.");
      }
    },
  });

  if (!isDoctorRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Review Artifact" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="AI artifact review is only available in Doctor mode."
          />
          {onBack ? (
            <Button label="Return to Main Menu" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  if (detail.isError && (detail.error as ApiErrorDetails | undefined)?.httpStatus === 403) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Review Artifact" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <View testID="doctor-artifact-access-revoked">
            <EmptyState
              title="Access Revoked"
              message="Review access to this artifact was removed or expired. Returning to the queue."
            />
          </View>
          {onBack ? (
            <Button label="Return to Review Queue" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  if (revoked) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Review Artifact" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <View testID="doctor-artifact-submit-revoked">
            <EmptyState
              title="Access Revoked"
              message="Your review capability for this artifact was removed while submitting. Returning to the queue."
            />
          </View>
          {onBack ? (
            <Button label="Return to Review Queue" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  if (detail.isError && (detail.error as ApiErrorDetails | undefined)?.httpStatus === 404) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Review Artifact" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <View testID="doctor-artifact-unavailable">
            <EmptyState title="Artifact unavailable" message="This artifact is no longer available for review." />
          </View>
          {onBack ? (
            <Button label="Return to Review Queue" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  if (detail.isLoading && !detail.artifact) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Review Artifact" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <LoadingState label="Loading artifact…" />
      </View>
    );
  }

  if (detail.isError || !detail.artifact) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Review Artifact" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <ErrorState title="Could not load artifact" message="Please try again." onRetry={() => detail.refetch()} />
        </View>
      </View>
    );
  }

  const artifact = detail.artifact;

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Review Artifact"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
      />

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {success ? (
          <View style={styles.content}>
            <AlertBanner
              tone="success"
              title="Review recorded"
              message={`${artifact.artifact_kind} marked ${success.state}.`}
            />
            <Button label="Return to Review Queue" variant="primary" onPress={onBack ?? (() => {})} accessibilityHint="Returns to the pending review queue." />
          </View>
        ) : (
          <>
            {errorMessage ? (
              <AlertBanner tone="critical" title="Review Failed" message={errorMessage} />
            ) : null}

            <View style={styles.header}>
              <Text style={styles.kind} allowFontScaling>
                {artifact.artifact_kind}
              </Text>
              <Badge label={artifact.state} tone="warning" />
            </View>
            <Text style={styles.meta} allowFontScaling>
              Patient {artifact.patient_id} · Created {artifact.created_at}
            </Text>

            <Divider label="AI-Generated Summary" />
            <Text style={styles.summary} allowFontScaling>
              {artifact.summary}
            </Text>

            <Divider label="Review Decision" />
            <ReviewDecisionForm
              isSubmitting={review.isPending}
              onSubmit={(request) => {
                setErrorMessage(null);
                review.mutate(request);
              }}
              testID="doctor-review-decision-form"
            />
          </>
        )}
      </ScrollView>
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
  scrollContent: {
    padding: spacing.md,
    gap: spacing.md,
    paddingBottom: spacing.xxl,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
  },
  kind: {
    flexShrink: 1,
    fontSize: typography.fontSize.headline,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  meta: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  summary: {
    fontSize: typography.fontSize.body,
    lineHeight: typography.lineHeight.body,
    color: colors.textPrimary,
  },
});