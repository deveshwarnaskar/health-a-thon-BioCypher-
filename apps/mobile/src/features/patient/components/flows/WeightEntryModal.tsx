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

export type WeightEntryData = {
  weight: number;
  unit: "kg" | "lbs";
  context?: string;
  date: string;
  time: string;
  notes?: string;
};

export type WeightEntryModalProps = {
  visible: boolean;
  onClose: () => void;
  onSave: (data: WeightEntryData) => Promise<void> | void;
};

const CONTEXT_OPTIONS = [
  "Morning (fasting)",
  "Post-workout",
  "Before dinner",
  "Bedtime",
  "Routine check",
];

export function WeightEntryModal({ visible, onClose, onSave }: WeightEntryModalProps) {
  const [weight, setWeight] = useState("70.5");
  const [unit, setUnit] = useState<"kg" | "lbs">("kg");
  const [selectedContext, setSelectedContext] = useState<string>("Morning (fasting)");
  const [notes, setNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    const val = parseFloat(weight);
    if (isNaN(val) || val < 20 || val > 400) {
      setError("Please enter a plausible weight value between 20 and 400.");
      return;
    }
    setError(null);
    setIsSaving(true);
    try {
      const now = new Date();
      await onSave({
        weight: val,
        unit,
        context: selectedContext,
        date: now.toISOString().split("T")[0]!,
        time: now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        notes: notes.trim() || undefined,
      });
      onClose();
    } catch {
      setError("Unable to save weight. Entry preserved on this device.");
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
              <Text style={styles.title} allowFontScaling>Body Weight</Text>
            </View>
            <TouchableOpacity onPress={onClose} style={styles.closeButton} accessibilityLabel="Close weight modal">
              <Ionicons name="close" size={22} color="#64748B" />
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
            {/* Non-mandatory Guidance Card */}
            <View style={styles.guidanceCard}>
              <Ionicons name="information-circle-outline" size={18} color="#0284C7" />
              <Text style={styles.guidanceText} allowFontScaling>
                Logging weight is optional. Recording once a week or as advised by your care team is typically sufficient.
              </Text>
            </View>

            {/* Weight Input with Unit Toggle */}
            <Text style={styles.fieldLabel} allowFontScaling>MEASURED WEIGHT</Text>
            <View style={styles.inputRow}>
              <TextInput
                style={styles.numericInput}
                value={weight}
                onChangeText={setWeight}
                keyboardType="decimal-pad"
                maxLength={6}
                placeholder="70.0"
                placeholderTextColor="#94A3B8"
              />
              <View style={styles.unitToggle}>
                <TouchableOpacity
                  style={[styles.unitButton, unit === "kg" && styles.unitButtonActive]}
                  onPress={() => setUnit("kg")}
                >
                  <Text style={[styles.unitText, unit === "kg" && styles.unitTextActive]} allowFontScaling>
                    kg
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.unitButton, unit === "lbs" && styles.unitButtonActive]}
                  onPress={() => setUnit("lbs")}
                >
                  <Text style={[styles.unitText, unit === "lbs" && styles.unitTextActive]} allowFontScaling>
                    lbs
                  </Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* Context Selector */}
            <Text style={styles.fieldLabel} allowFontScaling>CONTEXT</Text>
            <View style={styles.contextGrid}>
              {CONTEXT_OPTIONS.map((c) => {
                const isSelected = selectedContext === c;
                return (
                  <TouchableOpacity
                    key={c}
                    style={[styles.contextChip, isSelected && styles.contextChipSelected]}
                    onPress={() => setSelectedContext(c)}
                  >
                    <Text style={[styles.contextText, isSelected && styles.contextTextSelected]} allowFontScaling>
                      {c}
                    </Text>
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
              placeholder="e.g. Using home digital scale"
              placeholderTextColor="#94A3B8"
            />

            {error ? <Text style={styles.errorText} allowFontScaling>{error}</Text> : null}
          </ScrollView>

          {/* Footer Action */}
          <View style={styles.footer}>
            <Button
              label={isSaving ? "Saving…" : "Save Weight"}
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
  guidanceCard: {
    flexDirection: "row",
    gap: spacing.sm,
    backgroundColor: "#F0F9FF",
    borderRadius: radii.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#BAE6FD",
    alignItems: "flex-start",
  },
  guidanceText: {
    ...typography.caption,
    color: "#0369A1",
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
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  numericInput: {
    width: 120,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: 26,
    fontWeight: "800",
    color: colors.textPrimary,
  },
  unitToggle: {
    flexDirection: "row",
    backgroundColor: "#F1F5F9",
    borderRadius: radii.md,
    padding: 3,
  },
  unitButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.sm,
  },
  unitButtonActive: {
    backgroundColor: colors.surface,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  unitText: {
    ...typography.bodyMedium,
    color: "#64748B",
    fontWeight: "600",
  },
  unitTextActive: {
    color: colors.textPrimary,
    fontWeight: "700",
  },
  contextGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  contextChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.sm,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  contextChipSelected: {
    backgroundColor: "#EFF6FF",
    borderColor: "#3B82F6",
  },
  contextText: {
    ...typography.caption,
    color: "#475569",
    fontWeight: "600",
  },
  contextTextSelected: {
    color: "#2563EB",
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
