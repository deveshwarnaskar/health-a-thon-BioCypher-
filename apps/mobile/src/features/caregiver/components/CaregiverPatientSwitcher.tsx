import React from "react";
import { Modal, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useCaregiverContext } from "../context/CaregiverContext";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { Badge } from "../../../components/primitives/Badge";
import { Button } from "../../../components/primitives/Button";
import { canReadCaregiverGlucose, canRecordCaregiverGlucose } from "../../../services/schemas/caregiver";

export type CaregiverPatientSwitcherProps = {
  visible: boolean;
  onClose: () => void;
  testID?: string;
};

/**
 * Caregiver patient switcher modal.
 * Only lists authorized linked patients from CaregiverContext.
 * Never searches tenant-wide patients, creates fake records, or allows manual ID entry.
 */
export function CaregiverPatientSwitcher({
  visible,
  onClose,
  testID = "caregiver-patient-switcher",
}: CaregiverPatientSwitcherProps) {
  const { linkedPatients, activePatientId, selectPatient } = useCaregiverContext();

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.overlay} testID={testID}>
        <View style={styles.dialog}>
          <View style={styles.header}>
            <Text style={styles.title} allowFontScaling>
              Switch Patient
            </Text>
            <Text style={styles.subtitle} allowFontScaling>
              Select an authorized patient to view their records
            </Text>
          </View>

          <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
            {linkedPatients.map((patient) => {
              const isActive = patient.patient_id === activePatientId;
              const canRead = canReadCaregiverGlucose(patient.capabilities);
              const canRecord = canRecordCaregiverGlucose(patient.capabilities);

              return (
                <TouchableOpacity
                  key={patient.patient_id}
                  style={[styles.patientItem, isActive && styles.activeItem]}
                  onPress={() => {
                    selectPatient(patient.patient_id);
                    onClose();
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={`Select patient ${patient.name}${isActive ? ", currently active" : ""}`}
                  accessibilityState={{ selected: isActive }}
                >
                  <View style={styles.itemHeader}>
                    <Text
                      style={[styles.patientName, isActive && styles.activeText]}
                      allowFontScaling
                    >
                      {patient.name}
                    </Text>
                    {isActive ? <Badge label="Active" tone="success" /> : null}
                  </View>
                  <View style={styles.detailsRow}>
                    {patient.relationship_label ? (
                      <Badge label={patient.relationship_label} tone="neutral" />
                    ) : null}
                    {canRead ? <Badge label="Glucose view" tone="info" /> : null}
                    {canRecord ? <Badge label="Can record" tone="neutral" /> : null}
                  </View>
                </TouchableOpacity>
              );
            })}
          </ScrollView>

          <View style={styles.footer}>
            <Button label="Close" variant="outline" onPress={onClose} />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.4)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.md,
  },
  dialog: {
    width: "100%",
    maxWidth: 420,
    maxHeight: "80%",
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.1,
    shadowRadius: 16,
    elevation: 6,
  },
  header: {
    marginBottom: spacing.md,
    gap: spacing.xxs,
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
  },
  list: {
    maxHeight: 320,
  },
  listContent: {
    gap: spacing.sm,
  },
  patientItem: {
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    gap: spacing.xs,
    minHeight: touchTarget.min,
    justifyContent: "center",
  },
  activeItem: {
    borderColor: colors.primary,
    backgroundColor: "rgba(13, 148, 136, 0.06)",
  },
  itemHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  patientName: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  activeText: {
    color: colors.primary,
    fontWeight: "700",
  },
  detailsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  footer: {
    marginTop: spacing.md,
    alignItems: "flex-end",
  },
});
