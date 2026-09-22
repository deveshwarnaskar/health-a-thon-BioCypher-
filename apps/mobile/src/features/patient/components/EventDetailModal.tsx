import React from "react";
import {
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import type { TimelineEvent } from "../types";

export type EventDetailModalProps = {
  visible: boolean;
  event: TimelineEvent | null;
  onClose: () => void;
};

export function EventDetailModal({ visible, event, onClose }: EventDetailModalProps) {
  if (!event) return null;

  const dateObj = new Date(event.timestamp);
  const formattedDate = dateObj.toLocaleDateString([], {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const formattedTime = dateObj.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  const getSyncLabel = () => {
    if (event.status === "SYNCED") return "Synced to clinical record";
    if (event.status === "SAVED_LOCALLY") return "Saved locally on this device";
    if (event.status === "PENDING") return "Awaiting confirmation";
    if (event.status === "SYNCING") return "Synchronizing…";
    return "Local record";
  };

  return (
    <Modal visible={visible} animationType="fade" transparent onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.container}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerLeft}>
              <View style={styles.kickerRow}>
                <View style={styles.kickerDot} />
                <Text style={styles.kicker} allowFontScaling>
                  RECORD DETAILS
                </Text>
              </View>
              <Text style={styles.title} allowFontScaling numberOfLines={1}>
                {event.title}
              </Text>
            </View>
            <TouchableOpacity
              onPress={onClose}
              style={styles.closeBtn}
              accessibilityRole="button"
              accessibilityLabel="Close details"
              activeOpacity={0.7}
            >
              <Ionicons name="close" size={20} color="#0F172A" />
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
            {/* Sync / Provenance Banner */}
            <View style={styles.statusBanner}>
              <Ionicons
                name={event.status === "SYNCED" ? "cloud-done-outline" : "phone-portrait-outline"}
                size={16}
                color={event.status === "SYNCED" ? "#059669" : "#0284C7"}
              />
              <Text style={styles.statusBannerText} allowFontScaling>
                {getSyncLabel()}
              </Text>
            </View>

            {/* Core Attributes */}
            <View style={styles.section}>
              <View style={styles.row}>
                <Text style={styles.metaLabel} allowFontScaling>Date</Text>
                <Text style={styles.metaValue} allowFontScaling>{formattedDate}</Text>
              </View>
              <View style={styles.divider} />

              <View style={styles.row}>
                <Text style={styles.metaLabel} allowFontScaling>Time</Text>
                <Text style={styles.metaValue} allowFontScaling>{formattedTime}</Text>
              </View>
              <View style={styles.divider} />

              <View style={styles.row}>
                <Text style={styles.metaLabel} allowFontScaling>Category</Text>
                <Text style={styles.metaValue} allowFontScaling>
                  {event.type.charAt(0).toUpperCase() + event.type.slice(1)}
                </Text>
              </View>
              <View style={styles.divider} />

              <View style={styles.row}>
                <Text style={styles.metaLabel} allowFontScaling>Description</Text>
                <Text style={styles.metaValue} allowFontScaling>{event.subtitle}</Text>
              </View>
            </View>

            {/* Extra Details if present */}
            {event.details && Object.keys(event.details).length > 0 ? (
              <View style={styles.detailsCard}>
                <Text style={styles.detailsHeader} allowFontScaling>OBSERVED ATTRIBUTES</Text>
                {Object.entries(event.details).map(([k, v]) => {
                  if (v === undefined || v === null || typeof v === "object") return null;
                  return (
                    <View key={k} style={styles.detailRow}>
                      <Text style={styles.detailKey} allowFontScaling>
                        {k.replace(/_/g, " ")}:
                      </Text>
                      <Text style={styles.detailVal} allowFontScaling>
                        {String(v)}
                      </Text>
                    </View>
                  );
                })}
              </View>
            ) : null}

            {/* Non-diagnostic assurance */}
            <Text style={styles.disclaimer} allowFontScaling>
              This is a patient health event recorded for your personal tracking and clinician care review.
            </Text>
          </ScrollView>

          {/* Close button */}
          <TouchableOpacity style={styles.dismissButton} onPress={onClose} activeOpacity={0.7}>
            <Text style={styles.dismissButtonText} allowFontScaling>Close</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.65)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.md,
  },
  container: {
    backgroundColor: colors.surface,
    borderRadius: 24,
    width: "100%",
    maxWidth: 420,
    maxHeight: "82%",
    padding: spacing.lg,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.18,
    shadowRadius: 24,
    elevation: 8,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  headerLeft: {
    flex: 1,
    marginRight: spacing.sm,
  },
  kickerRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 2,
  },
  kickerDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#0D9488",
    marginRight: 6,
  },
  kicker: {
    fontSize: 10,
    color: "#64748B",
    fontWeight: "700",
    letterSpacing: 1.1,
  },
  title: {
    fontSize: 18,
    color: "#0F172A",
    fontWeight: "800",
    letterSpacing: -0.3,
  },
  closeBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    justifyContent: "center",
  },
  body: {
    marginBottom: spacing.md,
  },
  statusBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: "#F0FDF4",
    borderColor: "#BBF7D0",
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 3,
    marginBottom: spacing.md,
  },
  statusBannerText: {
    fontSize: 12,
    color: "#166534",
    fontWeight: "600",
  },
  section: {
    backgroundColor: "#F8FAFC",
    borderRadius: 18,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    marginBottom: spacing.md,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.xs,
  },
  divider: {
    height: 1,
    backgroundColor: "#EEF2F6",
    marginVertical: 2,
  },
  metaLabel: {
    fontSize: 13,
    color: "#64748B",
    fontWeight: "500",
  },
  metaValue: {
    fontSize: 13,
    color: "#0F172A",
    fontWeight: "700",
    maxWidth: "60%",
    textAlign: "right",
  },
  detailsCard: {
    backgroundColor: "#F8FAFC",
    borderRadius: 18,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    marginBottom: spacing.md,
  },
  detailsHeader: {
    fontSize: 11,
    color: "#475569",
    fontWeight: "700",
    letterSpacing: 0.8,
    marginBottom: spacing.xs,
  },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 2,
  },
  detailKey: {
    fontSize: 12,
    color: "#64748B",
    textTransform: "capitalize",
  },
  detailVal: {
    fontSize: 12,
    color: "#0F172A",
    fontWeight: "600",
  },
  disclaimer: {
    fontSize: 11,
    color: "#94A3B8",
    textAlign: "center",
    fontStyle: "italic",
    marginTop: spacing.xs,
    lineHeight: 16,
  },
  dismissButton: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: radii.pill,
    minHeight: 46,
    alignItems: "center",
    justifyContent: "center",
  },
  dismissButtonText: {
    fontSize: 14,
    color: "#0F172A",
    fontWeight: "700",
  },
});
