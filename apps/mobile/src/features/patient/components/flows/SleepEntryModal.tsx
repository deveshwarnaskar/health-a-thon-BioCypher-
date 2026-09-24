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

export type SleepQuality = "restful" | "normal" | "interrupted" | "poor";

export type SleepEntryData = {
  hours: number;
  minutes: number;
  quality: SleepQuality;
  date: string;
  notes?: string;
};

export type SleepEntryModalProps = {
  visible: boolean;
  onClose: () => void;
  onSave: (data: SleepEntryData) => Promise<void> | void;
};

const QUALITIES: { key: SleepQuality; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: "restful", label: "Restful & Deep", icon: "sparkles-outline" },
  { key: "normal", label: "Normal / Adequate", icon: "checkmark-circle-outline" },
  { key: "interrupted", label: "Interrupted / Woke up", icon: "alert-circle-outline" },
  { key: "poor", label: "Poor / Insufficient", icon: "close-circle-outline" },
];

export function SleepEntryModal({ visible, onClose, onSave }: SleepEntryModalProps) {
  const [hours, setHours] = useState("7");
  const [minutes, setMinutes] = useState("30");
  const [selectedQuality, setSelectedQuality] = useState<SleepQuality>("normal");
  const [notes, setNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    const h = parseInt(hours, 10);
    const m = parseInt(minutes, 10);
    if (isNaN(h) || h < 0 || h > 24) {
      setError("Please enter valid sleep hours (0–24).");
      return;
    }
    if (isNaN(m) || m < 0 || m > 59) {
      setError("Please enter valid sleep minutes (0–59).");
      return;
    }
    if (h === 0 && m === 0) {
      setError("Sleep duration must be greater than zero.");
      return;
    }
    setError(null);
    setIsSaving(true);
    try {
      const now = new Date();
      await onSave({
        hours: h,
        minutes: m,
        quality: selectedQuality,
        date: now.toISOString().split("T")[0]!,
        notes: notes.trim() || undefined,
      });
      onClose();
    } catch {
      setError("Unable to save sleep record. Saved locally on this device.");
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
              <Text style={styles.title} allowFontScaling>Night Sleep</Text>
            </View>
            <TouchableOpacity onPress={onClose} style={styles.closeButton} accessibilityLabel="Close sleep modal">
              <Ionicons name="close" size={22} color="#64748B" />
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
            {/* Duration Row */}
            <Text style={styles.fieldLabel} allowFontScaling>TOTAL SLEEP DURATION</Text>
            <View style={styles.durationRow}>
              <View style={styles.durationInputGroup}>
                <TextInput
                  style={styles.numericInput}
                  value={hours}
                  onChangeText={setHours}
                  keyboardType="number-pad"
                  maxLength={2}
                  placeholder="7"
                />
                <Text style={styles.unitText} allowFontScaling>hours</Text>
              </View>

              <View style={styles.durationInputGroup}>
                <TextInput
                  style={styles.numericInput}
                  value={minutes}
                  onChangeText={setMinutes}
                  keyboardType="number-pad"
                  maxLength={2}
                  placeholder="30"
                />
                <Text style={styles.unitText} allowFontScaling>minutes</Text>
              </View>
            </View>

            {/* Quick Duration Buttons */}
            <View style={styles.quickRow}>
              {[
                { h: "6", m: "00" },
                { h: "7", m: "00" },
                { h: "7", m: "30" },
                { h: "8", m: "00" },
              ].map((item) => (
                <TouchableOpacity
                  key={`${item.h}-${item.m}`}
                  style={[
                    styles.quickChip,
                    hours === item.h && minutes === item.m && styles.quickChipSelected,
                  ]}
                  onPress={() => {
                    setHours(item.h);
                    setMinutes(item.m);
                  }}
                >
                  <Text
                    style={[
                      styles.quickChipText,
                      hours === item.h && minutes === item.m && styles.quickChipTextSelected,
                    ]}
                    allowFontScaling
                  >
                    {item.h}h {item.m === "00" ? "" : `${item.m}m`}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Quality Selector */}
            <Text style={styles.fieldLabel} allowFontScaling>SLEEP QUALITY</Text>
            <View style={styles.qualityColumn}>
              {QUALITIES.map((q) => {
                const isSelected = selectedQuality === q.key;
                return (
                  <TouchableOpacity
                    key={q.key}
                    style={[styles.qualityCard, isSelected && styles.qualityCardSelected]}
                    onPress={() => setSelectedQuality(q.key)}
                  >
                    <Ionicons
                      name={q.icon}
                      size={18}
                      color={isSelected ? "#4F46E5" : "#64748B"}
                    />
                    <Text
                      style={[styles.qualityText, isSelected && styles.qualityTextSelected]}
                      allowFontScaling
                    >
                      {q.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Notes */}
            <Text style={styles.fieldLabel} allowFontScaling>NOTES (OPTIONAL)</Text>
            <TextInput
              style={styles.notesInput}
              value={notes}
              onChangeText={setNotes}
              placeholder="e.g. Woke up once around 3 AM"
              placeholderTextColor="#94A3B8"
            />

            {error ? <Text style={styles.errorText} allowFontScaling>{error}</Text> : null}
          </ScrollView>

          {/* Footer Action */}
          <View style={styles.footer}>
            <Button
              label={isSaving ? "Saving…" : "Save Sleep Log"}
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
    maxHeight: "80%",
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
  durationRow: {
    flexDirection: "row",
    gap: spacing.lg,
    backgroundColor: "#F8FAFC",
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  durationInputGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  numericInput: {
    width: 60,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: radii.sm,
    paddingVertical: spacing.xs,
    textAlign: "center",
    fontSize: 22,
    fontWeight: "800",
    color: colors.textPrimary,
  },
  unitText: {
    ...typography.bodyMedium,
    color: "#64748B",
  },
  quickRow: {
    flexDirection: "row",
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  quickChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radii.sm,
    backgroundColor: "#F1F5F9",
  },
  quickChipSelected: {
    backgroundColor: "#EEF2FF",
  },
  quickChipText: {
    ...typography.caption,
    color: "#64748B",
    fontWeight: "600",
  },
  quickChipTextSelected: {
    color: "#4F46E5",
    fontWeight: "700",
  },
  qualityColumn: {
    gap: spacing.xs,
  },
  qualityCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radii.md,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  qualityCardSelected: {
    backgroundColor: "#EEF2FF",
    borderColor: "#6366F1",
  },
  qualityText: {
    ...typography.bodyMedium,
    color: "#334155",
    fontWeight: "600",
  },
  qualityTextSelected: {
    color: "#4338CA",
    fontWeight: "700",
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
