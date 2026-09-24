import React, { useState } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Chip } from "../../components/primitives/Chip";
import { TextInput } from "../../components/primitives/TextInput";
import { colors, radii, spacing } from "../../theming/tokens";
import { COMMON_FOODS, type FoodItem } from "./types";
import { VoiceRecordModal } from "../../components/voice/VoiceRecordModal";
import { MealPhotoModal } from "../../components/camera/MealPhotoModal";
import type { AnalyzeMealPhotoAiResponse } from "../../services/schemas/ai";

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

export type FoodItemSelectorProps = {
  selectedFoodKey: string | null;
  onSelectFood: (food: FoodItem) => void;
  description: string;
  onChangeDescription: (text: string) => void;
  error?: string | null;
  testID?: string;
  patientName?: string;
  onPhotoAnalyzed?: (analysis: AnalyzeMealPhotoAiResponse, photoUri: string) => void;
  onDirectLog?: (analysis: AnalyzeMealPhotoAiResponse, photoUri: string) => Promise<void>;
};

export function FoodItemSelector({
  selectedFoodKey,
  onSelectFood,
  description,
  onChangeDescription,
  error,
  testID,
  patientName = "",
  onPhotoAnalyzed,
  onDirectLog,
}: FoodItemSelectorProps) {
  const [showVoiceModal, setShowVoiceModal] = useState(false);
  const [showPhotoModal, setShowPhotoModal] = useState(false);
  const [voiceFeedback, setVoiceFeedback] = useState<string | null>(null);
  const [photoFeedback, setPhotoFeedback] = useState<string | null>(null);

  const handleVoiceSuccess = (transcript: string) => {
    const clean = transcript.trim();
    if (!clean) return;

    onChangeDescription(clean);
    setVoiceFeedback(`Captured: "${clean}"`);

    // Auto-match food item from COMMON_FOODS if recognized without overwriting the spoken text
    const lower = clean.toLowerCase();
    const matched = COMMON_FOODS.find((f) => {
      const keyMatch = lower.includes(f.key.toLowerCase());
      const firstWord = f.label.toLowerCase().split(" ")[0] || "";
      const labelMatch = firstWord.length > 2 && lower.includes(firstWord);
      return keyMatch || labelMatch;
    });
    if (matched) {
      onSelectFood(matched);
      setTimeout(() => {
        onChangeDescription(clean);
      }, 0);
    }
  };

  const handlePhotoSuccess = (
    analysis: AnalyzeMealPhotoAiResponse,
    photoUri: string
  ) => {
    const clean = (analysis.description || "").trim();
    if (!clean) return;

    onChangeDescription(clean);
    setPhotoFeedback(
      `AI identified: "${clean}" (${analysis.total_calories_kcal} kcal)`
    );

    // Auto-match food item from COMMON_FOODS if recognized
    const lower = clean.toLowerCase();
    const matched = COMMON_FOODS.find((f) => {
      const keyMatch = lower.includes(f.key.toLowerCase());
      const firstWord = f.label.toLowerCase().split(" ")[0] || "";
      const labelMatch = firstWord.length > 2 && lower.includes(firstWord);
      return keyMatch || labelMatch;
    });
    if (matched) {
      onSelectFood(matched);
      setTimeout(() => {
        onChangeDescription(clean);
      }, 0);
    }

    onPhotoAnalyzed?.(analysis, photoUri);
  };

  return (
    <View style={styles.container} testID={testID}>
      {/* Header Row */}
      <View style={styles.headerRow}>
        <View style={styles.headerIconCircle}>
          <Ionicons name="restaurant" size={17} color={palette.teal600} />
        </View>
        <View style={styles.titleCol}>
          <Text style={styles.sectionTitle} allowFontScaling>
            Food Items
          </Text>
          <Text style={styles.caption} allowFontScaling>
            Select standard foods or enter your meal description below:
          </Text>
        </View>
      </View>

      {/* Voice Transcript Feedback */}
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

      {/* Photo AI Analysis Feedback */}
      {photoFeedback ? (
        <View style={styles.photoFeedbackBanner}>
          <Ionicons name="camera" size={14} color={palette.teal600} style={{ marginRight: 6 }} />
          <Text style={styles.voiceFeedbackText} allowFontScaling numberOfLines={2}>
            {photoFeedback}
          </Text>
          <TouchableOpacity
            onPress={() => setPhotoFeedback(null)}
            accessibilityRole="button"
            accessibilityLabel="Dismiss photo message"
          >
            <Ionicons name="close" size={14} color={palette.muted} />
          </TouchableOpacity>
        </View>
      ) : null}

      <View style={styles.chipGrid}>
        {COMMON_FOODS.map((food) => {
          const isSelected = selectedFoodKey === food.key;
          return (
            <Chip
              key={food.key}
              label={food.label}
              selected={isSelected}
              onPress={() => onSelectFood(food)}
              accessibilityHint={`Selects ${food.label} as your meal`}
            />
          );
        })}
      </View>

      <TextInput
        label="Meal Description *"
        value={description}
        onChangeText={onChangeDescription}
        error={error}
        hint="Describe what you are eating (e.g. 1 katori dal with rice)"
        accessibilityHint="Enter description of your meal"
        trailing={
          <View style={styles.trailingActionGroup}>
            <TouchableOpacity
              style={styles.actionIconBtn}
              onPress={() => setShowPhotoModal(true)}
              accessibilityRole="button"
              accessibilityLabel="Scan meal photo with camera"
              activeOpacity={0.7}
            >
              <Ionicons name="camera" size={20} color={palette.teal600} />
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.actionIconBtn}
              onPress={() => setShowVoiceModal(true)}
              accessibilityRole="button"
              accessibilityLabel="Speak meal description"
              activeOpacity={0.7}
            >
              <Ionicons name="mic" size={20} color={palette.teal600} />
            </TouchableOpacity>
          </View>
        }
      />

      {/* Voice Record Modal */}
      <VoiceRecordModal
        visible={showVoiceModal}
        onClose={() => setShowVoiceModal(false)}
        title="Describe Your Meal"
        subtitle="Speak your meal in English, Hindi, or Hinglish (e.g. '2 roti with dal and curd')"
        placeholderHint="2 roti with 1 bowl dal"
        onTranscribeSuccess={handleVoiceSuccess}
        testID="meal-voice-modal"
      />

      {/* Camera Photo Modal */}
      <MealPhotoModal
        visible={showPhotoModal}
        onClose={() => setShowPhotoModal(false)}
        patientName={patientName}
        onPhotoAnalyzed={handlePhotoSuccess}
        onDirectLog={onDirectLog}
        testID="meal-photo-modal"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.sm,
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
  titleCol: {
    flex: 1,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: palette.ink,
    letterSpacing: -0.3,
  },
  caption: {
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
  chipGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  trailingActionGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  actionIconBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: palette.tealBg,
    borderWidth: 1,
    borderColor: palette.tealBorder,
    alignItems: "center",
    justifyContent: "center",
  },
  photoFeedbackBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F0FDFA",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#99F6E4",
    paddingHorizontal: 12,
    paddingVertical: 8,
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
});