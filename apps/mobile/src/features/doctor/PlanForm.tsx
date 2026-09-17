import React, { useState } from "react";
import { StyleSheet, View } from "react-native";
import { Button } from "../../components/primitives/Button";
import { TextInput } from "../../components/primitives/TextInput";
import { spacing } from "../../theming/tokens";
import type { CreateMedicationPlanRequest } from "../../services/schemas/medication";

export type PlanFormProps = {
  patientId: string;
  isSubmitting?: boolean;
  /**
   * Field-level problems surfaced from the backend 422 body, keyed by field
   * name (medication / instruction). Only sanitized client-side copies render.
   */
  backendFieldErrors?: Record<string, string[]>;
  onSubmit: (request: CreateMedicationPlanRequest) => void;
  testID?: string;
};

/**
 * Clinician-authored medication-plan form (Gate 10F-M). Collects medication +
 * optional instruction; the patient scope comes from the selected patient and
 * the prescriber is ALWAYS backend-derived from the authenticated context —
 * no prescriber/actor/facility field is ever sent.
 */
export function PlanForm({
  patientId,
  isSubmitting = false,
  backendFieldErrors,
  onSubmit,
  testID,
}: PlanFormProps) {
  const [medication, setMedication] = useState("");
  const [instruction, setInstruction] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const serverMedicationError = backendFieldErrors?.medication?.[0];
  const serverInstructionError = backendFieldErrors?.instruction?.[0];

  const handleSubmit = () => {
    if (medication.trim().length === 0) {
      setLocalError("Medication name is required.");
      return;
    }
    setLocalError(null);
    onSubmit({
      patient_id: patientId,
      medication: medication.trim(),
      instruction: instruction.trim().length > 0 ? instruction.trim() : "",
    });
  };

  return (
    <View style={styles.container} testID={testID}>
      <TextInput
        label="Medication"
        value={medication}
        onChangeText={setMedication}
        error={localError ?? serverMedicationError ?? null}
        hint="Required. Name of the medication being prescribed."
        accessibilityHint="Enter the medication name."
        autoCapitalize="sentences"
      />
      <TextInput
        label="Instruction"
        value={instruction}
        onChangeText={setInstruction}
        error={serverInstructionError ?? null}
        hint="Optional. How and when to take the medication."
        accessibilityHint="Enter any dosage or timing instructions."
      />
      <Button
        label={isSubmitting ? "Submitting plan…" : "Create plan"}
        variant="primary"
        busy={isSubmitting}
        disabled={isSubmitting}
        onPress={handleSubmit}
        accessibilityHint="Creates the medication plan for this patient. Nothing is recorded until the backend confirms."
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.md,
  },
});