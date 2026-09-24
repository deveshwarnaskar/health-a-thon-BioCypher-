import React, { useState } from "react";
import { StyleSheet, Text, View, ScrollView, Pressable } from "react-native";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { LoadingState } from "../../components/primitives/LoadingState";
import { EmptyState } from "../../components/primitives/EmptyState";
import { spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import type { PatientSummaryResponse } from "../../services/schemas/patients";
import { useDoctorNotifications } from "./useDoctorNotifications";

export type CommunicationWorkspaceProps = {
  patients: PatientSummaryResponse[];
  onOpenPatientById?: (patientId: string) => void;
};

export function CommunicationWorkspace({
  patients,
  onOpenPatientById,
}: CommunicationWorkspaceProps) {
  const [selectedPatientId, setSelectedPatientId] = useState<string | undefined>(undefined);
  const { notifications, total, isLoading, refetch } = useDoctorNotifications(selectedPatientId);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Patient Communication & Notification Log</Text>
          <Text style={styles.subtitle}>
            Clinical messages, WhatsApp nudges, and metabolic alerts ({total} logged events)
          </Text>
        </View>
        <Button label="Refresh Feed" variant="outline" onPress={() => refetch()} />
      </View>

      {/* RBAC Notice */}
      <View style={styles.rbacNotice}>
        <Text style={styles.rbacTitle}>COMMUNICATION GOVERNANCE</Text>
        <Text style={styles.rbacText}>
          Doctor role holds audit inspection rights (READ_NOTIFICATIONS). Automated dispatch and
          template broadcasts are orchestrated via the Care Coordinator and backend notification worker.
        </Text>
      </View>

      {/* Patient Filter Pills */}
      <View style={styles.patientBar}>
        <Text style={styles.patientBarLabel}>Filter:</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.patientPills}>
          <Pressable
            style={[styles.patientPill, selectedPatientId === undefined ? styles.patientPillActive : null]}
            onPress={() => setSelectedPatientId(undefined)}
          >
            <Text
              style={[
                styles.patientPillText,
                selectedPatientId === undefined ? styles.patientPillTextActive : null,
              ]}
            >
              All Facility Patients
            </Text>
          </Pressable>
          {patients.map((p) => {
            const isSelected = p.patient_id === selectedPatientId;
            return (
              <Pressable
                key={p.patient_id}
                style={[styles.patientPill, isSelected ? styles.patientPillActive : null]}
                onPress={() => setSelectedPatientId(p.patient_id)}
              >
                <Text
                  style={[styles.patientPillText, isSelected ? styles.patientPillTextActive : null]}
                >
                  {p.name}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {/* Notification Stream */}
      {isLoading ? (
        <LoadingState label="Loading communications log…" />
      ) : notifications.length === 0 ? (
        <EmptyState
          title="No logged communications"
          message="No notification events found for this filter."
        />
      ) : (
        <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
          {notifications.map((item) => (
            <View key={item.id} style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardHeaderLeft}>
                  <Badge
                    label={item.status.toUpperCase()}
                    tone={
                      item.status === "delivered"
                        ? "success"
                        : item.status === "failed"
                        ? "critical"
                        : "info"
                    }
                  />
                  <Text style={styles.recipientPhone}>{item.recipient_phone}</Text>
                </View>
                <Text style={styles.timestamp}>
                  {new Date(item.created_at).toLocaleString()}
                </Text>
              </View>

              <Text style={styles.templateName}>
                Template / Kind: {item.template_name || item.notification_type || "Direct Alert"}
              </Text>

              {item.failure_reason ? (
                <Text style={styles.failureText}>Failure reason: {item.failure_reason}</Text>
              ) : null}

              {onOpenPatientById && item.recipient_id ? (
                <View style={styles.footerRow}>
                  <Pressable onPress={() => onOpenPatientById(item.recipient_id)}>
                    <Text style={styles.patientLink}>View Patient Record</Text>
                  </Pressable>
                </View>
              ) : null}
            </View>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  title: {
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  subtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.muted,
    fontWeight: "600",
  },
  rbacNotice: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.xs,
    backgroundColor: doctorPalette.limeSoft,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.9)",
    padding: spacing.sm,
    borderRadius: doctorRadii.lg,
    gap: 2,
    ...doctorSoftShadow,
  },
  rbacTitle: {
    fontSize: 10,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: 0,
  },
  rbacText: {
    fontSize: 11,
    color: doctorPalette.muted,
    lineHeight: 16,
  },
  patientBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    backgroundColor: doctorPalette.surface,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.border,
    marginTop: spacing.sm,
  },
  patientBarLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: "700",
    color: doctorPalette.muted,
  },
  patientPills: {
    flexDirection: "row",
  },
  patientPill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    marginRight: 6,
  },
  patientPillActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.surfaceLime,
  },
  patientPillText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
    fontWeight: "700",
  },
  patientPillTextActive: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.lg,
    gap: spacing.md,
    paddingBottom: 130,
  },
  card: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.md,
    gap: spacing.sm,
    ...doctorSoftShadow,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
    flexWrap: "wrap",
  },
  cardHeaderLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  recipientPhone: {
    fontSize: typography.fontSize.caption,
    fontWeight: "700",
    color: doctorPalette.ink,
  },
  timestamp: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  templateName: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.ink,
  },
  failureText: {
    fontSize: typography.fontSize.caption,
    color: "#BE185D",
  },
  footerRow: {
    borderTopWidth: 1,
    borderTopColor: doctorPalette.border,
    paddingTop: spacing.xs,
  },
  patientLink: {
    fontSize: typography.fontSize.caption,
    fontWeight: "800",
    color: doctorPalette.primary,
  },
});
