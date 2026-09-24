import React, { useState } from "react";
import {
  Modal,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../auth/AuthProvider";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { caregiverPalette, caregiverRadii, caregiverShadow } from "./caregiverDesign";
import type { CaregiverPatientListItem } from "../../services/schemas/caregiver";

export type CaregiverAccountModalProps = {
  visible: boolean;
  onClose: () => void;
  patients: CaregiverPatientListItem[];
  onOpenLinkModal?: () => void;
  onSignOut?: () => void;
  testID?: string;
};

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "CG";
  const first = parts[0] ?? "";
  if (parts.length === 1) return first.slice(0, 2).toUpperCase() || "CG";
  const last = parts[parts.length - 1] ?? "";
  return ((first[0] ?? "") + (last[0] ?? "")).toUpperCase() || "CG";
}

export function CaregiverAccountModal({
  visible,
  onClose,
  patients,
  onOpenLinkModal,
  onSignOut,
  testID = "caregiver-account-modal",
}: CaregiverAccountModalProps) {
  const { state, signOut } = useAuth();
  const authUser = state.name === "authenticated" ? state.user : null;
  const caregiverEmail = authUser?.email ?? "caregiver@plate.org";
  const caregiverName = (authUser as any)?.name || caregiverEmail.split("@")[0] || "Caregiver";
  const initials = getInitials(caregiverName);
  const actorId = authUser?.actor_id || "CG-ACTIVE";

  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [criticalAlertsEnabled, setCriticalAlertsEnabled] = useState(true);
  const [showSignOutConfirm, setShowSignOutConfirm] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);

  const handleSignOut = async () => {
    setIsSigningOut(true);
    try {
      if (onSignOut) {
        onSignOut();
      } else {
        await signOut();
      }
    } finally {
      setIsSigningOut(false);
      setShowSignOutConfirm(false);
      onClose();
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
      testID={testID}
    >
      <View style={styles.overlay}>
        <TouchableOpacity style={styles.backdrop} activeOpacity={1} onPress={onClose} />

        <View style={styles.sheetContainer}>
          {/* Grab Handle */}
          <View style={styles.sheetHandleRow}>
            <View style={styles.sheetHandle} />
          </View>

          {/* Modal Header */}
          <View style={styles.header}>
            <View style={styles.headerLeft}>
              <View style={styles.headerIconCircle}>
                <Ionicons name="shield-checkmark" size={18} color={caregiverPalette.primary} />
              </View>
              <View>
                <Text style={styles.headerTitle} allowFontScaling>
                  Caregiver Account
                </Text>
                <Text style={styles.headerSubtitle} allowFontScaling>
                  Identity, clinical authorizations & preferences
                </Text>
              </View>
            </View>

            <TouchableOpacity
              onPress={onClose}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              style={styles.closeButton}
              accessibilityRole="button"
              accessibilityLabel="Close account modal"
            >
              <Ionicons name="close" size={20} color={caregiverPalette.muted} />
            </TouchableOpacity>
          </View>

          <ScrollView
            contentContainerStyle={styles.scrollBody}
            showsVerticalScrollIndicator={false}
          >
            {/* Caregiver Identity Card */}
            <View style={styles.profileCard}>
              <View style={styles.profileTopRow}>
                <View style={styles.avatarContainer}>
                  <View style={styles.avatarCircle}>
                    <Text style={styles.avatarInitials} allowFontScaling>
                      {initials}
                    </Text>
                  </View>
                  <View style={styles.onlineBadge}>
                    <View style={styles.onlineDot} />
                  </View>
                </View>

                <View style={styles.profileDetails}>
                  <View style={styles.verifiedRow}>
                    <Text style={styles.profileName} numberOfLines={1} allowFontScaling>
                      {caregiverName}
                    </Text>
                    <View style={styles.verifiedPill}>
                      <Ionicons name="shield-checkmark" size={11} color={caregiverPalette.emeraldDark} />
                      <Text style={styles.verifiedPillText} allowFontScaling>
                        Verified
                      </Text>
                    </View>
                  </View>

                  <Text style={styles.profileEmail} numberOfLines={1} allowFontScaling>
                    {caregiverEmail}
                  </Text>

                  <View style={styles.actorIdRow}>
                    <Text style={styles.actorIdLabel}>Caregiver ID:</Text>
                    <View style={styles.actorIdChip}>
                      <Text style={styles.actorIdText} allowFontScaling>
                        {actorId}
                      </Text>
                    </View>
                  </View>
                </View>
              </View>

              {/* Status & Security Metrics Grid */}
              <View style={styles.metricsRow}>
                <View style={styles.metricItem}>
                  <Text style={styles.metricValue} allowFontScaling>
                    {patients.length}
                  </Text>
                  <Text style={styles.metricTitle} allowFontScaling>
                    Patients Linked
                  </Text>
                </View>

                <View style={styles.metricDivider} />

                <View style={styles.metricItem}>
                  <Text style={[styles.metricValue, { color: caregiverPalette.emeraldDark }]} allowFontScaling>
                    Active
                  </Text>
                  <Text style={styles.metricTitle} allowFontScaling>
                    Delegation State
                  </Text>
                </View>

                <View style={styles.metricDivider} />

                <View style={styles.metricItem}>
                  <Text style={[styles.metricValue, { color: caregiverPalette.sky }]} allowFontScaling>
                    256-bit
                  </Text>
                  <Text style={styles.metricTitle} allowFontScaling>
                    Encrypted Care
                  </Text>
                </View>
              </View>
            </View>

            {/* Section: Authorized Patients Management */}
            <View style={styles.sectionCard}>
              <View style={styles.sectionHeaderRow}>
                <View style={styles.sectionHeaderTitleRow}>
                  <Ionicons name="people" size={15} color={caregiverPalette.primary} />
                  <Text style={styles.sectionTitle} allowFontScaling>
                    Authorized Patient Relationships
                  </Text>
                </View>
                {onOpenLinkModal ? (
                  <TouchableOpacity
                    style={styles.addPatientSmallBtn}
                    onPress={() => {
                      onClose();
                      onOpenLinkModal();
                    }}
                    accessibilityRole="button"
                    accessibilityLabel="Add patient"
                  >
                    <Ionicons name="add" size={13} color={caregiverPalette.primary} />
                    <Text style={styles.addPatientSmallText} allowFontScaling>
                      + Link New
                    </Text>
                  </TouchableOpacity>
                ) : null}
              </View>

              {patients.length === 0 ? (
                <View style={styles.emptyPatientsBox}>
                  <Ionicons name="heart-dislike-outline" size={24} color={caregiverPalette.muted} />
                  <Text style={styles.emptyPatientsText} allowFontScaling>
                    No patients currently linked to this caregiver account.
                  </Text>
                </View>
              ) : (
                <View style={styles.patientRowsContainer}>
                  {patients.map((pat) => (
                    <View key={pat.patient_id} style={styles.patientRowItem}>
                      <View style={styles.patientRowLeft}>
                        <View style={styles.patientMiniAvatar}>
                          <Text style={styles.patientMiniAvatarText}>
                            {getInitials(pat.name)}
                          </Text>
                        </View>
                        <View style={styles.patientRowDetails}>
                          <Text style={styles.patientRowName} allowFontScaling>
                            {pat.name}
                          </Text>
                          <View style={styles.patientRowMeta}>
                            <Text style={styles.patientRowRel}>
                              {pat.relationship_label || "Family Care"}
                            </Text>
                            <Text style={styles.metaDot}>•</Text>
                            <Text style={styles.patientRowStatus}>Authorized</Text>
                          </View>
                        </View>
                      </View>

                      <View style={styles.patientRowCapabilities}>
                        <View style={styles.scopeMiniPill}>
                          <Ionicons name="water" size={10} color={caregiverPalette.sky} />
                          <Text style={styles.scopeMiniText}>Glucose</Text>
                        </View>
                        <View style={styles.scopeMiniPill}>
                          <Ionicons name="restaurant" size={10} color={caregiverPalette.amberDark} />
                          <Text style={styles.scopeMiniText}>Meals</Text>
                        </View>
                      </View>
                    </View>
                  ))}
                </View>
              )}

              {/* Information Asymmetry Notice */}
              <View style={styles.privacyExplainer}>
                <Ionicons name="lock-closed" size={14} color={caregiverPalette.tealDark} />
                <Text style={styles.privacyExplainerText} allowFontScaling>
                  <Text style={styles.boldText}>Information Asymmetry Protection:</Text> Medical diagnoses, prescriptions, and physician internal risk scores remain confidential. Family caregivers receive daily meal intake, sugar logs, and routine tasks to assist loved ones safely.
                </Text>
              </View>
            </View>

            {/* Section: Caregiver Notifications & Preferences */}
            <View style={styles.sectionCard}>
              <View style={styles.sectionHeaderTitleRow}>
                <Ionicons name="settings-outline" size={15} color={caregiverPalette.primary} />
                <Text style={styles.sectionTitle} allowFontScaling>
                  Caregiver Care Preferences
                </Text>
              </View>

              <TouchableOpacity
                style={styles.settingToggleRow}
                onPress={() => setNotificationsEnabled(!notificationsEnabled)}
                activeOpacity={0.8}
              >
                <View style={styles.settingTextCol}>
                  <Text style={styles.settingLabel} allowFontScaling>
                    Daily Routine & Meal Reminders
                  </Text>
                  <Text style={styles.settingDesc} allowFontScaling>
                    Alerts for breakfast, lunch, and dinner care logging
                  </Text>
                </View>
                <View
                  style={[
                    styles.toggleSwitch,
                    notificationsEnabled && styles.toggleSwitchActive,
                  ]}
                >
                  <View
                    style={[
                      styles.toggleKnob,
                      notificationsEnabled && styles.toggleKnobActive,
                    ]}
                  />
                </View>
              </TouchableOpacity>

              <View style={styles.settingDivider} />

              <TouchableOpacity
                style={styles.settingToggleRow}
                onPress={() => setCriticalAlertsEnabled(!criticalAlertsEnabled)}
                activeOpacity={0.8}
              >
                <View style={styles.settingTextCol}>
                  <Text style={styles.settingLabel} allowFontScaling>
                    Critical Blood Sugar Alerts
                  </Text>
                  <Text style={styles.settingDesc} allowFontScaling>
                    Immediate warning if patient logs &lt;70 or &gt;250 mg/dL
                  </Text>
                </View>
                <View
                  style={[
                    styles.toggleSwitch,
                    criticalAlertsEnabled && styles.toggleSwitchActive,
                  ]}
                >
                  <View
                    style={[
                      styles.toggleKnob,
                      criticalAlertsEnabled && styles.toggleKnobActive,
                    ]}
                  />
                </View>
              </TouchableOpacity>

              <View style={styles.settingDivider} />

              <View style={styles.settingStaticRow}>
                <View style={styles.settingTextCol}>
                  <Text style={styles.settingLabel} allowFontScaling>
                    Standard Glucose Unit
                  </Text>
                  <Text style={styles.settingDesc} allowFontScaling>
                    Indian Clinical Standard (ICMR guideline)
                  </Text>
                </View>
                <View style={styles.unitBadge}>
                  <Text style={styles.unitBadgeText} allowFontScaling>
                    mg/dL
                  </Text>
                </View>
              </View>
            </View>

            {/* Section: Clinical Support & Account Security */}
            <View style={styles.sectionCard}>
              <View style={styles.sectionHeaderTitleRow}>
                <Ionicons name="help-buoy-outline" size={15} color={caregiverPalette.primary} />
                <Text style={styles.sectionTitle} allowFontScaling>
                  Support & Verification
                </Text>
              </View>

              <View style={styles.supportRow}>
                <View style={styles.supportIconCircle}>
                  <Ionicons name="call-outline" size={16} color={caregiverPalette.primary} />
                </View>
                <View style={styles.supportTextCol}>
                  <Text style={styles.supportTitle} allowFontScaling>
                    THALI Clinical Desk
                  </Text>
                  <Text style={styles.supportSubtitle} allowFontScaling>
                    Need to link a patient without UHID or adjust relationships? Contact coordinator.
                  </Text>
                </View>
              </View>

              <View style={styles.settingDivider} />

              {/* Sign Out Trigger */}
              {showSignOutConfirm ? (
                <View style={styles.signOutConfirmBox}>
                  <Text style={styles.signOutConfirmTitle} allowFontScaling>
                    Are you sure you want to sign out?
                  </Text>
                  <Text style={styles.signOutConfirmDesc} allowFontScaling>
                    You will need your caregiver credentials to sign back in.
                  </Text>
                  <View style={styles.signOutButtonsRow}>
                    <TouchableOpacity
                      style={styles.cancelSignOutBtn}
                      onPress={() => setShowSignOutConfirm(false)}
                    >
                      <Text style={styles.cancelSignOutText} allowFontScaling>
                        Cancel
                      </Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.confirmSignOutBtn}
                      onPress={handleSignOut}
                      disabled={isSigningOut}
                    >
                      <Text style={styles.confirmSignOutText} allowFontScaling>
                        {isSigningOut ? "Signing Out…" : "Yes, Sign Out"}
                      </Text>
                    </TouchableOpacity>
                  </View>
                </View>
              ) : (
                <TouchableOpacity
                  style={styles.signOutRow}
                  onPress={() => setShowSignOutConfirm(true)}
                  activeOpacity={0.7}
                  accessibilityRole="button"
                  accessibilityLabel="Sign out"
                >
                  <View style={styles.signOutLeft}>
                    <Ionicons name="log-out-outline" size={18} color={caregiverPalette.rose} />
                    <Text style={styles.signOutText} allowFontScaling>
                      Sign Out of Caregiver Account
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={16} color={caregiverPalette.muted} />
                </TouchableOpacity>
              )}
            </View>

            <View style={styles.footerNote}>
              <Text style={styles.footerVersion} allowFontScaling>
                THALI x P.L.A.T.E. Healthcare Companion • Caregiver Portal v2.4
              </Text>
            </View>
          </ScrollView>
        </View>
      </View>
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
    backgroundColor: caregiverPalette.appBackground,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: "92%",
    paddingBottom: spacing.lg,
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
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: caregiverPalette.border,
    backgroundColor: caregiverPalette.surface,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    flex: 1,
  },
  headerIconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: caregiverPalette.tealSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: caregiverPalette.ink,
  },
  headerSubtitle: {
    fontSize: 11,
    color: caregiverPalette.muted,
    marginTop: 1,
  },
  closeButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: caregiverPalette.surfaceSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  scrollBody: {
    padding: 16,
    gap: 14,
    paddingBottom: spacing.xxl,
  },
  profileCard: {
    backgroundColor: caregiverPalette.surface,
    borderRadius: caregiverRadii.lg,
    padding: 16,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    gap: 14,
    ...caregiverShadow.card,
  },
  profileTopRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  avatarContainer: {
    position: "relative",
  },
  avatarCircle: {
    width: 58,
    height: 58,
    borderRadius: 29,
    backgroundColor: caregiverPalette.surfaceTeal,
    borderWidth: 2,
    borderColor: caregiverPalette.tealSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarInitials: {
    fontSize: 20,
    fontWeight: "800",
    color: caregiverPalette.tealDark,
    letterSpacing: 0.5,
  },
  onlineBadge: {
    position: "absolute",
    bottom: 0,
    right: 0,
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: caregiverPalette.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  onlineDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: caregiverPalette.emerald,
  },
  profileDetails: {
    flex: 1,
    gap: 3,
  },
  verifiedRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flexWrap: "wrap",
  },
  profileName: {
    fontSize: 17,
    fontWeight: "800",
    color: caregiverPalette.ink,
  },
  verifiedPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    backgroundColor: caregiverPalette.emeraldSoft,
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: caregiverRadii.pill,
    borderWidth: 1,
    borderColor: caregiverPalette.emeraldBorder,
  },
  verifiedPillText: {
    fontSize: 10,
    fontWeight: "700",
    color: caregiverPalette.emeraldDark,
  },
  profileEmail: {
    fontSize: 13,
    color: caregiverPalette.muted,
  },
  actorIdRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 2,
  },
  actorIdLabel: {
    fontSize: 11,
    color: caregiverPalette.muted,
    fontWeight: "500",
  },
  actorIdChip: {
    backgroundColor: caregiverPalette.surfaceSoft,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
  },
  actorIdText: {
    fontSize: 11,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
    fontWeight: "700",
    color: caregiverPalette.inkSecondary,
  },
  metricsRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: caregiverPalette.surfaceSoft,
    borderRadius: caregiverRadii.md,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  metricItem: {
    flex: 1,
    alignItems: "center",
    gap: 2,
  },
  metricValue: {
    fontSize: 16,
    fontWeight: "800",
    color: caregiverPalette.ink,
  },
  metricTitle: {
    fontSize: 10,
    fontWeight: "600",
    color: caregiverPalette.muted,
  },
  metricDivider: {
    width: 1,
    height: 24,
    backgroundColor: caregiverPalette.borderHighlight,
  },
  sectionCard: {
    backgroundColor: caregiverPalette.surface,
    borderRadius: caregiverRadii.lg,
    padding: 16,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    gap: 12,
    ...caregiverShadow.card,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  sectionHeaderTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: caregiverPalette.ink,
    letterSpacing: 0.2,
  },
  addPatientSmallBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: caregiverRadii.pill,
    backgroundColor: caregiverPalette.primaryLight,
  },
  addPatientSmallText: {
    fontSize: 11,
    fontWeight: "700",
    color: caregiverPalette.primary,
  },
  emptyPatientsBox: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 18,
    gap: 6,
  },
  emptyPatientsText: {
    fontSize: 12,
    color: caregiverPalette.muted,
    textAlign: "center",
  },
  patientRowsContainer: {
    gap: 8,
  },
  patientRowItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: caregiverPalette.surfaceMuted,
    borderRadius: caregiverRadii.md,
    padding: 10,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
  },
  patientRowLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    flex: 1,
  },
  patientMiniAvatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: caregiverPalette.skySoft,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: caregiverPalette.skyBorder,
  },
  patientMiniAvatarText: {
    fontSize: 12,
    fontWeight: "700",
    color: caregiverPalette.sky,
  },
  patientRowDetails: {
    gap: 2,
    flex: 1,
  },
  patientRowName: {
    fontSize: 13,
    fontWeight: "700",
    color: caregiverPalette.ink,
  },
  patientRowMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  patientRowRel: {
    fontSize: 11,
    color: caregiverPalette.muted,
    fontWeight: "500",
  },
  metaDot: {
    fontSize: 10,
    color: caregiverPalette.borderHighlight,
  },
  patientRowStatus: {
    fontSize: 11,
    color: caregiverPalette.emeraldDark,
    fontWeight: "600",
  },
  patientRowCapabilities: {
    flexDirection: "row",
    gap: 4,
  },
  scopeMiniPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    backgroundColor: caregiverPalette.surface,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: caregiverRadii.pill,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
  },
  scopeMiniText: {
    fontSize: 9,
    fontWeight: "700",
    color: caregiverPalette.inkSecondary,
  },
  privacyExplainer: {
    flexDirection: "row",
    gap: 8,
    backgroundColor: caregiverPalette.surfaceTeal,
    borderRadius: caregiverRadii.sm,
    padding: 10,
    borderWidth: 1,
    borderColor: caregiverPalette.tealSoft,
    alignItems: "flex-start",
  },
  privacyExplainerText: {
    flex: 1,
    fontSize: 11,
    color: caregiverPalette.tealDark,
    lineHeight: 16,
  },
  boldText: {
    fontWeight: "700",
  },
  settingToggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 4,
  },
  settingStaticRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 4,
  },
  settingTextCol: {
    flex: 1,
    gap: 2,
    marginRight: 10,
  },
  settingLabel: {
    fontSize: 13,
    fontWeight: "700",
    color: caregiverPalette.ink,
  },
  settingDesc: {
    fontSize: 11,
    color: caregiverPalette.muted,
  },
  settingDivider: {
    height: 1,
    backgroundColor: caregiverPalette.border,
    marginVertical: 2,
  },
  toggleSwitch: {
    width: 44,
    height: 24,
    borderRadius: 12,
    backgroundColor: caregiverPalette.borderHighlight,
    padding: 2,
    justifyContent: "center",
  },
  toggleSwitchActive: {
    backgroundColor: caregiverPalette.primary,
  },
  toggleKnob: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: caregiverPalette.surface,
  },
  toggleKnobActive: {
    alignSelf: "flex-end",
  },
  unitBadge: {
    backgroundColor: caregiverPalette.surfaceSoft,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: caregiverRadii.sm,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
  },
  unitBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: caregiverPalette.ink,
  },
  supportRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
    paddingVertical: 4,
  },
  supportIconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: caregiverPalette.primaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
  },
  supportTextCol: {
    flex: 1,
    gap: 2,
  },
  supportTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: caregiverPalette.ink,
  },
  supportSubtitle: {
    fontSize: 11,
    color: caregiverPalette.muted,
    lineHeight: 16,
  },
  signOutRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 6,
  },
  signOutLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  signOutText: {
    fontSize: 13,
    fontWeight: "700",
    color: caregiverPalette.rose,
  },
  signOutConfirmBox: {
    backgroundColor: caregiverPalette.surfaceRose,
    borderRadius: caregiverRadii.md,
    padding: 12,
    borderWidth: 1,
    borderColor: caregiverPalette.roseBorder,
    gap: 8,
  },
  signOutConfirmTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: caregiverPalette.roseDark,
  },
  signOutConfirmDesc: {
    fontSize: 11,
    color: caregiverPalette.inkSecondary,
  },
  signOutButtonsRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 4,
  },
  cancelSignOutBtn: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: caregiverRadii.sm,
    backgroundColor: caregiverPalette.surface,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    alignItems: "center",
  },
  cancelSignOutText: {
    fontSize: 12,
    fontWeight: "600",
    color: caregiverPalette.inkSecondary,
  },
  confirmSignOutBtn: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: caregiverRadii.sm,
    backgroundColor: caregiverPalette.rose,
    alignItems: "center",
  },
  confirmSignOutText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  footerNote: {
    alignItems: "center",
    paddingTop: 8,
  },
  footerVersion: {
    fontSize: 10,
    color: caregiverPalette.subtle,
  },
});
