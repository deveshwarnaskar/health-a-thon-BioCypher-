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
import { colors, radii, spacing, touchTarget, typography } from "../../../../theming/tokens";

export type CareProfileModalProps = {
  visible: boolean;
  onClose: () => void;
  patientName?: string;
  uhid?: string;
};

const TRACKING_MODULES = [
  { label: "Blood Glucose Logging", icon: "water-outline", color: "#0D9488", bg: "#F0FDFA" },
  { label: "Meals & Katori Sizing", icon: "restaurant-outline", color: "#D97706", bg: "#FFFBEB" },
  { label: "Prescription Adherence", icon: "medkit-outline", color: "#2563EB", bg: "#EFF6FF" },
  { label: "Physical Activity Tracking", icon: "walk-outline", color: "#059669", bg: "#ECFDF5" },
  { label: "Blood Pressure & Vitals", icon: "pulse-outline", color: "#E11D48", bg: "#FFF1F2" },
  { label: "Document & Lab Ingestion", icon: "document-text-outline", color: "#7C3AED", bg: "#F5F3FF" },
] as const;

export function CareProfileModal({ visible, onClose, patientName, uhid }: CareProfileModalProps) {
  return (
    <Modal visible={visible} animationType="slide" transparent={false} onRequestClose={onClose}>
      <View style={styles.container}>
        {/* Modern Header */}
        <View style={styles.header}>
          <TouchableOpacity
            onPress={onClose}
            style={styles.backBtn}
            accessibilityRole="button"
            accessibilityLabel="Back"
            activeOpacity={0.7}
          >
            <Ionicons name="arrow-back" size={20} color="#0F172A" />
          </TouchableOpacity>
          <View style={styles.headerTextCol}>
            <View style={styles.kickerRow}>
              <View style={styles.kickerDot} />
              <Text style={styles.kicker} allowFontScaling>
                CLINICAL CARE CONFIGURATION
              </Text>
            </View>
            <Text style={styles.title} allowFontScaling>
              Care Profile
            </Text>
          </View>
        </View>

        <ScrollView style={styles.body} contentContainerStyle={styles.bodyContent} showsVerticalScrollIndicator={false}>
          {/* Read-only Alert Card */}
          <View style={styles.noticeCard}>
            <View style={styles.noticeIconBox}>
              <Ionicons name="shield-checkmark" size={18} color="#0284C7" />
            </View>
            <View style={styles.noticeTextCol}>
              <Text style={styles.noticeTitle} allowFontScaling>
                Clinician-Authored Protocol
              </Text>
              <Text style={styles.noticeText} allowFontScaling>
                Care targets, prescription plans, and monitoring intervals are clinician-authored by your supervising doctor.
              </Text>
            </View>
          </View>

          {/* Section 1: Diagnosis & Plan */}
          <View style={styles.card}>
            <View style={styles.sectionHeaderRow}>
              <View style={[styles.sectionIconBox, { backgroundColor: "#F0FDFA" }]}>
                <Ionicons name="clipboard-outline" size={16} color="#0D9488" />
              </View>
              <Text style={styles.cardHeader} allowFontScaling>
                DIAGNOSIS & CARE REGIMEN
              </Text>
            </View>

            <View style={styles.itemRow}>
              <Text style={styles.label} allowFontScaling>Primary Condition</Text>
              <Text style={styles.val} allowFontScaling>Type 2 Diabetes Mellitus</Text>
            </View>
            <View style={styles.divider} />

            <View style={styles.itemRow}>
              <Text style={styles.label} allowFontScaling>Care Plan</Text>
              <Text style={styles.val} allowFontScaling>Standard Glycemic Management (ICMR 2024)</Text>
            </View>
            <View style={styles.divider} />

            <View style={styles.itemRow}>
              <Text style={styles.label} allowFontScaling>Monitoring Method</Text>
              <Text style={styles.val} allowFontScaling>Capillary Blood Glucose (SMBG)</Text>
            </View>
            <View style={styles.divider} />

            <View style={styles.itemRow}>
              <Text style={styles.label} allowFontScaling>Patient Identifier</Text>
              <View style={styles.idBadge}>
                <Ionicons name="id-card-outline" size={12} color="#0D9488" style={{ marginRight: 4 }} />
                <Text style={styles.idBadgeText} allowFontScaling>{uhid || "UHID-ASSIGNED"}</Text>
              </View>
            </View>
          </View>

          {/* Section 2: General Reference Ranges (Informational Only) */}
          <View style={styles.card}>
            <View style={styles.targetsHeaderRow}>
              <View style={styles.sectionHeaderRow}>
                <View style={[styles.sectionIconBox, { backgroundColor: "#EFF6FF" }]}>
                  <Ionicons name="speedometer-outline" size={16} color="#2563EB" />
                </View>
                <Text style={styles.cardHeader} allowFontScaling>
                  GENERAL REFERENCE RANGES
                </Text>
              </View>
              <View style={styles.readOnlyBadge}>
                <Ionicons name="information-circle-outline" size={12} color="#64748B" style={{ marginRight: 3 }} />
                <Text style={styles.readOnlyText} allowFontScaling>
                  INFORMATIONAL
                </Text>
              </View>
            </View>

            <View style={styles.targetRow}>
              <View style={styles.targetCol}>
                <Text style={styles.targetLabel} allowFontScaling>Fasting Target</Text>
                <Text style={styles.targetVal} allowFontScaling>80 – 130</Text>
                <Text style={styles.targetUnit} allowFontScaling>mg/dL</Text>
              </View>
              <View style={styles.targetColDivider} />
              <View style={styles.targetCol}>
                <Text style={styles.targetLabel} allowFontScaling>Post-Meal Target</Text>
                <Text style={styles.targetVal} allowFontScaling>&lt; 180</Text>
                <Text style={styles.targetUnit} allowFontScaling>mg/dL</Text>
              </View>
              <View style={styles.targetColDivider} />
              <View style={styles.targetCol}>
                <Text style={styles.targetLabel} allowFontScaling>HbA1c Target</Text>
                <Text style={styles.targetVal} allowFontScaling>&lt; 7.0</Text>
                <Text style={styles.targetUnit} allowFontScaling>%</Text>
              </View>
            </View>

            <View style={styles.explainerBox}>
              <Ionicons name="information-circle-outline" size={14} color="#64748B" style={{ marginRight: 6, marginTop: 1 }} />
              <Text style={styles.referenceExplainerText} allowFontScaling>
                These are general reference ranges and may not apply to your individual care plan. Your doctor&apos;s personalized targets will appear here when configured.
              </Text>
            </View>
          </View>

          {/* Section 3: Active Monitoring Modules */}
          <View style={styles.card}>
            <View style={styles.sectionHeaderRow}>
              <View style={[styles.sectionIconBox, { backgroundColor: "#ECFDF5" }]}>
                <Ionicons name="apps-outline" size={16} color="#059669" />
              </View>
              <Text style={styles.cardHeader} allowFontScaling>
                ACTIVE TRACKING MODULES
              </Text>
            </View>

            {TRACKING_MODULES.map((mod, index) => (
              <View key={mod.label}>
                <View style={styles.moduleRow}>
                  <View style={styles.moduleLeft}>
                    <View style={[styles.moduleIconCircle, { backgroundColor: mod.bg }]}>
                      <Ionicons name={mod.icon as any} size={17} color={mod.color} />
                    </View>
                    <Text style={styles.moduleLabel} allowFontScaling>
                      {mod.label}
                    </Text>
                  </View>
                  <View style={styles.moduleActiveBadge}>
                    <Ionicons name="checkmark-circle" size={12} color="#059669" style={{ marginRight: 3 }} />
                    <Text style={styles.moduleActiveText} allowFontScaling>
                      ENABLED
                    </Text>
                  </View>
                </View>
                {index < TRACKING_MODULES.length - 1 ? <View style={styles.divider} /> : null}
              </View>
            ))}
          </View>

          {/* Section 4: Report Schedule */}
          <View style={styles.card}>
            <View style={styles.sectionHeaderRow}>
              <View style={[styles.sectionIconBox, { backgroundColor: "#FFFBEB" }]}>
                <Ionicons name="time-outline" size={16} color="#D97706" />
              </View>
              <Text style={styles.cardHeader} allowFontScaling>
                REPORT SCHEDULE
              </Text>
            </View>

            <View style={styles.itemRow}>
              <View style={styles.scheduleLeft}>
                <Ionicons name="calendar-outline" size={16} color="#0284C7" style={{ marginRight: 8 }} />
                <Text style={styles.label} allowFontScaling>Weekly Care Summary</Text>
              </View>
              <Text style={styles.val} allowFontScaling>Every Monday 08:00 AM</Text>
            </View>
            <View style={styles.divider} />

            <View style={styles.itemRow}>
              <View style={styles.scheduleLeft}>
                <Ionicons name="bar-chart-outline" size={16} color="#7C3AED" style={{ marginRight: 8 }} />
                <Text style={styles.label} allowFontScaling>Monthly Clinical Review</Text>
              </View>
              <Text style={styles.val} allowFontScaling>1st of each month</Text>
            </View>
          </View>

          <View style={{ height: 40 }} />
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingTop: 54,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    backgroundColor: colors.surface,
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  headerTextCol: {
    marginLeft: spacing.sm + 2,
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
    fontSize: 20,
    color: "#0F172A",
    fontWeight: "800",
    letterSpacing: -0.3,
  },
  body: {
    flex: 1,
  },
  bodyContent: {
    padding: spacing.md,
    gap: spacing.md,
  },
  noticeCard: {
    flexDirection: "row",
    backgroundColor: "#F0F9FF",
    borderRadius: 18,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#BAE6FD",
    gap: spacing.sm,
    alignItems: "flex-start",
  },
  noticeIconBox: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: "#E0F2FE",
    alignItems: "center",
    justifyContent: "center",
  },
  noticeTextCol: {
    flex: 1,
  },
  noticeTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0369A1",
    marginBottom: 2,
  },
  noticeText: {
    fontSize: 12,
    color: "#0284C7",
    lineHeight: 18,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    padding: spacing.md + 2,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 1,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  sectionIconBox: {
    width: 28,
    height: 28,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  cardHeader: {
    fontSize: 11,
    color: "#64748B",
    fontWeight: "700",
    letterSpacing: 1,
  },
  targetsHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  readOnlyBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  readOnlyText: {
    color: "#475569",
    fontWeight: "700",
    fontSize: 10,
    letterSpacing: 0.5,
  },
  itemRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.xs + 2,
  },
  divider: {
    height: 1,
    backgroundColor: "#F1F5F9",
    marginVertical: 4,
  },
  label: {
    fontSize: 13,
    color: "#64748B",
    fontWeight: "500",
  },
  val: {
    fontSize: 13,
    color: "#0F172A",
    fontWeight: "700",
    maxWidth: "58%",
    textAlign: "right",
  },
  idBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  idBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#0D9488",
  },
  targetRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#F8FAFC",
    padding: spacing.md,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#EEF2F6",
    marginVertical: spacing.xs,
  },
  targetCol: {
    alignItems: "center",
    flex: 1,
  },
  targetColDivider: {
    width: 1,
    height: 36,
    backgroundColor: "#E2E8F0",
  },
  targetLabel: {
    fontSize: 10,
    fontWeight: "600",
    color: "#64748B",
    textAlign: "center",
  },
  targetVal: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
    marginTop: 2,
  },
  targetUnit: {
    fontSize: 10,
    color: "#94A3B8",
    fontWeight: "500",
  },
  explainerBox: {
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: "#F8FAFC",
    borderRadius: 12,
    padding: spacing.sm,
    marginTop: spacing.sm,
  },
  referenceExplainerText: {
    flex: 1,
    fontSize: 11,
    color: "#64748B",
    lineHeight: 16,
  },
  moduleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.xs + 2,
  },
  moduleLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  moduleIconCircle: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  moduleLabel: {
    fontSize: 13,
    color: "#0F172A",
    fontWeight: "600",
  },
  moduleActiveBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#ECFDF5",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#A7F3D0",
  },
  moduleActiveText: {
    color: "#059669",
    fontWeight: "700",
    fontSize: 10,
    letterSpacing: 0.5,
  },
  scheduleLeft: {
    flexDirection: "row",
    alignItems: "center",
  },
});
