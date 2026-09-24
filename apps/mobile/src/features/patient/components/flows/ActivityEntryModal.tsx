import React, { useState } from "react";
import {
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../../theming/tokens";
import { Button } from "../../../../components/primitives/Button";

export type ActivityType = "walking" | "running" | "cycling" | "gym" | "yoga" | "other";
export type ActivityIntensity = "light" | "moderate" | "vigorous";

export type ActivityEntryData = {
  type: ActivityType;
  durationMinutes: number;
  intensity: ActivityIntensity;
  date: string;
  time: string;
  notes?: string;
};

export type ActivityEntryModalProps = {
  visible: boolean;
  onClose: () => void;
  onSave: (data: ActivityEntryData) => Promise<void> | void;
};

const ACTIVITY_TYPES: { key: ActivityType; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: "walking", label: "Walking", icon: "walk-outline" },
  { key: "running", label: "Running", icon: "fitness-outline" },
  { key: "cycling", label: "Cycling", icon: "bicycle-outline" },
  { key: "gym", label: "Gym / Strength", icon: "barbell-outline" },
  { key: "yoga", label: "Yoga / Stretch", icon: "body-outline" },
  { key: "other", label: "Other", icon: "pulse-outline" },
];

const INTENSITIES: { key: ActivityIntensity; label: string; subtext: string }[] = [
  { key: "light", label: "Light", subtext: "Easy pace, normal breathing" },
  { key: "moderate", label: "Moderate", subtext: "Can talk, but not sing" },
  { key: "vigorous", label: "Vigorous", subtext: "Fast breathing, elevated heart rate" },
];

export function ActivityEntryModal({ visible, onClose, onSave }: ActivityEntryModalProps) {
  const [selectedType, setSelectedType] = useState<ActivityType>("walking");
  const [duration, setDuration] = useState("30");
  const [selectedIntensity, setSelectedIntensity] = useState<ActivityIntensity>("moderate");
  const [notes, setNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    const mins = parseInt(duration, 10);
    if (isNaN(mins) || mins <= 0 || mins > 720) {
      setError("Please enter a valid duration between 1 and 720 minutes.");
      return;
    }
    setError(null);
    setIsSaving(true);
    try {
      const now = new Date();
      await onSave({
        type: selectedType,
        durationMinutes: mins,
        intensity: selectedIntensity,
        date: now.toISOString().split("T")[0]!,
        time: now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        notes: notes.trim() || undefined,
      });
      onClose();
    } catch (e) {
      setError("Unable to save activity. Your entry is preserved on this device.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.container}>
          {/* Header */}
          <View style={styles.headerRow}>
            <View>
              <Text style={styles.kicker} allowFontScaling>RECORD EVENT</Text>
              <Text style={styles.title} allowFontScaling>Physical Activity</Text>
            </View>
            <TouchableOpacity onPress={onClose} style={styles.closeButton} accessibilityLabel="Close activity modal">
              <Ionicons name="close" size={22} color="#64748B" />
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
            {/* Activity Type Selector */}
            <Text style={styles.fieldLabel} allowFontScaling>ACTIVITY TYPE</Text>
            <View style={styles.typeGrid}>
              {ACTIVITY_TYPES.map((t) => {
                const isSelected = selectedType === t.key;
                return (
                  <TouchableOpacity
                    key={t.key}
                    style={[styles.typeChip, isSelected && styles.typeChipSelected]}
                    onPress={() => setSelectedType(t.key)}
                    accessibilityRole="button"
                    accessibilityState={{ selected: isSelected }}
                  >
                    <Ionicons name={t.icon} size={18} color={isSelected ? "#0284C7" : "#64748B"} />
                    <Text style={[styles.typeLabel, isSelected && styles.typeLabelSelected]} allowFontScaling>
                      {t.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Duration Input */}
            <Text style={styles.fieldLabel} allowFontScaling>DURATION (MINUTES)</Text>
            <View style={styles.inputRow}>
              <TextInput
                style={styles.numericInput}
                value={duration}
                onChangeText={setDuration}
                keyboardType="number-pad"
                maxLength={3}
                placeholder="30"
                placeholderTextColor="#94A3B8"
              />
              <Text style={styles.unitText} allowFontScaling>minutes</Text>
            </View>

            {/* Quick Duration Chips */}
            <View style={styles.durationQuickRow}>
              {["15", "30", "45", "60"].map((mins) => (
                <TouchableOpacity
                  key={mins}
                  style={[styles.quickChip, duration === mins && styles.quickChipSelected]}
                  onPress={() => setDuration(mins)}
                >
                  <Text style={[styles.quickChipText, duration === mins && styles.quickChipTextSelected]} allowFontScaling>
                    {mins}m
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Intensity Selector */}
            <Text style={styles.fieldLabel} allowFontScaling>INTENSITY</Text>
            <View style={styles.intensityColumn}>
              {INTENSITIES.map((i) => {
                const isSelected = selectedIntensity === i.key;
                return (
                  <TouchableOpacity
                    key={i.key}
                    style={[styles.intensityCard, isSelected && styles.intensityCardSelected]}
                    onPress={() => setSelectedIntensity(i.key)}
                    accessibilityRole="button"
                    accessibilityState={{ selected: isSelected }}
                  >
                    <View style={styles.intensityHeader}>
                      <Text style={[styles.intensityTitle, isSelected && styles.intensityTitleSelected]} allowFontScaling>
                        {i.label}
                      </Text>
                      <Ionicons
                        name={isSelected ? "radio-button-on" : "radio-button-off"}
                        size={18}
                        color={isSelected ? "#0284C7" : "#CBD5E1"}
                      />
                    </View>
                    <Text style={styles.intensitySubtext} allowFontScaling>{i.subtext}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Optional Notes */}
            <Text style={styles.fieldLabel} allowFontScaling>NOTES (OPTIONAL)</Text>
            <TextInput
              style={styles.notesInput}
              value={notes}
              onChangeText={setNotes}
              placeholder="e.g. Post-lunch brisk walk in the park"
              placeholderTextColor="#94A3B8"
              multiline
              numberOfLines={2}
            />

            {error ? <Text style={styles.errorText} allowFontScaling>{error}</Text> : null}
          </ScrollView>

          {/* Footer Action */}
          <View style={styles.footer}>
            <Button
              label={isSaving ? "Saving…" : "Save Activity"}
              variant="primary"
              onPress={handleSave}
              disabled={isSaving}
            />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.6)",
    justifyContent: "flex-end",
  },
  container: {
    backgroundColor: colors.background,
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
    maxHeight: "85%",
    paddingBottom: spacing.xl,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F9",
  },
  kicker: {
    ...typography.caption,
    color: "#64748B",
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  title: {
    ...typography.titleLarge,
    color: colors.textPrimary,
    fontWeight: "800",
  },
  closeButton: {
    width: touchTarget.min,
    height: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
  },
  body: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
  },
  fieldLabel: {
    ...typography.caption,
    color: "#475569",
    fontWeight: "700",
    marginTop: spacing.md,
    marginBottom: spacing.xs,
    letterSpacing: 0.5,
  },
  typeGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  typeChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.md,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  typeChipSelected: {
    backgroundColor: "#F0F9FF",
    borderColor: "#0284C7",
  },
  typeLabel: {
    ...typography.bodyMedium,
    color: "#475569",
    fontWeight: "600",
  },
  typeLabelSelected: {
    color: "#0284C7",
    fontWeight: "700",
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  numericInput: {
    width: 100,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: 22,
    fontWeight: "800",
    color: colors.textPrimary,
  },
  unitText: {
    ...typography.bodyMedium,
    color: "#64748B",
  },
  durationQuickRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  quickChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radii.sm,
    backgroundColor: "#F1F5F9",
  },
  quickChipSelected: {
    backgroundColor: "#E0F2FE",
  },
  quickChipText: {
    ...typography.caption,
    color: "#64748B",
    fontWeight: "600",
  },
  quickChipTextSelected: {
    color: "#0284C7",
    fontWeight: "700",
  },
  intensityColumn: {
    gap: spacing.xs,
  },
  intensityCard: {
    padding: spacing.md,
    borderRadius: radii.md,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  intensityCardSelected: {
    backgroundColor: "#F0F9FF",
    borderColor: "#0284C7",
  },
  intensityHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  intensityTitle: {
    ...typography.bodyMedium,
    fontWeight: "700",
    color: "#334155",
  },
  intensityTitleSelected: {
    color: "#0284C7",
  },
  intensitySubtext: {
    ...typography.caption,
    color: "#64748B",
    marginTop: 2,
  },
  notesInput: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: radii.md,
    padding: spacing.md,
    ...typography.bodyMedium,
    color: colors.textPrimary,
  },
  errorText: {
    ...typography.caption,
    color: colors.error,
    marginTop: spacing.sm,
  },
  footer: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
  },
});
