import React, { useState } from "react";
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { caregiverPalette, caregiverRadii, caregiverShadow } from "./caregiverDesign";
import { Button } from "../../components/primitives/Button";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { useLinkCaregiverPatient } from "./useLinkCaregiverPatient";
import type { CaregiverPatientListItem } from "../../services/schemas/caregiver";
import type { ApiErrorDetails } from "../../services/api/errors";

export type LinkPatientModalProps = {
  visible: boolean;
  onClose: () => void;
  onSuccess: (patient: CaregiverPatientListItem) => void;
  testID?: string;
};

const RELATIONSHIP_OPTIONS: { label: string; icon: string }[] = [
  { label: "Primary Family Caregiver", icon: "heart" },
  { label: "Spouse", icon: "people" },
  { label: "Parent", icon: "person" },
  { label: "Son / Daughter", icon: "happy" },
  { label: "Guardian", icon: "shield" },
  { label: "Family Member", icon: "home" },
];

export function LinkPatientModal({
  visible,
  onClose,
  onSuccess,
  testID,
}: LinkPatientModalProps) {
  const [uhid, setUhid] = useState("");
  const [relationship, setRelationship] = useState("Primary Family Caregiver");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const linkMutation = useLinkCaregiverPatient({
    onSuccess: (linkedPatient) => {
      setUhid("");
      setErrorMessage(null);
      onSuccess(linkedPatient);
    },
    onError: (err) => {
      const apiErr = err as ApiErrorDetails | undefined;
      if (apiErr?.httpStatus === 404) {
        setErrorMessage(
          "No active patient found with this UHID. Please check the spelling or ask the patient for their UHID from their Profile."
        );
      } else if (apiErr?.httpStatus === 403) {
        setErrorMessage("Only authenticated caregivers can link patients.");
      } else {
        setErrorMessage(apiErr?.message ?? "Failed to link patient. Please try again.");
      }
    },
  });

  const handleSubmit = () => {
    if (!uhid.trim()) {
      setErrorMessage("Please enter a patient UHID or ID.");
      return;
    }
    setErrorMessage(null);
    linkMutation.mutate({
      uhid: uhid.trim(),
      relationship_label: relationship,
    });
  };

  const handleClose = () => {
    setErrorMessage(null);
    onClose();
  };

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent
      onRequestClose={handleClose}
      testID={testID}
    >
      <KeyboardAvoidingView
        style={styles.overlay}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <TouchableOpacity
          style={styles.backdrop}
          activeOpacity={1}
          onPress={handleClose}
        />

        <View style={styles.sheetContainer}>
          <View style={styles.sheetHandleRow}>
            <View style={styles.sheetHandle} />
          </View>

          {/* Header */}
          <View style={styles.sheetHeader}>
            <View style={styles.sheetHeaderLeft}>
              <View style={styles.iconCircle}>
                <Ionicons name="link" size={18} color={caregiverPalette.primary} />
              </View>
              <View>
                <Text style={styles.sheetTitle} allowFontScaling>
                  Link Patient Account
                </Text>
                <Text style={styles.sheetSubtitle} allowFontScaling>
                  Connect via UHID for daily care support
                </Text>
              </View>
            </View>
            <TouchableOpacity
              onPress={handleClose}
              hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
              style={styles.closeBtn}
              accessibilityRole="button"
              accessibilityLabel="Close"
            >
              <Ionicons name="close" size={20} color={caregiverPalette.muted} />
            </TouchableOpacity>
          </View>

          <ScrollView
            contentContainerStyle={styles.sheetBody}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {/* Procedure Explainer Card */}
            <View style={styles.procedureCard}>
              <Text style={styles.procedureTitle} allowFontScaling>
                How Caregiver Linking Works
              </Text>
              <View style={styles.stepRow}>
                <View style={styles.stepNumberBadge}>
                  <Text style={styles.stepNumberText}>1</Text>
                </View>
                <Text style={styles.stepText} allowFontScaling>
                  Ask the patient for their UHID (e.g., <Text style={styles.boldText}>UHID-C3AA6104</Text>) found in their app's Profile / You tab.
                </Text>
              </View>
              <View style={styles.stepRow}>
                <View style={styles.stepNumberBadge}>
                  <Text style={styles.stepNumberText}>2</Text>
                </View>
                <Text style={styles.stepText} allowFontScaling>
                  Enter their UHID below and declare your family relationship.
                </Text>
              </View>
              <View style={styles.stepRow}>
                <View style={styles.stepNumberBadge}>
                  <Text style={styles.stepNumberText}>3</Text>
                </View>
                <Text style={styles.stepText} allowFontScaling>
                  Start monitoring their daily glucose, meals, and helping with routine tasks immediately.
                </Text>
              </View>
            </View>

            {errorMessage ? (
              <AlertBanner
                tone="critical"
                title="Linking Failed"
                message={errorMessage}
              />
            ) : null}

            {/* UHID / Code Input */}
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel} allowFontScaling>
                Patient UHID, Pairing Passcode, or Email
              </Text>
              <View style={styles.inputWrapper}>
                <Ionicons
                  name="card-outline"
                  size={18}
                  color={caregiverPalette.primary}
                  style={styles.inputIcon}
                />
                <TextInput
                  style={styles.textInput}
                  value={uhid}
                  onChangeText={(val) => {
                    setUhid(val);
                    if (errorMessage) setErrorMessage(null);
                  }}
                  placeholder="e.g. PAIR-3F03EEB2 or UHID-C3AA6104"
                  placeholderTextColor={caregiverPalette.subtle}
                  autoCapitalize="none"
                  autoCorrect={false}
                  editable={!linkMutation.isPending}
                />
                {uhid.length > 0 ? (
                  <TouchableOpacity
                    onPress={() => setUhid("")}
                    hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                  >
                    <Ionicons name="close-circle" size={18} color={caregiverPalette.muted} />
                  </TouchableOpacity>
                ) : null}
              </View>
            </View>

            {/* Relationship Selector */}
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel} allowFontScaling>
                Your Relationship to Patient
              </Text>
              <View style={styles.chipGrid}>
                {RELATIONSHIP_OPTIONS.map((opt) => {
                  const isSelected = relationship === opt.label;
                  return (
                    <TouchableOpacity
                      key={opt.label}
                      style={[styles.chip, isSelected && styles.chipSelected]}
                      onPress={() => setRelationship(opt.label)}
                      activeOpacity={0.75}
                      accessibilityRole="button"
                    >
                      <Ionicons
                        name={opt.icon as any}
                        size={12}
                        color={isSelected ? caregiverPalette.primary : caregiverPalette.muted}
                      />
                      <Text
                        style={[
                          styles.chipText,
                          isSelected && styles.chipTextSelected,
                        ]}
                        allowFontScaling
                      >
                        {opt.label}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>

            {/* Security Assurance */}
            <View style={styles.assuranceBox}>
              <Ionicons name="shield-checkmark-outline" size={14} color={caregiverPalette.tealDark} />
              <Text style={styles.assuranceText} allowFontScaling>
                Direct Clinical Link: Verifying this patient connects your companion view securely under end-to-end audit compliance.
              </Text>
            </View>

            {/* Submit Action */}
            <View style={styles.buttonRow}>
              <Button
                label={linkMutation.isPending ? "Connecting…" : "Verify & Connect Patient"}
                variant="primary"
                onPress={handleSubmit}
                disabled={linkMutation.isPending || !uhid.trim()}
              />
            </View>
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.65)",
    justifyContent: "flex-end",
  },
  backdrop: {
    ...StyleSheet.absoluteFill,
  },
  sheetContainer: {
    backgroundColor: caregiverPalette.surface,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: "92%",
    paddingBottom: spacing.xl,
    ...caregiverShadow.modal,
  },
  sheetHandleRow: {
    alignItems: "center",
    paddingTop: 10,
    paddingBottom: 4,
  },
  sheetHandle: {
    width: 40,
    height: 4.5,
    borderRadius: 3,
    backgroundColor: "#CBD5E1",
  },
  sheetHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: caregiverPalette.border,
  },
  sheetHeaderLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  iconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: caregiverPalette.primaryLight,
    borderWidth: 1,
    borderColor: caregiverPalette.primaryBorder,
    alignItems: "center",
    justifyContent: "center",
  },
  sheetTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: caregiverPalette.ink,
  },
  sheetSubtitle: {
    fontSize: 11,
    color: caregiverPalette.muted,
    marginTop: 1,
  },
  closeBtn: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: caregiverPalette.surfaceSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  sheetBody: {
    padding: 16,
    gap: 14,
  },
  procedureCard: {
    backgroundColor: caregiverPalette.surfaceBlue,
    borderWidth: 1,
    borderColor: caregiverPalette.skyBorder,
    borderRadius: caregiverRadii.md,
    padding: 14,
    gap: 10,
  },
  procedureTitle: {
    fontSize: 13,
    fontWeight: "800",
    color: caregiverPalette.sky,
    marginBottom: 2,
  },
  stepRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 9,
  },
  stepNumberBadge: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: caregiverPalette.sky,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 1,
  },
  stepNumberText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  stepText: {
    flex: 1,
    fontSize: 12,
    color: "#0C4A6E",
    lineHeight: 18,
  },
  boldText: {
    fontWeight: "700",
  },
  inputGroup: {
    gap: 6,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: "700",
    color: caregiverPalette.inkSecondary,
  },
  inputWrapper: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: caregiverPalette.borderHighlight,
    borderRadius: caregiverRadii.md,
    backgroundColor: caregiverPalette.surfaceMuted,
    paddingHorizontal: 12,
    height: 48,
  },
  inputIcon: {
    marginRight: 8,
  },
  textInput: {
    flex: 1,
    fontSize: 14,
    color: caregiverPalette.ink,
    fontWeight: "700",
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
  },
  chipGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 2,
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: caregiverRadii.pill,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    backgroundColor: caregiverPalette.surfaceMuted,
  },
  chipSelected: {
    borderColor: caregiverPalette.primary,
    backgroundColor: caregiverPalette.primaryLight,
  },
  chipText: {
    fontSize: 11,
    color: caregiverPalette.muted,
    fontWeight: "600",
  },
  chipTextSelected: {
    color: caregiverPalette.primary,
    fontWeight: "800",
  },
  assuranceBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: caregiverPalette.surfaceTeal,
    padding: 10,
    borderRadius: caregiverRadii.sm,
    borderWidth: 1,
    borderColor: caregiverPalette.tealSoft,
  },
  assuranceText: {
    flex: 1,
    fontSize: 11,
    color: caregiverPalette.tealDark,
    lineHeight: 16,
  },
  buttonRow: {
    marginTop: 4,
  },
});
