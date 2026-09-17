import React, { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Button } from "../../components/primitives/Button";
import { TextInput } from "../../components/primitives/TextInput";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { touchTargetStyle } from "../../components/primitives/button.accessibility";
import type { ReviewAIArtifactRequest } from "../../services/schemas/ai";

export type ReviewDecisionValue = "approve" | "edit" | "reject";

export type ReviewDecisionFormProps = {
  onSubmit: (request: ReviewAIArtifactRequest) => void;
  isSubmitting?: boolean;
  testID?: string;
};

const DECISIONS: readonly { value: ReviewDecisionValue; label: string; hint: string }[] = [
  { value: "approve", label: "Approve", hint: "Accepts the AI summary as reviewed." },
  { value: "edit", label: "Edit", hint: "Replaces the summary with a corrected version." },
  { value: "reject", label: "Reject", hint: "Discards the artifact as unusable." },
];

/**
 * Review decision form (Gate 10F-B contract → Gate 10F-M).
 *
 * The contract requires a decision of approve | edit | reject and an
 * edited_summary for the EDIT decision. The form enforces that a corrected
 * summary is entered before an EDIT can be submitted — the client never
 * fabricates a review result and never transitions state locally; only the
 * backend review confirmation is a success.
 */
export function ReviewDecisionForm({ onSubmit, isSubmitting = false, testID }: ReviewDecisionFormProps) {
  const [decision, setDecision] = useState<ReviewDecisionValue>("approve");
  const [editedSummary, setEditedSummary] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleDecisionPress = (value: ReviewDecisionValue) => {
    setDecision(value);
    setValidationError(null);
  };

  const handleSubmit = () => {
    if (decision === "edit" && editedSummary.trim().length === 0) {
      setValidationError("Enter a corrected summary to submit an Edit review.");
      return;
    }
    setValidationError(null);
    onSubmit({
      decision,
      edited_summary: decision === "edit" ? editedSummary : null,
    });
  };

  return (
    <View style={styles.container} testID={testID}>
      <View style={styles.choiceRow} accessibilityRole="radiogroup" accessibilityLabel="Review decision">
        {DECISIONS.map((choice) => {
          const selected = decision === choice.value;
          return (
            <Pressable
              key={choice.value}
              onPress={() => handleDecisionPress(choice.value)}
              disabled={isSubmitting}
              accessible
              accessibilityRole="radio"
              accessibilityLabel={choice.label}
              accessibilityHint={choice.hint}
              accessibilityState={{ selected, disabled: isSubmitting }}
              style={({ pressed }) => [
                styles.choice,
                touchTargetStyle(),
                selected ? styles.choiceSelected : styles.choiceIdle,
                pressed ? styles.pressed : null,
                isSubmitting ? styles.disabled : null,
              ]}
            >
              <Text style={[styles.choiceLabel, selected ? styles.choiceLabelSelected : null]} allowFontScaling>
                {choice.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {decision === "edit" ? (
        <TextInput
          label="Corrected summary"
          value={editedSummary}
          onChangeText={setEditedSummary}
          error={validationError}
          hint="Required for the Edit decision. Replaces the AI-generated summary."
          accessibilityHint="Enter the corrected summary that will replace the AI-generated one."
        />
      ) : null}

      <Button
        label={isSubmitting ? "Submitting review…" : "Submit review"}
        variant="primary"
        busy={isSubmitting}
        disabled={isSubmitting}
        onPress={handleSubmit}
        accessibilityHint="Sends the review decision to the backend; the patient care team is not committed until confirmed."
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.md,
  },
  choiceRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  choice: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.sm,
    borderRadius: radii.md,
    borderWidth: 1,
  },
  choiceIdle: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
  },
  choiceSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  choiceLabel: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "600",
    color: colors.textSecondary,
  },
  choiceLabelSelected: {
    color: colors.textOnPrimary,
  },
  pressed: {
    opacity: 0.85,
  },
  disabled: {
    opacity: 0.5,
  },
});