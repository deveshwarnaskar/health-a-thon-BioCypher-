import React, { useState } from "react";
import { StyleSheet, Text, View, Pressable, ScrollView } from "react-native";
import { useReviewQueue } from "./useReviewQueue";
import { ArtifactDetailScreen } from "./ArtifactDetailScreen";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { LoadingState } from "../../components/primitives/LoadingState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { EmptyState } from "../../components/primitives/EmptyState";
import { spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import type { AIArtifactResponse } from "../../services/schemas/ai";

export type ReviewQueueWorkspaceProps = {
  onOpenPatientById?: (patientId: string) => void;
};

export function ReviewQueueWorkspace({ onOpenPatientById }: ReviewQueueWorkspaceProps) {
  const { queue, artifactCount, isLoading, isError, refetch } = useReviewQueue();
  const [selectedArtifact, setSelectedArtifact] = useState<AIArtifactResponse | null>(null);
  const [kindFilter, setKindFilter] = useState<string>("all");

  if (selectedArtifact) {
    return (
      <ArtifactDetailScreen
        artifactId={selectedArtifact.artifact_id}
        onBack={() => {
          setSelectedArtifact(null);
          refetch();
        }}
      />
    );
  }

  const items = queue.filter((item: AIArtifactResponse) => {
    if (kindFilter === "all") return true;
    return item.artifact_kind === kindFilter;
  });

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>AI Artifact Review Queue</Text>
          <Text style={styles.subtitle}>
            Clinician approval boundary: AI suggestions require human sign-off before becoming clinical record
          </Text>
        </View>
        <Button label="Refresh Queue" variant="outline" onPress={() => refetch()} />
      </View>

      {/* Filter Chips */}
      <View style={styles.filterRow}>
        {["all", "meal_review", "glucose_review", "report_summary"].map((k) => (
          <Pressable
            key={k}
            style={[styles.filterChip, kindFilter === k ? styles.filterChipActive : null]}
            onPress={() => setKindFilter(k)}
          >
            <Text style={[styles.filterText, kindFilter === k ? styles.filterTextActive : null]}>
              {k === "all" ? `All (${artifactCount})` : k.replace("_", " ")}
            </Text>
          </Pressable>
        ))}
      </View>

      {/* Main content */}
      {isLoading ? (
        <LoadingState label="Loading review queue…" />
      ) : isError ? (
        <ErrorState
          title="Could not load review queue"
          message="Failed to connect to clinical AI queue service."
          onRetry={() => refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          title="Review queue empty"
          message="No pending AI-generated artifacts require clinician review."
        />
      ) : (
        <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
          {items.map((item) => (
            <View key={item.artifact_id} style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardHeaderLeft}>
                  <Badge
                    label={item.artifact_kind.replace("_", " ").toUpperCase()}
                    tone="info"
                  />
                  <Badge label="PENDING REVIEW" tone="warning" />
                </View>
                <Text style={styles.timestamp}>
                  {new Date(item.created_at).toLocaleString()}
                </Text>
              </View>

              <Text style={styles.summaryText}>{item.summary}</Text>

              <View style={styles.cardFooter}>
                <View style={styles.patientMeta}>
                  <Text style={styles.patientLabel}>Patient ID:</Text>
                  <Text style={styles.patientId}>{item.patient_id.slice(0, 8)}…</Text>
                  {onOpenPatientById ? (
                    <Pressable onPress={() => onOpenPatientById(item.patient_id)}>
                      <Text style={styles.openPatientLink}>Open Patient</Text>
                    </Pressable>
                  ) : null}
                </View>

                <Button
                  label="Inspect & Review"
                  variant="primary"
                  onPress={() => setSelectedArtifact(item)}
                />
              </View>
            </View>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
    gap: spacing.md,
    flexWrap: "wrap",
  },
  title: {
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  subtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.muted,
    fontWeight: "600",
  },
  filterRow: {
    flexDirection: "row",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    backgroundColor: doctorPalette.surface,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.border,
    flexWrap: "wrap",
  },
  filterChip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
  },
  filterChipActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.surfaceLime,
  },
  filterText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
    fontWeight: "700",
    textTransform: "capitalize",
  },
  filterTextActive: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  card: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.md,
    gap: spacing.sm,
    ...doctorSoftShadow,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
    flexWrap: "wrap",
  },
  cardHeaderLeft: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  timestamp: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  summaryText: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.ink,
    lineHeight: 20,
  },
  cardFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: doctorPalette.border,
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  patientMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  patientLabel: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  patientId: {
    fontSize: typography.fontSize.caption,
    fontWeight: "600",
    color: doctorPalette.ink,
  },
  openPatientLink: {
    fontSize: typography.fontSize.caption,
    fontWeight: "800",
    color: doctorPalette.primary,
    marginLeft: 6,
  },
});
