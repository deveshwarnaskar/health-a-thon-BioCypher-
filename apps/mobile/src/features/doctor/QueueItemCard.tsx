import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { AppCard } from "../../components/primitives/AppCard";
import { Badge } from "../../components/primitives/Badge";
import { colors, spacing, typography } from "../../theming/tokens";
import type { AIArtifactResponse } from "../../services/schemas/ai";

export type QueueItemCardProps = {
  artifact: AIArtifactResponse;
  onSelect: (artifact: AIArtifactResponse) => void;
  disabled?: boolean;
};

/**
 * One PENDING_REVIEW artifact in the clinician queue. Displays review facts
 * only (summary, kind, patient reference, created_at) — the sealed detail
 * contract carries no payload/evidence body.
 */
export function QueueItemCard({ artifact, onSelect, disabled = false }: QueueItemCardProps) {
  return (
    <AppCard
      accessibilityLabel={`Review artifact for patient ${artifact.patient_id}`}
      onPress={disabled ? undefined : () => onSelect(artifact)}
      style={disabled ? styles.disabled : undefined}
    >
      <View style={styles.header}>
        <Text style={styles.kind} numberOfLines={1} allowFontScaling>
          {artifact.artifact_kind}
        </Text>
        <Badge label={artifact.state} tone="warning" />
      </View>
      <Text style={styles.summary} numberOfLines={3} allowFontScaling>
        {artifact.summary}
      </Text>
      <Text style={styles.meta} allowFontScaling>
        Patient {artifact.patient_id} · Created {artifact.created_at}
      </Text>
    </AppCard>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
  },
  kind: {
    flexShrink: 1,
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  summary: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textPrimary,
  },
  meta: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  disabled: {
    opacity: 0.5,
  },
});