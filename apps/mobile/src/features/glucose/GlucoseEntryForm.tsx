import React, { useState } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { NumericInput } from "../../components/primitives/NumericInput";
import { Button } from "../../components/primitives/Button";
import { Chip } from "../../components/primitives/Chip";
import { colors, radii, spacing } from "../../theming/tokens";
import {
  READING_TAGS,
  READING_TAG_LABELS,
  type ReadingTag,
} from "./types";
import { evaluateGlucose } from "./glucoseRanges";
import { parseGlucoseVoiceTranscript } from "./voiceParser";
import { VoiceRecordModal } from "../../components/voice/VoiceRecordModal";

/**
 * Consistent clinical palettes for the logbook (anchored to design tokens).
 */
const palette = {
  teal700: "#0F766E",
  teal600: "#0D9488",
  tealBg: "#F0FDFA",
  tealBorder: "#A7F3D2",
  ink: "#0F172A",
  body: "#334155",
  muted: "#64748B",
  border: "rgba(15, 23, 42, 0.07)",
  hairline: "#EEF2F7",
} as const;

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
  const [showVoiceModal, setShowVoiceModal] = useState(false);
  const [voiceFeedback, setVoiceFeedback] = useState<string | null>(null);

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
    setVoiceFeedback(null);
  };

  // Handle successful voice transcription from Sarvam AI
  const handleVoiceSuccess = (transcript: string) => {
    const parsed = parseGlucoseVoiceTranscript(transcript);
    if (parsed.value !== null) {
      setValueText(String(parsed.value));
      if (validationError) setValidationError(null);
    }
    if (parsed.tag) {
      setSelectedTag(parsed.tag);
    }

    if (parsed.value !== null && parsed.tag) {
      setVoiceFeedback(`Captured "${transcript}" → ${parsed.value} mg/dL (${READING_TAG_LABELS[parsed.tag]})`);
    } else if (parsed.value !== null) {
      setVoiceFeedback(`Captured "${transcript}" → ${parsed.value} mg/dL`);
    } else {
      setVoiceFeedback(`Transcribed: "${transcript}". Please confirm your numeric value.`);
    }
  };

  // Compute live glycemic feedback when a valid number is keyed
  const parsedNum = Number(valueText);
  const isNumberValid =
    valueText.trim().length > 0 &&
    Number.isInteger(parsedNum) &&
    parsedNum >= 20 &&
    parsedNum <= 600;
  const liveStatus = isNumberValid
    ? evaluateGlucose(parsedNum, selectedTag)
    : null;

  return (
    <View style={styles.container} testID={testID} accessible={false}>
      {/* Form Header */}
      <View style={styles.headerRow}>
        <View style={styles.headerIconCircle}>
          <Ionicons name="water" size={17} color={palette.teal600} />
        </View>
        <View style={styles.headerTitles}>
          <Text style={styles.sectionHeader} allowFontScaling>
            Record Blood Glucose
          </Text>
          <Text style={styles.sectionSubheader} allowFontScaling>
            Log your measurement from your glucometer
          </Text>
        </View>
      </View>

      {/* Voice Recognition Toast / Feedback */}
      {voiceFeedback ? (
        <View style={styles.voiceFeedbackBanner}>
          <Ionicons name="sparkles" size={14} color={palette.teal600} style={{ marginRight: 6 }} />
          <Text style={styles.voiceFeedbackText} allowFontScaling numberOfLines={2}>
            {voiceFeedback}
          </Text>
          <TouchableOpacity
            onPress={() => setVoiceFeedback(null)}
            accessibilityRole="button"
            accessibilityLabel="Dismiss voice message"
          >
            <Ionicons name="close" size={14} color={palette.muted} />
          </TouchableOpacity>
        </View>
      ) : null}

      {/* Numeric Reading Input with inline voice capture */}
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
            trailing={
              <TouchableOpacity
                style={styles.micButton}
                onPress={() => setShowVoiceModal(true)}
                accessibilityRole="button"
                accessibilityLabel="Speak blood glucose reading"
                activeOpacity={0.7}
              >
                <Ionicons name="mic" size={20} color={palette.teal600} />
              </TouchableOpacity>
            }
          />
        </View>
      </View>

      {/* Real-time Glycemic Context Feedback */}
      {liveStatus ? (
        <View
          style={[
            styles.liveStatusBanner,
            {
              backgroundColor: liveStatus.bgColor,
              borderColor: liveStatus.borderColor,
            },
          ]}
        >
          <Ionicons
            name={
              liveStatus.category === "target"
                ? "checkmark-circle"
                : liveStatus.category === "elevated"
                ? "trending-up"
                : liveStatus.category === "low"
                ? "alert-circle"
                : "warning"
            }
            size={16}
            color={liveStatus.color}
            style={{ marginRight: 6 }}
          />
          <View style={styles.liveStatusTextCol}>
            <Text
              style={[styles.liveStatusTitle, { color: liveStatus.color }]}
              allowFontScaling
            >
              {liveStatus.label}: {liveStatus.description}
            </Text>
          </View>
        </View>
      ) : null}

      {/* Context Selection Tags */}
      <View style={styles.tagSection}>
        <View style={styles.tagLabelRow}>
          <Ionicons name="time-outline" size={13} color={palette.muted} style={{ marginRight: 4 }} />
          <Text style={styles.tagGroupLabel} allowFontScaling>
            Measurement Context (Optional)
          </Text>
        </View>

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
      </View>

      {/* Action Row */}
      <View style={styles.actionRow}>
        <View style={styles.submitBtnWrapper}>
          <Button
            label={isSubmitting ? "Recording…" : "Record Reading"}
            variant="primary"
            onPress={handleSubmit}
            disabled={isSubmitting || !valueText.trim()}
            accessibilityHint="Submits this blood glucose observation to your clinical record"
          />
        </View>
        {valueText ? (
          <Button
            label="Clear"
            variant="ghost"
            onPress={clearForm}
            disabled={isSubmitting}
          />
        ) : null}
      </View>

      {/* Voice Dictation Modal */}
      <VoiceRecordModal
        visible={showVoiceModal}
        onClose={() => setShowVoiceModal(false)}
        title="Speak Glucose Reading"
        subtitle="Say your reading like 'Fasting 115' or 'Post lunch 140' in English or Hindi"
        placeholderHint="Fasting 110"
        onTranscribeSuccess={handleVoiceSuccess}
        testID="glucose-voice-modal"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: spacing.md + 2,
    backgroundColor: colors.surface,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: palette.border,
    gap: spacing.md,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.06,
    shadowRadius: 22,
    elevation: 3,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  headerIconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: palette.tealBg,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.sm,
  },
  headerTitles: {
    flex: 1,
  },
  sectionHeader: {
    fontSize: 16,
    fontWeight: "800",
    color: palette.ink,
    letterSpacing: -0.3,
  },
  sectionSubheader: {
    fontSize: 11,
    color: palette.muted,
    marginTop: 1,
  },
  voiceFeedbackBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: palette.tealBg,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: palette.tealBorder,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  voiceFeedbackText: {
    flex: 1,
    fontSize: 12,
    fontWeight: "600",
    color: palette.teal700,
    marginRight: 4,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  inputWrapper: {
    flex: 1,
  },
  micButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: palette.tealBg,
    borderWidth: 1,
    borderColor: palette.tealBorder,
    alignItems: "center",
    justifyContent: "center",
  },
  liveStatusBanner: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
  },
  liveStatusTextCol: {
    flex: 1,
  },
  liveStatusTitle: {
    fontSize: 12,
    fontWeight: "700",
    lineHeight: 16,
  },
  tagSection: {
    gap: spacing.sm,
  },
  tagLabelRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  tagGroupLabel: {
    fontSize: 13,
    fontWeight: "700",
    color: palette.body,
  },
  tagGroup: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  actionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingTop: spacing.xxs,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
  },
  submitBtnWrapper: {
    flex: 1,
  },
});