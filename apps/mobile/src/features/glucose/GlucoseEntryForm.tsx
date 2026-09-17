import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { NumericInput } from "../../components/primitives/NumericInput";
import { Button } from "../../components/primitives/Button";
import { Chip } from "../../components/primitives/Chip";
import { colors, spacing, typography } from "../../theming/tokens";
import {
  READING_TAGS,
  READING_TAG_LABELS,
  type ReadingTag,
} from "./types";

export type GlucoseEntryFormProps = {
  onSubmit: (data: {
    value_mg_dl: number;
    tag?: ReadingTag | null;
  }) => void;
  isSubmitting?: boolean;
  testID?: string;
};

export function GlucoseEntryForm({
  onSubmit,
  isSubmitting = false,
  testID,
}: GlucoseEntryFormProps) {
  const [valueText, setValueText] = useState<string>("");
  const [selectedTag, setSelectedTag] = useState<ReadingTag | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleValueChange = (text: string) => {
    setValueText(text);
    if (validationError) {
      setValidationError(null);
    }
  };

  const handleTagPress = (tag: ReadingTag) => {
    setSelectedTag((prev) => (prev === tag ? null : tag));
  };

  const validate = (): number | null => {
    if (!valueText.trim()) {
      setValidationError("Please enter a glucose reading.");
      return null;
    }
    const num = Number(valueText);
    if (!Number.isInteger(num) || num < 20 || num > 600) {
      setValidationError("Reading must be a whole number between 20 and 600 mg/dL.");
      return null;
    }
    return num;
  };

  const handleSubmit = () => {
    const validNum = validate();
    if (validNum === null) return;

    // taken_at is intentionally NOT computed here: the capture session inside
    // useIngestGlucose locks the reading time once so every retry of the same
    // submission carries a byte-identical body (Gate 09 HMAC dedup).
    onSubmit({
      value_mg_dl: validNum,
      tag: selectedTag,
    });
  };

  const clearForm = () => {
    setValueText("");
    setSelectedTag(null);
    setValidationError(null);
  };

  return (
    <View style={styles.container} testID={testID} accessible={false}>
      <Text style={styles.sectionHeader} allowFontScaling>
        Record Blood Glucose
      </Text>

      <View style={styles.inputRow}>
        <View style={styles.inputWrapper}>
          <NumericInput
            label="Blood Glucose (mg/dL)"
            hint="Valid range: 20 – 600 mg/dL"
            value={valueText}
            onChangeText={handleValueChange}
            error={validationError}
            disabled={isSubmitting}
            accessibilityHint="Enter your blood glucose level in milligrams per deciliter"
          />
        </View>
      </View>

      <Text style={styles.tagGroupLabel} allowFontScaling>
        Measurement Context (Optional)
      </Text>

      <View style={styles.tagGroup} accessibilityRole="radiogroup">
        {READING_TAGS.map((tag) => {
          const isSelected = selectedTag === tag;
          return (
            <Chip
              key={tag}
              label={READING_TAG_LABELS[tag]}
              selected={isSelected}
              onPress={() => handleTagPress(tag)}
              disabled={isSubmitting}
              accessibilityHint={`Selects ${READING_TAG_LABELS[tag]} as the measurement context`}
            />
          );
        })}
      </View>

      <View style={styles.actionRow}>
        <Button
          label={isSubmitting ? "Recording…" : "Record Reading"}
          variant="primary"
          onPress={handleSubmit}
          disabled={isSubmitting || !valueText.trim()}
          accessibilityHint="Submits this blood glucose observation to your clinical record"
        />
        {valueText ? (
          <Button
            label="Clear"
            variant="ghost"
            onPress={clearForm}
            disabled={isSubmitting}
          />
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.md,
  },
  sectionHeader: {
    fontSize: typography.fontSize.title,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  inputWrapper: {
    flex: 1,
  },
  tagGroupLabel: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "500",
    color: colors.textSecondary,
  },
  tagGroup: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  actionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
});
