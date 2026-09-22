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

export type CareTeamModalProps = {
  visible: boolean;
  onClose: () => void;
  doctorName?: string;
  facilityName?: string;
};

export function CareTeamModal({
  visible,
  onClose,
  doctorName = "Dr. S. Mukherjee (Consultant Diabetologist)",
  facilityName = "Apex Diabetes & Endocrine Centre",
}: CareTeamModalProps) {
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
                CLINICAL SUPERVISION
              </Text>
            </View>
            <Text style={styles.title} allowFontScaling>
              Care Team
            </Text>
          </View>
        </View>

        <ScrollView style={styles.body} contentContainerStyle={styles.bodyContent} showsVerticalScrollIndicator={false}>
          {/* Supervision Notice */}
          <View style={styles.infoCard}>
            <View style={styles.infoIconBox}>
              <Ionicons name="medical" size={18} color="#0284C7" />
            </View>
            <View style={styles.infoTextCol}>
              <Text style={styles.infoTitle} allowFontScaling>
                Active Clinical Supervision
              </Text>
              <Text style={styles.infoText} allowFontScaling>
                Your care team reviews your longitudinal observations, authors medication plans, and monitors glycemic stability.
              </Text>
            </View>
          </View>

          <Text style={styles.sectionHeader} allowFontScaling>
            PRIMARY CLINICAL TEAM
          </Text>

          {/* Primary Clinician Card */}
          <View style={styles.memberCard}>
            <View style={styles.memberTopRow}>
              <View style={styles.avatar}>
                <Ionicons name="person" size={24} color="#2563EB" />
              </View>
              <View style={styles.memberInfo}>
                <View style={styles.memberNameRow}>
                  <Text style={styles.memberName} allowFontScaling numberOfLines={1}>
                    {doctorName}
                  </Text>
                  <View style={styles.verifiedBadge}>
                    <Ionicons name="checkmark-circle" size={14} color="#10B981" />
                  </View>
                </View>
                <Text style={styles.memberRole} allowFontScaling>
                  Lead Treating Physician · MBBS, MD
                </Text>
                <View style={styles.authBadge}>
                  <Ionicons name="shield-checkmark" size={12} color="#059669" style={{ marginRight: 4 }} />
                  <Text style={styles.authBadgeText} allowFontScaling>
                    Prescription Authority Active
                  </Text>
                </View>
              </View>
            </View>
          </View>

          {/* Facility Card */}
          <View style={styles.facilityCard}>
            <View style={styles.facilityIconCircle}>
              <Ionicons name="business-outline" size={22} color="#0D9488" />
            </View>
            <View style={styles.facilityInfo}>
              <Text style={styles.facilityKicker} allowFontScaling>
                ASSIGNED CLINICAL FACILITY
              </Text>
              <Text style={styles.facilityName} allowFontScaling>
                {facilityName}
              </Text>
              <Text style={styles.facilitySub} allowFontScaling>
                Active Facility Trust Boundary · P.L.A.T.E. Workstation
              </Text>
            </View>
          </View>

          {/* Clinical Escalation guidance */}
          <View style={styles.escalationCard}>
            <View style={styles.escalationHeaderRow}>
              <Ionicons name="information-circle-outline" size={16} color="#64748B" />
              <Text style={styles.escalationTitle} allowFontScaling>
                CLINICAL CONSULTATIONS
              </Text>
            </View>
            <Text style={styles.escalationBody} allowFontScaling>
              THALI is an assistive patient logbook. For prescription renewals, dose inquiries, or acute clinical concerns, contact your facility directly or visit your scheduled appointment.
            </Text>
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
  infoCard: {
    flexDirection: "row",
    backgroundColor: "#F0F9FF",
    borderRadius: 18,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#BAE6FD",
    gap: spacing.sm,
    alignItems: "flex-start",
  },
  infoIconBox: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: "#E0F2FE",
    alignItems: "center",
    justifyContent: "center",
  },
  infoTextCol: {
    flex: 1,
  },
  infoTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0369A1",
    marginBottom: 2,
  },
  infoText: {
    fontSize: 12,
    color: "#0284C7",
    lineHeight: 18,
  },
  sectionHeader: {
    fontSize: 11,
    color: "#64748B",
    fontWeight: "700",
    letterSpacing: 1.1,
    marginLeft: 4,
  },
  memberCard: {
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
  memberTopRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  avatar: {
    width: 50,
    height: 50,
    borderRadius: 16,
    backgroundColor: "#EFF6FF",
    borderWidth: 1,
    borderColor: "#BFDBFE",
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  memberInfo: {
    flex: 1,
  },
  memberNameRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  memberName: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
    flex: 1,
  },
  verifiedBadge: {
    marginLeft: 2,
  },
  memberRole: {
    fontSize: 12,
    color: "#475569",
    marginTop: 2,
  },
  authBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#ECFDF5",
    borderWidth: 1,
    borderColor: "#A7F3D0",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radii.pill,
    alignSelf: "flex-start",
    marginTop: 6,
  },
  authBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#059669",
    letterSpacing: 0.3,
  },
  facilityCard: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: 20,
    padding: spacing.md + 2,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    gap: spacing.md,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 1,
  },
  facilityIconCircle: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    alignItems: "center",
    justifyContent: "center",
  },
  facilityInfo: {
    flex: 1,
  },
  facilityKicker: {
    fontSize: 10,
    color: "#64748B",
    fontWeight: "700",
    letterSpacing: 0.8,
  },
  facilityName: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0F172A",
    marginTop: 2,
  },
  facilitySub: {
    fontSize: 11,
    color: "#64748B",
    marginTop: 2,
  },
  escalationCard: {
    backgroundColor: "#F8FAFC",
    borderRadius: 16,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    gap: 6,
  },
  escalationHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  escalationTitle: {
    fontSize: 11,
    color: "#475569",
    fontWeight: "700",
    letterSpacing: 0.8,
  },
  escalationBody: {
    fontSize: 11,
    color: "#64748B",
    lineHeight: 17,
  },
});
