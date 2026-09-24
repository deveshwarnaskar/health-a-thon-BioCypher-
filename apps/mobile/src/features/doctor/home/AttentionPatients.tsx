import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "../doctorDesign";
import { SectionHeader, HomeInlineState } from "./DoctorHomeBits";
import type { AttentionFlag } from "../../../services/clinical/cohortClinicalAnalysis";
import type { PatientSummaryResponse } from "../../../services/schemas/patients";

function flagGlyph(sev: AttentionFlag["severity"]): React.ComponentProps<typeof Ionicons>["name"] {
  return sev === "needs_review" ? "alert-circle" : "time-outline";
}

function formatReadingTime(timestamp: string | null): string | null {
  if (!timestamp) return null;
  const ms = Date.now() - new Date(timestamp).getTime();
  if (isNaN(ms) || ms < 0) return null;
  const mins = Math.round(ms / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

function getReadingBadge(val: number | null) {
  if (val === null) return null;
  const round = Math.round(val);
  if (val < 54) {
    return { label: `🚨 Hypo · ${round} mg/dL`, bg: "#FEE2E2", text: "#991B1B", border: "#FCA5A5" };
  }
  if (val < 70) {
    return { label: `Low · ${round} mg/dL`, bg: "#FEF2F2", text: "#DC2626", border: "#FECACA" };
  }
  if (val <= 180) {
    return { label: `Target · ${round} mg/dL`, bg: "#F0FDF4", text: "#15803D", border: "#BBF7D0" };
  }
  if (val <= 250) {
    return { label: `High · ${round} mg/dL`, bg: "#FFFBEB", text: "#B45309", border: "#FDE68A" };
  }
  return { label: `Very High · ${round} mg/dL`, bg: "#FEF2F2", text: "#B91C1C", border: "#FECACA" };
}

export function AttentionPatients({
  patients,
  onSelectPatient,
  onViewAll,
  emptyMessage,
  isLoading,
}: {
  patients: {
    patient: PatientSummaryResponse;
    flags: AttentionFlag[];
    lastReadingValue: number | null;
    lastReadingAt: string | null;
  }[];
  onSelectPatient: (patientId: string) => void;
  onViewAll?: () => void;
  emptyMessage?: string;
  isLoading?: boolean;
}) {
  const empty = isLoading ? (
    <HomeInlineState
      icon="sync-outline"
      title="Checking clinical cohort flags"
      message="Evaluating active glucose telemetry, glycemic thresholds, and review cadences."
    />
  ) : (
    <HomeInlineState
      icon="checkmark-circle-outline"
      title="No Urgent Attention Required"
      message={emptyMessage ?? "All analyzed patients are within target glycemic parameters and on-schedule for reviews."}
    />
  );

  return (
    <View style={styles.section}>
      <SectionHeader
        title="Patients Who Need Attention"
        viewAllLabel="Open directory"
        onViewAll={onViewAll}
      />
      {patients.length === 0 ? (
        empty
      ) : (
        <View style={styles.list}>
          {patients.map(({ patient, flags, lastReadingValue, lastReadingAt }) => {
            const uhid =
              patient.uh_id ||
              (patient.patient_id.length > 12
                ? `UHID-${patient.patient_id.slice(0, 8).toUpperCase()}`
                : patient.patient_id);
            const badge = getReadingBadge(lastReadingValue);
            const timeAgo = formatReadingTime(lastReadingAt);
            const initial = (patient.name || "P").trim().charAt(0).toUpperCase();

            return (
              <Pressable
                key={patient.patient_id}
                style={({ pressed }) => [styles.patientRow, pressed && styles.patientRowPressed]}
                onPress={() => onSelectPatient(patient.patient_id)}
                accessibilityRole="button"
                accessibilityLabel={`${patient.name}, ${uhid}: ${flags.map((f) => f.label).join(", ")}`}
              >
                <View style={styles.avatar}>
                  <Text style={styles.avatarInitial} allowFontScaling>
                    {initial}
                  </Text>
                </View>

                <View style={styles.patientBody}>
                  <View style={styles.patientTopRow}>
                    <View style={styles.nameUhidCol}>
                      <Text style={styles.patientName} allowFontScaling numberOfLines={1}>
                        {patient.name}
                      </Text>
                      <View style={styles.uhidTimeRow}>
                        <Text style={styles.uhidText} allowFontScaling numberOfLines={1}>
                          {uhid}
                        </Text>
                        {timeAgo ? (
                          <>
                            <Text style={styles.metaDot}>·</Text>
                            <Text style={styles.timeText} allowFontScaling numberOfLines={1}>
                              {timeAgo}
                            </Text>
                          </>
                        ) : null}
                      </View>
                    </View>

                    {badge ? (
                      <View
                        style={[
                          styles.readingChip,
                          {
                            backgroundColor: badge.bg,
                            borderColor: badge.border,
                          },
                        ]}
                      >
                        <Text style={[styles.readingChipText, { color: badge.text }]} allowFontScaling>
                          {badge.label}
                        </Text>
                      </View>
                    ) : null}
                  </View>

                  <View style={styles.flagsContainer}>
                    {flags.map((flag) => {
                      const isCritical = flag.severity === "needs_review";
                      return (
                        <View
                          key={flag.label}
                          style={[
                            styles.flagPill,
                            isCritical ? styles.flagPillCritical : styles.flagPillWatch,
                          ]}
                        >
                          <Ionicons
                            name={flagGlyph(flag.severity)}
                            size={12}
                            color={isCritical ? "#DC2626" : "#D97706"}
                          />
                          <Text
                            style={[
                              styles.flagLabel,
                              isCritical ? styles.flagLabelCritical : styles.flagLabelWatch,
                            ]}
                            allowFontScaling
                            numberOfLines={1}
                          >
                            {flag.label}
                          </Text>
                        </View>
                      );
                    })}
                  </View>
                </View>

                <Ionicons name="chevron-forward" size={18} color={doctorPalette.muted} />
              </Pressable>
            );
          })}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: 12,
  },
  list: {
    gap: 10,
  },
  patientRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: doctorPalette.surface,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 14,
    ...doctorSoftShadow,
  },
  patientRowPressed: {
    opacity: 0.86,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  avatar: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
  },
  avatarInitial: {
    fontSize: 16,
    fontWeight: "800",
    color: doctorPalette.primary,
  },
  patientBody: {
    flex: 1,
    gap: 6,
  },
  patientTopRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 8,
  },
  nameUhidCol: {
    flex: 1,
    gap: 2,
  },
  patientName: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.2,
  },
  uhidTimeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  uhidText: {
    fontSize: 11,
    fontWeight: "700",
    color: doctorPalette.muted,
  },
  metaDot: {
    fontSize: 11,
    color: doctorPalette.quiet,
  },
  timeText: {
    fontSize: 11,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  readingChip: {
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderWidth: 1,
  },
  readingChipText: {
    fontSize: 11,
    fontWeight: "800",
  },
  flagsContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  flagPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderWidth: 1,
  },
  flagPillCritical: {
    backgroundColor: "#FEF2F2",
    borderColor: "#FECACA",
  },
  flagPillWatch: {
    backgroundColor: "#FFFBEB",
    borderColor: "#FDE68A",
  },
  flagLabel: {
    fontSize: 11,
    fontWeight: "700",
  },
  flagLabelCritical: {
    color: "#B91C1C",
  },
  flagLabelWatch: {
    color: "#B45309",
  },
});