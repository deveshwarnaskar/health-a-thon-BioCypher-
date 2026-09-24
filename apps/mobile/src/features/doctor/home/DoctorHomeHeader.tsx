import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "../doctorDesign";

function formatAgo(timestamp: number | null): string {
  if (!timestamp) return "just now";
  const elapsedMs = Date.now() - timestamp;
  if (elapsedMs < 60_000) return "just now";
  const minutes = Math.round(elapsedMs / 60_000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}

function formatFacilityName(facilityId?: string | null): string {
  if (!facilityId) return "Apex Diabetes Care Centre";
  const trimmed = facilityId.trim();
  // If it's a UUID or default placeholder, render authoritative clinic name
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(trimmed) || trimmed === "Facility 1") {
    return "Apex Diabetes & Endocrine Centre";
  }
  return trimmed;
}

export function DoctorHomeHeader({
  facilityId,
  lastSyncedAt,
  subSpecialty = "Metabolic & Outpatient Unit",
}: {
  facilityId: string;
  lastSyncedAt: number | null;
  subSpecialty?: string;
}) {
  const clinicName = formatFacilityName(facilityId);

  return (
    <View style={styles.headerCard}>
      <View style={styles.facilityBlock}>
        <View style={styles.facilityIcon}>
          <Ionicons name="business" size={17} color={doctorPalette.primary} />
        </View>
        <View style={styles.facilityTextCol}>
          <Text style={styles.facilityName} allowFontScaling numberOfLines={1}>
            {clinicName}
          </Text>
          <View style={styles.subInfoRow}>
            <View style={styles.liveIndicator}>
              <View style={styles.liveDot} />
              <View style={styles.liveDotPing} />
            </View>
            <Text style={styles.syncText} allowFontScaling numberOfLines={1}>
              Live Telemetry · {formatAgo(lastSyncedAt)}
            </Text>
          </View>
        </View>
      </View>

      <View style={styles.protocolBadge}>
        <Ionicons name="shield-checkmark" size={12} color="#15803D" />
        <Text style={styles.protocolBadgeText} allowFontScaling>
          ADA / RSSDI
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  headerCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: doctorPalette.surface,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    paddingHorizontal: 14,
    paddingVertical: 10,
    gap: 10,
    ...doctorSoftShadow,
  },
  facilityBlock: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    flex: 1,
  },
  facilityIcon: {
    width: 34,
    height: 34,
    borderRadius: 12,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  facilityTextCol: {
    flex: 1,
    gap: 2,
  },
  facilityName: {
    fontSize: 13,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.2,
  },
  subInfoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  liveIndicator: {
    width: 8,
    height: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#10B981",
  },
  liveDotPing: {
    position: "absolute",
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "rgba(16, 185, 129, 0.35)",
  },
  syncText: {
    fontSize: 11,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  protocolBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: "#F0FDF4",
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderWidth: 1,
    borderColor: "#DCFCE7",
  },
  protocolBadgeText: {
    fontSize: 11,
    fontWeight: "800",
    color: "#166534",
  },
});