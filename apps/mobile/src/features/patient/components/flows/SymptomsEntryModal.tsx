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

export type SymptomItem = {
  key: string;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
};

export type SymptomEntryData = {
  selectedSymptoms: string[];
  nearbyGlucose?: number;
  date: string;
  time: string;
  notes?: string;
};

export type SymptomsEntryModalProps = {
  visible: boolean;
  onClose: () => void;
  onSave: (data: SymptomEntryData) => Promise<void> | void;
  suggestedGlucose?: number;
};

const SYMPTOMS: SymptomItem[] = [
  { key: "shaky", label: "Shaky / Trembling", icon: "pulse-outline" },
  { key: "sweating", label: "Excessive Sweating", icon: "water-outline" },
  { key: "dizziness", label: "Dizziness / Lightheaded", icon: "sync-outline" },
  { key: "weakness", label: "Sudden Weakness / Fatigue", icon: "body-outline" },
  { key: "headache", label: "Headache", icon: "alert-circle-outline" },
  { key: "nausea", label: "Nausea", icon: "bandage-outline" },
  { key: "thirsty", label: "Unusually Thirsty", icon: "cafe-outline" },
  { key: "frequent_urination", label: "Frequent Urination", icon: "time-outline" },
  { key: "other", label: "Other Unusual Feeling", icon: "help-circle-outline" },
];

export function SymptomsEntryModal({
  visible,
  onClose,
  onSave,
  suggestedGlucose,
}: SymptomsEntryModalProps) {
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [nearbyGlucose, setNearbyGlucose] = useState(suggestedGlucose ? String(suggestedGlucose) : "");
  const [notes, setNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleSymptom = (key: string) => {
    setSelectedKeys((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  const handleSave = async () => {
    if (selectedKeys.length === 0) {
      setError("Please select at least one observation.");
      return;
    }
    setError(null);
    setIsSaving(true);
    try {
      const now = new Date();
      const gNum = nearbyGlucose ? parseInt(nearbyGlucose, 10) : undefined;
      await onSave({
        selectedSymptoms: selectedKeys,
        nearbyGlucose: !isNaN(gNum as number) ? gNum : undefined,
        date: now.toISOString().split("T")[0]!,
        time: now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        notes: notes.trim() || undefined,
      });
      onClose();
    } catch {
      setError("Unable to save event. Saved locally on this device.");
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
              <Text style={styles.kicker} allowFontScaling>PATIENT OBSERVATION</Text>
              <Text style={styles.title} allowFontScaling>Symptoms / Events</Text>
            </View>
            <TouchableOpacity onPress={onClose} style={styles.closeButton} accessibilityLabel="Close symptoms modal">
              <Ionicons name="close" size={22} color="#64748B" />
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
            {/* Safety framing card */}
            <View style={styles.framingCard}>
              <Ionicons name="shield-checkmark-outline" size={18} color="#D97706" />
              <Text style={styles.framingText} allowFontScaling>
                This log captures patient-reported observations to share with your doctor. If you feel severely unwell, seek immediate clinical care.
              </Text>
            </View>

            <Text style={styles.fieldLabel} allowFontScaling>WHAT DID YOU NOTICE?</Text>
            <View style={styles.symptomsGrid}>
              {SYMPTOMS.map((s) => {
                const isSelected = selectedKeys.includes(s.key);
                return (
                  <TouchableOpacity
                    key={s.key}
                    style={[styles.symptomChip, isSelected && styles.symptomChipSelected]}
                    onPress={() => toggleSymptom(s.key)}
                    accessibilityRole="checkbox"
                    accessibilityState={{ checked: isSelected }}
                  >
                    <Ionicons
                      name={s.icon}
                      size={16}
                      color={isSelected ? "#B45309" : "#64748B"}
                    />
                    <Text
                      style={[styles.symptomText, isSelected && styles.symptomTextSelected]}
                      allowFontScaling
                    >
                      {s.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Associated Glucose Reading */}
            <Text style={styles.fieldLabel} allowFontScaling>NEARBY GLUCOSE READING (OPTIONAL)</Text>
            <View style={styles.glucoseRow}>
              <TextInput
                style={styles.glucoseInput}
                value={nearbyGlucose}
                onChangeText={setNearbyGlucose}
                keyboardType="number-pad"
                placeholder="e.g. 68"
                placeholderTextColor="#94A3B8"
              />
              <Text style={styles.unitText} allowFontScaling>mg/dL</Text>
            </View>

            {/* Optional Notes */}
            <Text style={styles.fieldLabel} allowFontScaling>ADDITIONAL CONTEXT (OPTIONAL)</Text>
            <TextInput
              style={styles.notesInput}
              value={notes}
              onChangeText={setNotes}
              placeholder="e.g. Felt shaky after 2 hours of skipped lunch"
              placeholderTextColor="#94A3B8"
              multiline
              numberOfLines={2}
            />

            {error ? <Text style={styles.errorText} allowFontScaling>{error}</Text> : null}
          </ScrollView>

          {/* Footer Action */}
          <View style={styles.footer}>
            <Button
              label={isSaving ? "Saving…" : "Save Observation"}
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
  framingCard: {
    flexDirection: "row",
    gap: spacing.sm,
    backgroundColor: "#FFFBEB",
    borderRadius: radii.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#FDE68A",
    alignItems: "flex-start",
  },
  framingText: {
    ...typography.caption,
    color: "#92400E",
    flex: 1,
    lineHeight: 18,
  },
  fieldLabel: {
    ...typography.caption,
    color: "#475569",
    fontWeight: "700",
    marginTop: spacing.md,
    marginBottom: spacing.xs,
    letterSpacing: 0.5,
  },
  symptomsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  symptomChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.md,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  symptomChipSelected: {
    backgroundColor: "#FEF3C7",
    borderColor: "#F59E0B",
  },
  symptomText: {
    ...typography.caption,
    color: "#475569",
    fontWeight: "600",
  },
  symptomTextSelected: {
    color: "#92400E",
    fontWeight: "700",
  },
  glucoseRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  glucoseInput: {
    width: 100,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    fontSize: 20,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  unitText: {
    ...typography.bodyMedium,
    color: "#64748B",
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
