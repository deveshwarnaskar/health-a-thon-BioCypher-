import React, { useState } from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { PatientScreenHeader } from "../components/PatientScreenHeader";
import { SignOutConfirmModal } from "../components/SignOutConfirmModal";
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
}: YouTabProps) {
  const { language, setLanguage } = useTranslation();
  const [showSignOutModal, setShowSignOutModal] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [showLanguagePicker, setShowLanguagePicker] = useState(false);

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
            <Text style={styles.menuIcon} allowFontScaling>
              💊
            </Text>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Prescribed Medications
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Clinician-authored treatment plans and doses
              </Text>
            </View>
            <Text style={styles.menuChevron} allowFontScaling>
              →
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={onNavigateToDocuments}
            accessibilityRole="button"
            accessibilityLabel="Documents & Reports"
          >
            <Text style={styles.menuIcon} allowFontScaling>
              📄
            </Text>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Documents & Reports
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Care summaries, clinic letters, and lab PDFs
              </Text>
            </View>
            <Text style={styles.menuChevron} allowFontScaling>
              →
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={onNavigateToNotifications}
            accessibilityRole="button"
            accessibilityLabel="Notification Reminders"
          >
            <Text style={styles.menuIcon} allowFontScaling>
              🔔
            </Text>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Notifications & Reminders
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Medication schedule and task alerts
              </Text>
            </View>
            <Text style={styles.menuChevron} allowFontScaling>
              →
            </Text>
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
            <Text style={styles.menuIcon} allowFontScaling>
              🌐
            </Text>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Language
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                {languages.find((l) => l.key === language)?.label || "English"}
              </Text>
            </View>
            <Text style={styles.menuChevron} allowFontScaling>
              {showLanguagePicker ? "▲" : "▼"}
            </Text>
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
                    <Text style={styles.checkCheck} allowFontScaling>
                      ✓
                    </Text>
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
  },
  profileCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
  },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: radii.pill,
    backgroundColor: colors.primary,
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
    backgroundColor: "#F0F7F9",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.sm,
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
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    minHeight: touchTarget.min,
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
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
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
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
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
    backgroundColor: "#F0F7F9",
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
    backgroundColor: "#F4F6F7",
    borderRadius: radii.md,
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
    backgroundColor: colors.surface,
    borderRadius: radii.md,
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
});
