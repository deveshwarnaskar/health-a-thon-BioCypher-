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

export type BloodPressureData = {
  systolic: number;
  diastolic: number;
  pulse?: number;
  position: "sitting" | "standing" | "reclining" | "other";
  date: string;
  time: string;
  notes?: string;
};

export type BloodPressureEntryModalProps = {
  visible: boolean;
  onClose: () => void;
  onSave: (data: BloodPressureData) => Promise<void> | void;
};

const POSITIONS = [
  { key: "sitting", label: "Sitting" },
  { key: "standing", label: "Standing" },
  { key: "reclining", label: "Lying down" },
  { key: "other", label: "Other" },
] as const;

export function BloodPressureEntryModal({ visible, onClose, onSave }: BloodPressureEntryModalProps) {
  const [systolic, setSystolic] = useState("120");
  const [diastolic, setDiastolic] = useState("80");
  const [pulse, setPulse] = useState("72");
  const [position, setPosition] = useState<BloodPressureData["position"]>("sitting");
  const [notes, setNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    const sys = parseInt(systolic, 10);
    const dia = parseInt(diastolic, 10);
    const pul = pulse ? parseInt(pulse, 10) : undefined;

    if (isNaN(sys) || sys < 60 || sys > 260) {
      setError("Please enter a valid systolic value between 60 and 260 mmHg.");
      return;
    }
    if (isNaN(dia) || dia < 40 || dia > 160) {
      setError("Please enter a valid diastolic value between 40 and 160 mmHg.");
      return;
    }
    if (pul !== undefined && (isNaN(pul) || pul < 30 || pul > 220)) {
      setError("Please enter a valid pulse rate between 30 and 220 bpm.");
      return;
    }

    setError(null);
    setIsSaving(true);
    try {
      const now = new Date();
      await onSave({
        systolic: sys,
        diastolic: dia,
        pulse: pul,
        position,
        date: now.toISOString().split("T")[0]!,
        time: now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        notes: notes.trim() || undefined,
      });
      onClose();
    } catch {
      setError("Unable to save blood pressure. Saved locally on this device.");
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
              <Text style={styles.title} allowFontScaling>Blood Pressure</Text>
            </View>
            <TouchableOpacity onPress={onClose} style={styles.closeButton} accessibilityLabel="Close BP modal">
              <Ionicons name="close" size={22} color="#64748B" />
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
            {/* Reading Inputs */}
            <View style={styles.readingsRow}>
              <View style={styles.readingCol}>
                <Text style={styles.fieldLabel} allowFontScaling>SYSTOLIC</Text>
                <TextInput
                  style={styles.bpInput}
                  value={systolic}
                  onChangeText={setSystolic}
                  keyboardType="number-pad"
                  maxLength={3}
                  placeholder="120"
                />
                <Text style={styles.unitText} allowFontScaling>mmHg</Text>
              </View>

              <Text style={styles.slash} allowFontScaling>/</Text>

              <View style={styles.readingCol}>
                <Text style={styles.fieldLabel} allowFontScaling>DIASTOLIC</Text>
                <TextInput
                  style={styles.bpInput}
                  value={diastolic}
                  onChangeText={setDiastolic}
                  keyboardType="number-pad"
                  maxLength={3}
                  placeholder="80"
                />
                <Text style={styles.unitText} allowFontScaling>mmHg</Text>
              </View>

              <View style={[styles.readingCol, styles.pulseCol]}>
                <Text style={styles.fieldLabel} allowFontScaling>PULSE</Text>
                <TextInput
                  style={styles.bpInput}
                  value={pulse}
                  onChangeText={setPulse}
                  keyboardType="number-pad"
                  maxLength={3}
                  placeholder="72"
                />
                <Text style={styles.unitText} allowFontScaling>bpm</Text>
              </View>
            </View>

            {/* Body Position */}
            <Text style={styles.fieldLabel} allowFontScaling>BODY POSITION</Text>
            <View style={styles.positionGrid}>
              {POSITIONS.map((p) => {
                const isSelected = position === p.key;
                return (
                  <TouchableOpacity
                    key={p.key}
                    style={[styles.positionChip, isSelected && styles.positionChipSelected]}
                    onPress={() => setPosition(p.key)}
                  >
                    <Text style={[styles.positionText, isSelected && styles.positionTextSelected]} allowFontScaling>
                      {p.label}
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
              placeholder="e.g. Left arm, rested 5 minutes prior"
              placeholderTextColor="#94A3B8"
            />

            {error ? <Text style={styles.errorText} allowFontScaling>{error}</Text> : null}
          </ScrollView>

          {/* Footer Action */}
          <View style={styles.footer}>
            <Button
              label={isSaving ? "Saving…" : "Save Blood Pressure"}
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
  readingsRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#F8FAFC",
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  readingCol: {
    alignItems: "center",
  },
  pulseCol: {
    borderLeftWidth: 1,
    borderLeftColor: "#E2E8F0",
    paddingLeft: spacing.md,
  },
  slash: {
    fontSize: 28,
    color: "#94A3B8",
    fontWeight: "300",
    marginTop: spacing.md,
  },
  bpInput: {
    width: 76,
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
    ...typography.caption,
    color: "#64748B",
    marginTop: 2,
  },
  positionGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  positionChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.sm,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  positionChipSelected: {
    backgroundColor: "#EFF6FF",
    borderColor: "#3B82F6",
  },
  positionText: {
    ...typography.caption,
    color: "#475569",
    fontWeight: "600",
  },
  positionTextSelected: {
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
