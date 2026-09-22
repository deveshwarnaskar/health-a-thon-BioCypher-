import React, { useState } from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { PatientScreenHeader } from "../components/PatientScreenHeader";
import { SignOutConfirmModal } from "../components/SignOutConfirmModal";
import { WhatsAppManageModal } from "../components/WhatsAppManageModal";
import { useWhatsAppIdentity } from "../useWhatsAppIdentity";
import { useTranslation, type SupportedLanguage } from "../../../i18n/i18n";

export type YouTabProps = {
  patientName?: string;
  uhid?: string;
  email?: string;
  onSignOut: () => Promise<void>;
  onNavigateToMedications?: () => void;
  onNavigateToDocuments?: () => void;
  onNavigateToNotifications?: () => void;
  onOpenAssist?: () => void;
  onConnectWhatsApp?: () => void;
};

export function YouTab({
  patientName,
  uhid,
  email,
  onSignOut,
  onNavigateToMedications,
  onNavigateToDocuments,
  onNavigateToNotifications,
  onOpenAssist,
  onConnectWhatsApp,
}: YouTabProps) {
  const { t, language, setLanguage } = useTranslation();
  const [showSignOutModal, setShowSignOutModal] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [showLanguagePicker, setShowLanguagePicker] = useState(false);
  const [showWhatsAppManageModal, setShowWhatsAppManageModal] = useState(false);

  const { data: whatsAppIdentity, isOffline: isWhatsAppOffline } = useWhatsAppIdentity();

  const handleConfirmSignOut = async () => {
    setIsSigningOut(true);
    try {
      await onSignOut();
    } finally {
      setIsSigningOut(false);
      setShowSignOutModal(false);
    }
  };

  const languages: { key: SupportedLanguage; label: string }[] = [
    { key: "en", label: "English" },
    { key: "hi", label: "हिंदी (Hindi)" },
    { key: "bn", label: "বাংলা (Bengali)" },
    { key: "ta", label: "தமிழ் (Tamil)" },
    { key: "te", label: "తెలుగు (Telugu)" },
    { key: "mr", label: "मराठी (Marathi)" },
  ];

  return (
    <View style={styles.container}>
      <PatientScreenHeader
        title="Account & Care"
        subtitle="Manage your profile and clinical settings"
        onPressAssist={onOpenAssist}
      />

      <ScrollView contentContainerStyle={styles.content}>
        {/* Profile Card */}
        <View style={styles.profileCard}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText} allowFontScaling>
              {patientName ? patientName.charAt(0).toUpperCase() : "P"}
            </Text>
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.profileName} allowFontScaling>
              {patientName || "Patient Account"}
            </Text>
            {email ? (
              <Text style={styles.profileEmail} allowFontScaling>
                {email}
              </Text>
            ) : null}
            <View style={styles.roleRow}>
              <View style={styles.roleBadge}>
                <Text style={styles.roleBadgeText} allowFontScaling>
                  ROLE: PATIENT
                </Text>
              </View>
              {uhid ? (
                <Text style={styles.uhidText} allowFontScaling>
                  UHID: {uhid}
                </Text>
              ) : null}
            </View>
          </View>
        </View>

        {/* Section 1: Clinical Records */}
        <View style={styles.menuSection}>
          <Text style={styles.sectionHeader} allowFontScaling>
            CLINICAL RECORDS
          </Text>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={onNavigateToMedications}
            accessibilityRole="button"
            accessibilityLabel="Prescribed Medications"
          >
            <View style={styles.menuIconContainer}>
              <Ionicons name="medkit-outline" size={20} color={colors.primary} />
            </View>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Prescribed Medications
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Clinician-authored treatment plans and doses
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color="#94A3B8" />
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={onNavigateToDocuments}
            accessibilityRole="button"
            accessibilityLabel="Documents & Reports"
          >
            <View style={styles.menuIconContainer}>
              <Ionicons name="document-text-outline" size={20} color={colors.primary} />
            </View>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Documents & Reports
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Care summaries, clinic letters, and lab PDFs
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color="#94A3B8" />
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={onNavigateToNotifications}
            accessibilityRole="button"
            accessibilityLabel="Notification Reminders"
          >
            <View style={styles.menuIconContainer}>
              <Ionicons name="notifications-outline" size={20} color={colors.primary} />
            </View>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Notifications & Reminders
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Medication schedule and task alerts
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color="#94A3B8" />
          </TouchableOpacity>
        </View>

        {/* Section 2: Caregiver & Privacy (Placeholder for future support) */}
        <View style={styles.menuSection}>
          <Text style={styles.sectionHeader} allowFontScaling>
            PRIVACY & CARE TEAM ACCESS
          </Text>

          <View style={styles.infoBox}>
            <Text style={styles.infoBoxTitle} allowFontScaling>
              People Who Can Support You
            </Text>
            <Text style={styles.infoBoxText} allowFontScaling>
              No caregivers are currently connected. Delegated caregiver access requires verification by your clinic care coordinator.
            </Text>
          </View>
        </View>

        {/* Section: WhatsApp Integration */}
        <View style={styles.menuSection}>
          <Text style={styles.sectionHeader} allowFontScaling>
            {t("whatsapp.settingsSectionTitle")}
          </Text>

          {isWhatsAppOffline ? (
            <View style={styles.waCard}>
              <Text style={styles.waOfflineText} allowFontScaling>
                {t("whatsapp.statusUnavailableOffline")}
              </Text>
            </View>
          ) : whatsAppIdentity?.status === "connected" ? (
            <View style={styles.waCard}>
              <View style={styles.waHeaderRow}>
                <View style={styles.waStatusBadge}>
                  <Text style={styles.waStatusBadgeText} allowFontScaling>
                    ✓ {t("whatsapp.connectedStatus")}
                  </Text>
                </View>
                <Text style={styles.waPhoneText} allowFontScaling>
                  {whatsAppIdentity.phone_number_masked || whatsAppIdentity.phone_number}
                </Text>
              </View>
              <Text style={styles.waDescText} allowFontScaling>
                {t("whatsapp.connectedDesc")}
              </Text>
              <TouchableOpacity
                style={styles.waManageButton}
                onPress={() => setShowWhatsAppManageModal(true)}
                accessibilityRole="button"
                accessibilityLabel={t("whatsapp.manageButton")}
                activeOpacity={0.7}
              >
                <Text style={styles.waManageButtonText} allowFontScaling>
                  {t("whatsapp.manageButton")} →
                </Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.waCard}>
              <View style={styles.waHeaderRow}>
                <View style={styles.waNotConnectedBadge}>
                  <Text style={styles.waNotConnectedBadgeText} allowFontScaling>
                    {t("whatsapp.notConnectedStatus")}
                  </Text>
                </View>
              </View>
              <Text style={styles.waDescText} allowFontScaling>
                {t("whatsapp.notConnectedDesc")}
              </Text>
              <TouchableOpacity
                style={styles.waConnectButton}
                onPress={() => onConnectWhatsApp?.()}
                accessibilityRole="button"
                accessibilityLabel={t("whatsapp.connectButton")}
                activeOpacity={0.8}
              >
                <Text style={styles.waConnectButtonText} allowFontScaling>
                  + {t("whatsapp.connectButton")}
                </Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Section 3: Preferences & Language */}
        <View style={styles.menuSection}>
          <Text style={styles.sectionHeader} allowFontScaling>
            PREFERENCES
          </Text>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={() => setShowLanguagePicker(!showLanguagePicker)}
            accessibilityRole="button"
            accessibilityLabel={`Language: ${language}`}
          >
            <View style={styles.menuIconContainer}>
              <Ionicons name="globe-outline" size={20} color={colors.primary} />
            </View>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Language
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                {languages.find((l) => l.key === language)?.label || "English"}
              </Text>
            </View>
            <Ionicons
              name={showLanguagePicker ? "chevron-up" : "chevron-down"}
              size={16}
              color="#94A3B8"
            />
          </TouchableOpacity>

          {showLanguagePicker ? (
            <View style={styles.languagePickerBox}>
              {languages.map((lang) => (
                <TouchableOpacity
                  key={lang.key}
                  style={[
                    styles.langOption,
                    language === lang.key && styles.langOptionActive,
                  ]}
                  onPress={() => {
                    setLanguage(lang.key);
                    setShowLanguagePicker(false);
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={`Select ${lang.label}`}
                >
                  <Text
                    style={[
                      styles.langOptionText,
                      language === lang.key && styles.langOptionTextActive,
                    ]}
                    allowFontScaling
                  >
                    {lang.label}
                  </Text>
                  {language === lang.key ? (
                    <Ionicons name="checkmark" size={18} color={colors.primary} />
                  ) : null}
                </TouchableOpacity>
              ))}
            </View>
          ) : null}
        </View>

        {/* Section 4: Security & Sign Out */}
        <View style={styles.menuSection}>
          <Text style={styles.sectionHeader} allowFontScaling>
            SECURITY & SESSION
          </Text>

          <View style={styles.securityNoteBox}>
            <Text style={styles.securityNoteTitle} allowFontScaling>
              Protected Session
            </Text>
            <Text style={styles.securityNoteText} allowFontScaling>
              Your clinical telemetry session is signed with cryptographic keys and protected by server-side session rotation.
            </Text>
          </View>

          <TouchableOpacity
            style={styles.signOutButton}
            onPress={() => setShowSignOutModal(true)}
            accessibilityRole="button"
            accessibilityLabel="Sign out of THALI"
            accessibilityHint="Ends this session and returns to the sign-in screen"
          >
            <Ionicons name="log-out-outline" size={18} color="#DC2626" style={{ marginRight: 6 }} />
            <Text style={styles.signOutText} allowFontScaling>
              Sign out
            </Text>
          </TouchableOpacity>
        </View>

        <View style={styles.footerNote}>
          <Text style={styles.footerText} allowFontScaling>
            THALI × P.L.A.T.E. Healthcare Platform
          </Text>
          <Text style={styles.versionText} allowFontScaling>
            Version 0.1.0 · Clinical Telemetry & Intervention Logbook
          </Text>
        </View>
      </ScrollView>

      {/* Confirmation Modal */}
      <SignOutConfirmModal
        visible={showSignOutModal}
        onCancel={() => setShowSignOutModal(false)}
        onConfirm={handleConfirmSignOut}
        isSigningOut={isSigningOut}
      />

      {/* WhatsApp Manage Modal */}
      <WhatsAppManageModal
        visible={showWhatsAppManageModal}
        onClose={() => setShowWhatsAppManageModal(false)}
        identity={whatsAppIdentity}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    gap: spacing.lg,
    paddingBottom: 100,
  },
  profileCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.07,
    shadowRadius: 16,
    elevation: 2,
  },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: radii.pill,
    backgroundColor: colors.primaryInk,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  avatarText: {
    fontSize: 22,
    color: colors.textOnPrimary,
    fontWeight: typography.weight.bold,
  },
  profileInfo: {
    flex: 1,
  },
  profileName: {
    fontSize: typography.fontSize.headline,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  profileEmail: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  roleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginTop: 4,
    flexWrap: "wrap",
  },
  roleBadge: {
    backgroundColor: colors.tileAqua,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  roleBadgeText: {
    fontSize: 10,
    fontWeight: typography.weight.bold,
    color: colors.primary,
    letterSpacing: 0.5,
  },
  uhidText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    fontWeight: typography.weight.medium,
  },
  menuSection: {
    gap: spacing.xs,
  },
  sectionHeader: {
    fontSize: 11,
    fontWeight: typography.weight.bold,
    color: colors.textSecondary,
    letterSpacing: 1.2,
    marginBottom: 4,
    marginLeft: 4,
  },
  menuItem: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    minHeight: touchTarget.min,
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.05,
    shadowRadius: 14,
    elevation: 1,
  },
  menuIconContainer: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: "rgba(13, 148, 136, 0.08)",
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.sm,
  },
  menuIcon: {
    fontSize: 20,
    marginRight: spacing.md,
  },
  menuTextColumn: {
    flex: 1,
  },
  menuTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  menuSubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  menuChevron: {
    fontSize: 16,
    color: colors.textSecondary,
    marginLeft: spacing.xs,
  },
  infoBox: {
    backgroundColor: colors.tileAqua,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    padding: spacing.md,
  },
  infoBoxTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    marginBottom: 4,
  },
  infoBoxText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  languagePickerBox: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    padding: spacing.xs,
    marginTop: 4,
  },
  langOption: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radii.sm,
    minHeight: touchTarget.min,
  },
  langOptionActive: {
    backgroundColor: colors.tileAqua,
  },
  langOptionText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textPrimary,
  },
  langOptionTextActive: {
    fontWeight: typography.weight.bold,
    color: colors.primary,
  },
  checkCheck: {
    fontSize: 16,
    color: colors.primary,
    fontWeight: "bold",
  },
  securityNoteBox: {
    backgroundColor: colors.tileCream,
    borderRadius: radii.lg,
    padding: spacing.md,
    marginBottom: spacing.xs,
  },
  securityNoteTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    marginBottom: 2,
  },
  securityNoteText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  signOutButton: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.critical,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.xs,
  },
  signOutText: {
    color: colors.critical,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
  },
  footerNote: {
    alignItems: "center",
    marginTop: spacing.sm,
    marginBottom: spacing.lg,
  },
  footerText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.semibold,
    color: colors.textSecondary,
  },
  versionText: {
    fontSize: 11,
    color: colors.disabled,
    marginTop: 2,
  },
  waCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    gap: spacing.xs,
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 1,
  },
  waHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  waStatusBadge: {
    backgroundColor: "#DCF8C6",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  waStatusBadgeText: {
    color: "#075E54",
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
  },
  waNotConnectedBadge: {
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  waNotConnectedBadgeText: {
    color: colors.textSecondary,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.semibold,
  },
  waPhoneText: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  waDescText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
    marginVertical: 2,
  },
  waManageButton: {
    alignSelf: "flex-start",
    marginTop: spacing.xs,
    paddingVertical: 4,
  },
  waManageButtonText: {
    color: "#128C7E",
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
  },
  waConnectButton: {
    alignSelf: "flex-start",
    marginTop: spacing.xs,
    backgroundColor: "#128C7E",
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    borderRadius: radii.pill,
    minHeight: touchTarget.min,
    justifyContent: "center",
  },
  waConnectButtonText: {
    color: "#FFFFFF",
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
  },
  waOfflineText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    fontStyle: "italic",
  },
});
