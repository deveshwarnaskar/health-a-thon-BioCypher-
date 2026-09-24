import React from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { touchTarget } from "../../../theming/tokens";
import {
  doctorPalette,
  doctorRadii,
  doctorSoftShadow,
  doctorPillShadow,
} from "../doctorDesign";

export type DoctorSubWorkspaceKey =
  | "monitoring"
  | "reports"
  | "plans"
  | "documents"
  | "messages"
  | "audit";

export type DoctorWorkspaceHubTabProps = {
  doctorName?: string | null;
  facilityId?: string | null;
  onSelectWorkspace: (key: DoctorSubWorkspaceKey) => void;
  onSignOut?: () => void;
};

type WorkspaceItem = {
  key: DoctorSubWorkspaceKey;
  title: string;
  description: string;
  icon: keyof typeof Ionicons.glyphMap;
  iconBg: string;
  iconColor: string;
  badge?: string;
};

const WORKSPACES: WorkspaceItem[] = [
  {
    key: "monitoring",
    title: "Longitudinal Monitoring",
    description:
      "Continuous glucose telemetry, ADA/EASD TIR metrics, and excursion tracking across the cohort.",
    icon: "analytics",
    iconBg: "#F5F3FF",
    iconColor: "#7C3AED",
    badge: "Telemetry",
  },
  {
    key: "reports",
    title: "Clinical Reports Generator",
    description:
      "Generate authoritative server-side PDF reports, weekly glycemic summaries, and consultation documents.",
    icon: "document-text",
    iconBg: "#EFF6FF",
    iconColor: "#2563EB",
    badge: "Authoritative",
  },
  {
    key: "plans",
    title: "Medication Regimens & Plans",
    description:
      "Author clinician-guided titration plans, review active prescriptions, and inspect dose schedules.",
    icon: "medkit",
    iconBg: "#F0FDF4",
    iconColor: "#16A34A",
  },
  {
    key: "documents",
    title: "Clinical Document Vault",
    description:
      "Inspect diagnostic charts, external lab panels, and patient-uploaded hospital records.",
    icon: "folder-open",
    iconBg: "#FFFBEB",
    iconColor: "#D97706",
  },
  {
    key: "messages",
    title: "Patient Communications",
    description:
      "Review WhatsApp notification delivery status, automated reminder queues, and outreach logs.",
    icon: "chatbubbles",
    iconBg: "#F0FDFA",
    iconColor: "#0D9488",
  },
  {
    key: "audit",
    title: "Security & Audit Trail",
    description:
      "Immutable access logs, digital signatures, AI verification records, and operator timestamps.",
    icon: "shield-checkmark",
    iconBg: "#EEF2FF",
    iconColor: "#4F46E5",
    badge: "FHIR Log",
  },
];

export function DoctorWorkspaceHubTab({
  doctorName: propDoctorName,
  facilityId: propFacilityId,
  onSelectWorkspace,
  onSignOut,
}: DoctorWorkspaceHubTabProps) {
  const doctorName = propDoctorName || "Doctor";
  const facilityId = propFacilityId || "Facility 1";
  const initial = doctorName.replace(/^Dr\.\s*/i, "").charAt(0).toUpperCase() || "D";

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* 1. Doctor Profile Hero Card (matching rightmost screen of reference) */}
      <View style={styles.profileCard}>
        <View style={styles.profileTopRow}>
          <View style={styles.profileAvatar}>
            <Text style={styles.profileAvatarText} allowFontScaling>
              {initial}
            </Text>
          </View>
          <View style={styles.profileInfoCol}>
            <View style={styles.nameBadgeRow}>
              <Text style={styles.profileDoctorName} numberOfLines={1} allowFontScaling>
                Dr. {doctorName}
              </Text>
              <Ionicons name="checkmark-circle" size={18} color={doctorPalette.primary} />
            </View>
            <Text style={styles.profileSpecialty} allowFontScaling>
              Endocrinology & Diabetology
            </Text>
            <Text style={styles.profileFacility} allowFontScaling>
              {facilityId} · P.L.A.T.E. Clinical v2.4
            </Text>
          </View>
        </View>

        {/* 3-Column Stats Row (matching reference screen stats) */}
        <View style={styles.statsPillRow}>
          {/* Stat 1 */}
          <View style={styles.statColumn}>
            <View style={[styles.statIconCircle, { backgroundColor: doctorPalette.surfaceBlue }]}>
              <Ionicons name="people" size={16} color={doctorPalette.primary} />
            </View>
            <Text style={styles.statNumber} allowFontScaling>
              Active
            </Text>
            <Text style={styles.statLabel} allowFontScaling>
              Cohort
            </Text>
          </View>

          {/* Stat 2 */}
          <View style={styles.statColumn}>
            <View style={[styles.statIconCircle, { backgroundColor: doctorPalette.limeSoft }]}>
              <Ionicons name="shield-checkmark" size={16} color="#15803D" />
            </View>
            <Text style={styles.statNumber} allowFontScaling>
              100%
            </Text>
            <Text style={styles.statLabel} allowFontScaling>
              Deterministic
            </Text>
          </View>

          {/* Stat 3 */}
          <View style={styles.statColumn}>
            <View style={[styles.statIconCircle, { backgroundColor: "#FEF3C7" }]}>
              <Ionicons name="pulse" size={16} color="#D97706" />
            </View>
            <Text style={styles.statNumber} allowFontScaling>
              14-Day
            </Text>
            <Text style={styles.statLabel} allowFontScaling>
              TIR Window
            </Text>
          </View>
        </View>
      </View>

      {/* 2. Specialized Workstations Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle} allowFontScaling>
          Clinical Workstations & Vaults
        </Text>

        <View style={styles.workspaceList}>
          {WORKSPACES.map((item) => (
            <TouchableOpacity
              key={item.key}
              style={styles.workspaceCard}
              onPress={() => onSelectWorkspace(item.key)}
              accessibilityRole="button"
              accessibilityLabel={`Open ${item.title}`}
              activeOpacity={0.75}
            >
              <View style={[styles.iconBox, { backgroundColor: item.iconBg }]}>
                <Ionicons name={item.icon} size={22} color={item.iconColor} />
              </View>

              <View style={styles.workspaceTextCol}>
                <View style={styles.cardHeaderRow}>
                  <Text style={styles.workspaceTitle} allowFontScaling numberOfLines={1}>
                    {item.title}
                  </Text>
                  {item.badge ? (
                    <View style={styles.tagBadge}>
                      <Text style={styles.tagBadgeText} allowFontScaling>
                        {item.badge}
                      </Text>
                    </View>
                  ) : null}
                </View>
                <Text style={styles.workspaceDescription} allowFontScaling>
                  {item.description}
                </Text>
              </View>

              <View style={styles.circleArrowBtn}>
                <Ionicons name="arrow-forward" size={15} color={doctorPalette.ink} />
              </View>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* 3. Session Security & Sign Out Section */}
      {onSignOut ? (
        <View style={styles.signOutCard}>
          <TouchableOpacity
            style={styles.signOutButton}
            onPress={onSignOut}
            accessibilityRole="button"
            accessibilityLabel="Sign out of doctor clinical session"
            activeOpacity={0.85}
          >
            <Ionicons name="log-out-outline" size={18} color="#EF4444" />
            <Text style={styles.signOutButtonText} allowFontScaling>
              Sign Out of Clinical Session
            </Text>
          </TouchableOpacity>
          <Text style={styles.securityFootnote} allowFontScaling>
            Secured under HIPAA, FHIR, and cryptographic OIDC token lifecycle management.
          </Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: doctorPalette.appBackground,
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 4,
    gap: 20,
    paddingBottom: 110,
  },
  profileCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 26,
    padding: 20,
    gap: 18,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    ...doctorSoftShadow,
  },
  profileTopRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  profileAvatar: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: doctorPalette.surfaceLime,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: doctorPalette.borderSubtle,
    ...doctorSoftShadow,
  },
  profileAvatarText: {
    fontSize: 24,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  profileInfoCol: {
    flex: 1,
  },
  nameBadgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  profileDoctorName: {
    fontSize: 20,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.2,
    flexShrink: 1,
  },
  profileSpecialty: {
    fontSize: 13,
    color: doctorPalette.inkSecondary,
    marginTop: 2,
  },
  profileFacility: {
    fontSize: 11,
    color: doctorPalette.muted,
    marginTop: 2,
  },
  statsPillRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    backgroundColor: doctorPalette.appBackground,
    borderRadius: 20,
    paddingVertical: 14,
    paddingHorizontal: 12,
  },
  statColumn: {
    flex: 1,
    alignItems: "center",
    gap: 4,
  },
  statIconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 2,
  },
  statNumber: {
    fontSize: 15,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  statLabel: {
    fontSize: 11,
    fontWeight: "500",
    color: doctorPalette.muted,
  },
  section: {
    gap: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.2,
  },
  workspaceList: {
    gap: 12,
  },
  workspaceCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 16,
    ...doctorSoftShadow,
  },
  iconBox: {
    width: 46,
    height: 46,
    borderRadius: 23,
    alignItems: "center",
    justifyContent: "center",
  },
  workspaceTextCol: {
    flex: 1,
  },
  cardHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  workspaceTitle: {
    fontSize: 15,
    fontWeight: "800",
    color: doctorPalette.ink,
    flexShrink: 1,
  },
  tagBadge: {
    backgroundColor: doctorPalette.limeSoft,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: doctorRadii.pill,
  },
  tagBadgeText: {
    fontSize: 9,
    fontWeight: "800",
    color: "#15803D",
  },
  workspaceDescription: {
    fontSize: 12,
    color: doctorPalette.muted,
    marginTop: 2,
    lineHeight: 16,
  },
  circleArrowBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: doctorPalette.appBackground,
    alignItems: "center",
    justifyContent: "center",
  },
  signOutCard: {
    marginTop: 8,
    gap: 8,
    alignItems: "center",
  },
  signOutButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: doctorPalette.criticalSoft,
    borderWidth: 1,
    borderColor: "#FECACA",
    borderRadius: doctorRadii.pill,
    minHeight: touchTarget.min,
    paddingHorizontal: 20,
    width: "100%",
  },
  signOutButtonText: {
    color: "#EF4444",
    fontSize: 14,
    fontWeight: "800",
  },
  securityFootnote: {
    fontSize: 11,
    color: doctorPalette.muted,
    textAlign: "center",
    marginTop: 2,
  },
});
