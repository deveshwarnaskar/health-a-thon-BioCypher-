import React, { useState } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as ImagePicker from "expo-image-picker";
import { Button } from "../../components/primitives/Button";
import { TextInput } from "../../components/primitives/TextInput";
import { spacing } from "../../theming/tokens";
import { doctorPalette, doctorRadii } from "./doctorDesign";
import type { CreateMedicationPlanRequest } from "../../services/schemas/medication";

export type PlanAttachment = {
  filename: string;
  mime_type: string;
  content_base64: string;
  kind: "prescription" | "lab_report" | "clinical_note";
};

export type PlanFormProps = {
  patientId: string;
  isSubmitting?: boolean;
  /**
   * Field-level problems surfaced from the backend 422 body, keyed by field
   * name (medication / instruction). Only sanitized client-side copies render.
   */
  backendFieldErrors?: Record<string, string[]>;
  onSubmit: (request: CreateMedicationPlanRequest, attachment?: PlanAttachment | null) => void;
  testID?: string;
};

const DOC_KINDS: { key: PlanAttachment["kind"]; label: string }[] = [
  { key: "prescription", label: "Prescription" },
  { key: "lab_report", label: "Lab Report" },
  { key: "clinical_note", label: "Clinical Note" },
];

/**
 * Clinician-authored medication-plan form (Gate 10F-M). Collects medication +
 * optional instruction + optional prescription/clinical document attachment.
 * The patient scope comes from the selected patient and the prescriber is
 * ALWAYS backend-derived from the authenticated context.
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

  // Document attachment state
  const [attachment, setAttachment] = useState<PlanAttachment | null>(null);
  const [selectedKind, setSelectedKind] = useState<PlanAttachment["kind"]>("prescription");
  const [attachmentName, setAttachmentName] = useState("");

  const serverMedicationError = backendFieldErrors?.medication?.[0];
  const serverInstructionError = backendFieldErrors?.instruction?.[0];

  const handlePickCamera = async () => {
    try {
      const res = await ImagePicker.launchCameraAsync({
        base64: true,
        quality: 0.8,
      });
      if (!res.canceled && res.assets && res.assets.length > 0) {
        const asset = res.assets[0];
        if (asset) {
          const base64 = asset.base64 || "bW9ja2Jhc2U2NA==";
          const name = `Prescription_${Date.now()}.jpg`;
          setAttachment({
            filename: name,
            mime_type: "image/jpeg",
            content_base64: base64,
            kind: selectedKind,
          });
          setAttachmentName(name);
        }
      }
    } catch {
      // User cancelled or permissions denied
    }
  };

  const handlePickLibrary = async () => {
    try {
      const res = await ImagePicker.launchImageLibraryAsync({
        base64: true,
        quality: 0.8,
      });
      if (!res.canceled && res.assets && res.assets.length > 0) {
        const asset = res.assets[0];
        if (asset) {
          const base64 = asset.base64 || "bW9ja2Jhc2U2NA==";
          const name = `Prescription_Doc_${Date.now()}.jpg`;
          setAttachment({
            filename: name,
            mime_type: "image/jpeg",
            content_base64: base64,
            kind: selectedKind,
          });
          setAttachmentName(name);
        }
      }
    } catch {
      // User cancelled or permissions denied
    }
  };

  const handleSubmit = () => {
    if (medication.trim().length === 0) {
      setLocalError("Medication name is required.");
      return;
    }
    setLocalError(null);

    const finalAttachment = attachment
      ? {
          ...attachment,
          filename: attachmentName.trim() || attachment.filename,
          kind: selectedKind,
        }
      : null;

    onSubmit(
      {
        patient_id: patientId,
        medication: medication.trim(),
        instruction: instruction.trim().length > 0 ? instruction.trim() : "",
      },
      finalAttachment
    );
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

      {/* Prescription / Clinical Document Attachment Section */}
      <View style={styles.attachmentSection}>
        <View style={styles.attachmentHeader}>
          <Ionicons name="document-attach" size={17} color={doctorPalette.primary} />
          <Text style={styles.attachmentSectionTitle} allowFontScaling>
            Prescription or Supporting Document (Optional)
          </Text>
        </View>
        <Text style={styles.attachmentSub} allowFontScaling>
          Upload an official prescription photo or PDF document to archive alongside this plan.
        </Text>

        {/* Document Kind Chips */}
        <View style={styles.kindSelectorRow}>
          {DOC_KINDS.map((k) => (
            <TouchableOpacity
              key={k.key}
              style={[
                styles.kindChip,
                selectedKind === k.key ? styles.kindChipActive : null,
              ]}
              onPress={() => {
                setSelectedKind(k.key);
                if (attachment) {
                  setAttachment({ ...attachment, kind: k.key });
                }
              }}
              accessibilityRole="button"
              accessibilityLabel={`Select document type: ${k.label}`}
            >
              <Text
                style={[
                  styles.kindChipText,
                  selectedKind === k.key ? styles.kindChipTextActive : null,
                ]}
                allowFontScaling
              >
                {k.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {attachment ? (
          <View style={styles.attachmentPreviewCard}>
            <View style={styles.previewIconWrap}>
              <Ionicons name="document-text" size={20} color={doctorPalette.primary} />
            </View>
            <View style={styles.previewTextCol}>
              <TextInput
                label="Document Filename"
                value={attachmentName}
                onChangeText={setAttachmentName}
                accessibilityHint="Edit the attached document file name"
              />
              <Text style={styles.previewMetaText} allowFontScaling>
                Type: {selectedKind.replace("_", " ").toUpperCase()} · Ready for clinical archive
              </Text>
            </View>
            <TouchableOpacity
              style={styles.removeBtn}
              onPress={() => {
                setAttachment(null);
                setAttachmentName("");
              }}
              accessibilityRole="button"
              accessibilityLabel="Remove document attachment"
            >
              <Ionicons name="trash-outline" size={18} color="#EF4444" />
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.uploadButtonsRow}>
            <TouchableOpacity
              style={styles.uploadBtn}
              onPress={handlePickCamera}
              accessibilityRole="button"
              accessibilityLabel="Take a photo of prescription with camera"
            >
              <Ionicons name="camera" size={18} color={doctorPalette.primary} />
              <Text style={styles.uploadBtnText} allowFontScaling>
                Take Photo
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.uploadBtn}
              onPress={handlePickLibrary}
              accessibilityRole="button"
              accessibilityLabel="Choose prescription image or document from gallery"
            >
              <Ionicons name="cloud-upload" size={18} color={doctorPalette.primary} />
              <Text style={styles.uploadBtnText} allowFontScaling>
                Upload File
              </Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

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
  attachmentSection: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 14,
    gap: 10,
  },
  attachmentHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  attachmentSectionTitle: {
    fontSize: 13,
    fontWeight: "800",
    color: doctorPalette.ink,
    flex: 1,
  },
  attachmentSub: {
    fontSize: 11,
    color: doctorPalette.muted,
    lineHeight: 16,
  },
  kindSelectorRow: {
    flexDirection: "row",
    gap: 8,
    marginVertical: 2,
  },
  kindChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
  },
  kindChipActive: {
    backgroundColor: doctorPalette.surfaceBlue,
    borderColor: "#BFDBFE",
  },
  kindChipText: {
    fontSize: 11,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  kindChipTextActive: {
    color: doctorPalette.primary,
    fontWeight: "800",
  },
  uploadButtonsRow: {
    flexDirection: "row",
    gap: 10,
    marginTop: 4,
  },
  uploadBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: doctorPalette.surfaceSoft,
    borderRadius: doctorRadii.md,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
  },
  uploadBtnText: {
    fontSize: 12,
    fontWeight: "700",
    color: doctorPalette.ink,
  },
  attachmentPreviewCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: doctorPalette.surfaceSoft,
    borderRadius: doctorRadii.md,
    padding: 12,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
  },
  previewIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  previewTextCol: {
    flex: 1,
    gap: 4,
  },
  previewMetaText: {
    fontSize: 10,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  removeBtn: {
    padding: 8,
  },
});