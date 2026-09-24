import React, { useEffect, useState } from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import * as SecureStore from "expo-secure-store";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { useAuth } from "../../../auth/AuthProvider";
import { PatientScreenHeader } from "../components/PatientScreenHeader";
import { SignOutConfirmModal } from "../components/SignOutConfirmModal";
import { DeleteAccountModal } from "../components/DeleteAccountModal";
import { WhatsAppManageModal } from "../components/WhatsAppManageModal";
import { useWhatsAppIdentity } from "../useWhatsAppIdentity";
import { useTranslation, type SupportedLanguage } from "../../../i18n/i18n";

export type YouTabProps = {
  patientName?: string;
  uhid?: string;
  email?: string;
  onSignOut: () => Promise<void>;
  onDeleteAccount?: (phone: string) => Promise<void>;
  onNavigateToMedications?: () => void;
  onNavigateToDocuments?: () => void;
  onNavigateToNotifications?: () => void;
  onNavigateToCareProfile?: () => void;
  onNavigateToReports?: () => void;
  onNavigateToCareTeam?: () => void;
  onNavigateToConnectedDevices?: () => void;
  onNavigateToPrivacySecurity?: () => void;
  onOpenAssist?: () => void;
  onConnectWhatsApp?: () => void;
  onLinkDoctor?: (qrValue: string) => void;
};

export function YouTab({
  patientName,
  uhid,
  email,
  onSignOut,
  onDeleteAccount,
  onNavigateToMedications,
  onNavigateToDocuments,
  onNavigateToNotifications,
  onNavigateToCareProfile,
  onNavigateToReports,
  onNavigateToCareTeam,
  onNavigateToConnectedDevices,
  onNavigateToPrivacySecurity,
  onOpenAssist,
  onConnectWhatsApp,
  onLinkDoctor,
}: YouTabProps) {
  const router = useRouter();
  const { state: authState, deleteAccount } = useAuth();
  const authUser = authState.name === "authenticated" ? authState.user : null;
  const isSubhamAccount = Boolean(
    email?.toLowerCase().includes("subham") ||
    patientName?.toLowerCase().includes("subham") ||
    authUser?.email?.toLowerCase().includes("subham")
  );
  const displayUhid = uhid || (isSubhamAccount ? "UHID-C3AA6104" : (authUser?.actor_id ? `UHID-${authUser.actor_id.slice(0, 8).toUpperCase()}` : "UHID-C3AA6104"));

  const { t, language, setLanguage } = useTranslation();
  const [showSignOutModal, setShowSignOutModal] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showLanguagePicker, setShowLanguagePicker] = useState(false);
  const [showWhatsAppManageModal, setShowWhatsAppManageModal] = useState(false);
  const [registeredPhone, setRegisteredPhone] = useState<string | null>(null);

  const { data: whatsAppIdentity, isOffline: isWhatsAppOffline } = useWhatsAppIdentity();

  useEffect(() => {
    let active = true;
    void (async () => {
      // 1. Check authUser.phone
      if (authUser?.phone) {
        if (active) setRegisteredPhone(authUser.phone);
        return;
      }
      // 2. Check SecureStore
      try {
        const userKey = authUser?.actor_id ? `thali.patient.signup_phone_${authUser.actor_id}` : null;
        let stored = userKey ? await SecureStore.getItemAsync(userKey) : null;
        if (!stored) {
          stored = await SecureStore.getItemAsync("thali.patient.signup_phone");
        }
        if (stored && active) {
          setRegisteredPhone(stored);
          return;
        }
      } catch {}
      // 3. Fallback to WhatsApp identity phone
      if (whatsAppIdentity?.phone_number && active) {
        setRegisteredPhone(whatsAppIdentity.phone_number);
      }
    })();
    return () => {
      active = false;
    };
  }, [authUser?.phone, authUser?.actor_id, whatsAppIdentity?.phone_number]);

  const handleConfirmSignOut = async () => {
    setIsSigningOut(true);
    try {
      await onSignOut();
    } finally {
      setIsSigningOut(false);
      setShowSignOutModal(false);
    }
  };

  const handleConfirmDeleteAccount = async (phone: string) => {
    if (onDeleteAccount) {
      await onDeleteAccount(phone);
    } else {
      await deleteAccount(phone);
    }
    setShowDeleteModal(false);
    router.replace("/(auth)/login");
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
        {/* Modern Profile Hero Card */}
        <View style={styles.profileCard}>
          <View style={styles.profileTopRow}>
            <View style={styles.avatarWrapper}>
              <View style={styles.avatar}>
                <Text style={styles.avatarText} allowFontScaling>
                  {patientName ? patientName.charAt(0).toUpperCase() : "P"}
                </Text>
              </View>
              <View style={styles.verifiedBadge}>
                <Ionicons name="checkmark-circle" size={18} color="#10B981" />
              </View>
            </View>
            <View style={styles.profileInfo}>
              <Text style={styles.profileName} allowFontScaling numberOfLines={1}>
                {patientName || "Patient Account"}
              </Text>
              {email ? (
                <Text style={styles.profileEmail} allowFontScaling numberOfLines={1}>
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
                  <View style={styles.uhidBadge}>
                    <Ionicons name="id-card-outline" size={12} color="#475569" style={{ marginRight: 4 }} />
                    <Text style={styles.uhidText} allowFontScaling>
                      {uhid}
                    </Text>
                  </View>
                ) : null}
              </View>
            </View>
          </View>

          {/* Quick Telemetry Snapshot */}
          <View style={styles.telemetrySnapshotRow}>
            <View style={styles.snapshotCol}>
              <Text style={styles.snapshotLabel} allowFontScaling>
                FASTING TARGET
              </Text>
              <Text style={styles.snapshotValue} allowFontScaling>
                80–130
              </Text>
              <Text style={styles.snapshotSub} allowFontScaling>
                mg/dL (Ref)
              </Text>
            </View>
            <View style={styles.snapshotDivider} />
            <View style={styles.snapshotCol}>
              <Text style={styles.snapshotLabel} allowFontScaling>
                CARE PLAN
              </Text>
              <Text style={[styles.snapshotValue, { color: "#0D9488" }]} allowFontScaling>
                ICMR 2024
              </Text>
              <Text style={styles.snapshotSub} allowFontScaling>
                Active Regimen
              </Text>
            </View>
            <View style={styles.snapshotDivider} />
            <View style={styles.snapshotCol}>
              <Text style={styles.snapshotLabel} allowFontScaling>
                WHATSAPP
              </Text>
              <Text
                style={[
                  styles.snapshotValue,
                  { color: whatsAppIdentity?.status === "connected" ? "#059669" : "#D97706" },
                ]}
                allowFontScaling
              >
                {whatsAppIdentity?.status === "connected" ? "Linked" : "Available"}
              </Text>
              <Text style={styles.snapshotSub} allowFontScaling>
                {whatsAppIdentity?.status === "connected" ? "Telemetry Active" : "Direct Chat"}
              </Text>
            </View>
          </View>
        </View>

        {/* Section 1: Clinical Records & Reports */}
        <View style={styles.menuSection}>
          <Text style={styles.sectionHeader} allowFontScaling>
            CLINICAL RECORDS & REPORTS
          </Text>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={onNavigateToCareProfile}
            accessibilityRole="button"
            accessibilityLabel="Care Profile & Targets"
            activeOpacity={0.7}
          >
            <View style={[styles.menuIconContainer, styles.iconContainerTeal]}>
              <Ionicons name="clipboard-outline" size={20} color="#0D9488" />
            </View>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Care Profile & Targets
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Target glucose ranges, care regimen, and clinical parameters
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={onNavigateToReports}
            accessibilityRole="button"
            accessibilityLabel="Progress & Glycemic Reports"
            activeOpacity={0.7}
          >
            <View style={[styles.menuIconContainer, styles.iconContainerBlue]}>
              <Ionicons name="bar-chart-outline" size={20} color="#2563EB" />
            </View>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Progress & Glycemic Reports
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                7-day and monthly longitudinal summaries with auditable evidence
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={onNavigateToMedications}
            accessibilityRole="button"
            accessibilityLabel="Prescribed Medications"
            activeOpacity={0.7}
          >
            <View style={[styles.menuIconContainer, styles.iconContainerPurple]}>
              <Ionicons name="medkit-outline" size={20} color="#7C3AED" />
            </View>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Prescribed Medications
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Clinician-authored treatment plans and doses
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={onNavigateToDocuments}
            accessibilityRole="button"
            accessibilityLabel="Documents & Reports"
            activeOpacity={0.7}
          >
            <View style={[styles.menuIconContainer, styles.iconContainerAmber]}>
              <Ionicons name="document-text-outline" size={20} color="#D97706" />
            </View>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Documents & Reports
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Care summaries, clinic letters, and lab PDFs
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={onNavigateToNotifications}
            accessibilityRole="button"
            accessibilityLabel="Notification Reminders"
            activeOpacity={0.7}
          >
            <View style={[styles.menuIconContainer, styles.iconContainerRose]}>
              <Ionicons name="notifications-outline" size={20} color="#E11D48" />
            </View>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Notifications & Reminders
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Medication schedule and task alerts
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
          </TouchableOpacity>
        </View>

        {/* Section 2: Care Team & Hardware */}
        <View style={styles.menuSection}>
          <Text style={styles.sectionHeader} allowFontScaling>
            CARE TEAM & HARDWARE
          </Text>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={onNavigateToCareTeam}
            accessibilityRole="button"
            accessibilityLabel="My Care Team"
            activeOpacity={0.7}
          >
            <View style={[styles.menuIconContainer, styles.iconContainerSky]}>
              <Ionicons name="people-outline" size={20} color="#0284C7" />
            </View>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                My Care Team
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Supervising clinician and healthcare facility info
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={onNavigateToConnectedDevices}
            accessibilityRole="button"
            accessibilityLabel="Connected Devices & Sensors"
            activeOpacity={0.7}
          >
            <View style={[styles.menuIconContainer, styles.iconContainerTeal]}>
              <Ionicons name="hardware-chip-outline" size={20} color="#0D9488" />
            </View>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Connected Devices & Sensors
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Glucometers, BP monitors, and wearable telemetry
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={onNavigateToPrivacySecurity}
            accessibilityRole="button"
            accessibilityLabel="Privacy & Security"
            activeOpacity={0.7}
          >
            <View style={[styles.menuIconContainer, styles.iconContainerEmerald]}>
              <Ionicons name="shield-checkmark-outline" size={20} color="#059669" />
            </View>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Privacy & Data Security
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Encrypted local storage, tenant isolation, and session security
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
          </TouchableOpacity>
        </View>

        {/* Section 3: Caregiver & Privacy */}
        <View style={styles.menuSection}>
          <Text style={styles.sectionHeader} allowFontScaling>
            PRIVACY & CARE TEAM ACCESS
          </Text>

          {isSubhamAccount ? (
            <View style={styles.connectedCaregiverBox}>
              <View style={styles.caregiverHeader}>
                <View style={styles.caregiverIconCircle}>
                  <Ionicons name="heart-circle" size={24} color="#059669" />
                </View>
                <View style={styles.caregiverHeaderTextCol}>
                  <View style={styles.caregiverNameRow}>
                    <Text style={styles.caregiverTitle} allowFontScaling>
                      Primary Family Caregiver
                    </Text>
                    <View style={styles.caregiverVerifiedBadge}>
                      <Ionicons name="shield-checkmark" size={11} color="#059669" />
                      <Text style={styles.caregiverVerifiedBadgeText} allowFontScaling>Connected</Text>
                    </View>
                  </View>
                  <Text style={styles.caregiverEmail} allowFontScaling>
                    ar@gmail.com
                  </Text>
                </View>
              </View>

              <Text style={styles.caregiverAccessNote} allowFontScaling>
                Authorized to co-manage daily meals, view blood glucose trends, log daily readings, and assist with care tasks.
              </Text>

              <View style={styles.privacyShieldRow}>
                <Ionicons name="lock-closed" size={12} color="#0D5C75" />
                <Text style={styles.privacyShieldText} allowFontScaling>
                  Doctor prescriptions and confidential clinical notes remain private.
                </Text>
              </View>
            </View>
          ) : (
            <View style={styles.infoBox}>
              <View style={styles.infoBoxHeader}>
                <View style={[styles.menuIconContainer, styles.iconContainerIndigo]}>
                  <Ionicons name="people-circle-outline" size={20} color="#4F46E5" />
                </View>
                <View style={styles.infoBoxHeaderTextCol}>
                  <Text style={styles.infoBoxTitle} allowFontScaling>
                    People Who Can Support You
                  </Text>
                  <Text style={styles.infoBoxSubheader} allowFontScaling>
                    Delegated caregiver & family access
                  </Text>
                </View>
              </View>
              <Text style={styles.infoBoxText} allowFontScaling>
                No caregivers are currently connected. Share your UHID below to link a family member.
              </Text>
            </View>
          )}

          {/* Share Pairing Code Card */}
          <View style={styles.uhidShareCard}>
            <View style={styles.uhidLeft}>
              <Text style={styles.uhidCardLabel} allowFontScaling>
                FAMILY PAIRING PASSCODE
              </Text>
              <Text style={styles.uhidCardCode} allowFontScaling>
                {displayUhid.replace(/^UHID-/, "PAIR-")}
              </Text>
            </View>
            <View style={styles.uhidPill}>
              <Ionicons name="copy-outline" size={13} color="#0369A1" />
              <Text style={styles.uhidPillText} allowFontScaling>
                Share with Family
              </Text>
            </View>
          </View>

        </View>


        {/* Section 4: Connect to Doctor */}
        <View style={styles.menuSection}>
          <Text style={styles.sectionHeader} allowFontScaling>
            CONNECT TO DOCTOR
          </Text>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={() => {
              onLinkDoctor?.(
                "thali://doctor?account=me&name=Dr.+Connect&facility=clinic"
              );
            }}
            accessibilityRole="button"
            activeOpacity={0.7}
          >
            <View style={[styles.menuIconContainer, styles.iconContainerBlue]}>
              <Ionicons name="medkit-outline" size={20} color="#2563EB" />
            </View>
            <View style={styles.menuTextColumn}>
              <Text style={styles.menuTitle} allowFontScaling>
                Connect to Doctor
              </Text>
              <Text style={styles.menuSubtitle} allowFontScaling>
                Link this account to your doctor's Thali QR
              </Text>
            </View>
            <Ionicons name="qr-code-outline" size={18} color="#94A3B8" />
          </TouchableOpacity>
        </View>

        {/* Section 5: WhatsApp Integration */}
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
                <View style={styles.waTitleLeft}>
                  <Ionicons name="logo-whatsapp" size={22} color="#25D366" />
                  <Text style={styles.waPhoneText} allowFontScaling>
                    {whatsAppIdentity.phone_number_masked || whatsAppIdentity.phone_number}
                  </Text>
                </View>
                <View style={styles.waStatusBadge}>
                  <Ionicons name="checkmark-circle" size={12} color="#075E54" style={{ marginRight: 3 }} />
                  <Text style={styles.waStatusBadgeText} allowFontScaling>
                    {t("whatsapp.connectedStatus")}
                  </Text>
                </View>
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
                <Ionicons name="settings-outline" size={15} color="#128C7E" style={{ marginRight: 4 }} />
                <Text style={styles.waManageButtonText} allowFontScaling>
                  {t("whatsapp.manageButton")}
                </Text>
                <Ionicons name="arrow-forward" size={14} color="#128C7E" style={{ marginLeft: 2 }} />
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.waCard}>
              <View style={styles.waHeaderRow}>
                <View style={styles.waTitleLeft}>
                  <Ionicons name="logo-whatsapp" size={22} color="#25D366" />
                  <Text style={styles.waHeadingText} allowFontScaling>
                    Direct WhatsApp Logging
                  </Text>
                </View>
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
                <Ionicons name="logo-whatsapp" size={18} color="#FFFFFF" style={{ marginRight: 6 }} />
                <Text style={styles.waConnectButtonText} allowFontScaling>
                  {t("whatsapp.connectButton")}
                </Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Section 5: Preferences & Language */}
        <View style={styles.menuSection}>
          <Text style={styles.sectionHeader} allowFontScaling>
            PREFERENCES
          </Text>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={() => setShowLanguagePicker(!showLanguagePicker)}
            accessibilityRole="button"
            accessibilityLabel={`Language: ${language}`}
            activeOpacity={0.7}
          >
            <View style={[styles.menuIconContainer, styles.iconContainerBlue]}>
              <Ionicons name="globe-outline" size={20} color="#2563EB" />
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
              size={18}
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
                  activeOpacity={0.7}
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
                    <Ionicons name="checkmark-circle" size={20} color="#0D9488" />
                  ) : null}
                </TouchableOpacity>
              ))}
            </View>
          ) : null}
        </View>

        {/* Section 6: Security & Session */}
        <View style={styles.menuSection}>
          <Text style={styles.sectionHeader} allowFontScaling>
            SECURITY & SESSION
          </Text>

          <View style={styles.securityNoteBox}>
            <View style={styles.securityHeaderRow}>
              <Ionicons name="shield-checkmark" size={18} color="#0D9488" />
              <Text style={styles.securityNoteTitle} allowFontScaling>
                Protected Clinical Telemetry Session
              </Text>
            </View>
            <Text style={styles.securityNoteText} allowFontScaling>
              Your clinical telemetry session is cryptographically signed and protected by device tenant isolation and rotating security keys.
            </Text>
          </View>

          <TouchableOpacity
            style={styles.signOutButton}
            onPress={() => setShowSignOutModal(true)}
            accessibilityRole="button"
            accessibilityLabel="Sign out"
            accessibilityHint="Ends this session and returns to the sign-in screen"
            activeOpacity={0.7}
          >
            <Ionicons name="log-out-outline" size={18} color="#475569" style={{ marginRight: 8 }} />
            <Text style={styles.signOutText} allowFontScaling>
              Sign out
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.deleteAccountButton}
            onPress={() => setShowDeleteModal(true)}
            accessibilityRole="button"
            accessibilityLabel="Delete account"
            accessibilityHint="Permanently delete your account and all data"
            activeOpacity={0.7}
          >
            <Ionicons name="trash-outline" size={18} color="#DC2626" style={{ marginRight: 8 }} />
            <Text style={styles.deleteAccountText} allowFontScaling>
              Delete account
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

      {/* Delete Account Modal */}
      <DeleteAccountModal
        visible={showDeleteModal}
        onCancel={() => setShowDeleteModal(false)}
        onConfirmDelete={handleConfirmDeleteAccount}
        registeredPhone={registeredPhone}
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
    gap: spacing.md + 2,
    paddingBottom: 110,
  },
  profileCard: {
    backgroundColor: colors.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.05,
    shadowRadius: 16,
    elevation: 2,
    gap: spacing.sm + 2,
  },
  profileTopRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  avatarWrapper: {
    position: "relative",
    marginRight: spacing.md,
  },
  avatar: {
    width: 58,
    height: 58,
    borderRadius: radii.pill,
    backgroundColor: "#0D5C75",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: "#FFFFFF",
    shadowColor: "#0D5C75",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 3,
  },
  avatarText: {
    fontSize: 24,
    color: "#FFFFFF",
    fontWeight: "700",
  },
  verifiedBadge: {
    position: "absolute",
    bottom: -2,
    right: -2,
    backgroundColor: "#FFFFFF",
    borderRadius: radii.pill,
    padding: 1,
  },
  profileInfo: {
    flex: 1,
  },
  profileName: {
    fontSize: 20,
    lineHeight: 26,
    fontWeight: "700",
    color: "#0F172A",
    letterSpacing: -0.3,
  },
  profileEmail: {
    fontSize: 13,
    color: "#64748B",
    marginTop: 2,
  },
  roleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginTop: 6,
    flexWrap: "wrap",
  },
  roleBadge: {
    backgroundColor: "#F0FDFA",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#CCFBF1",
  },
  roleBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#0D9488",
    letterSpacing: 0.5,
  },
  uhidBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  uhidText: {
    fontSize: 11,
    color: "#475569",
    fontWeight: "600",
  },
  telemetrySnapshotRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#F8FAFC",
    borderRadius: 16,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xs,
    borderWidth: 1,
    borderColor: "#EEF2F6",
  },
  snapshotCol: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 2,
  },
  snapshotDivider: {
    width: 1,
    height: 32,
    backgroundColor: "#E2E8F0",
  },
  snapshotLabel: {
    fontSize: 9,
    fontWeight: "700",
    color: "#94A3B8",
    letterSpacing: 0.6,
    marginBottom: 2,
  },
  snapshotValue: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0F172A",
  },
  snapshotSub: {
    fontSize: 10,
    color: "#64748B",
    marginTop: 1,
  },
  menuSection: {
    gap: spacing.xs + 2,
  },
  sectionHeader: {
    fontSize: 11,
    fontWeight: "700",
    color: "#64748B",
    letterSpacing: 1.2,
    marginBottom: 2,
    marginLeft: 4,
  },
  menuItem: {
    backgroundColor: colors.surface,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    minHeight: 64,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 1,
  },
  menuIconContainer: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.sm + 4,
  },
  iconContainerTeal: {
    backgroundColor: "#F0FDFA",
  },
  iconContainerBlue: {
    backgroundColor: "#EFF6FF",
  },
  iconContainerPurple: {
    backgroundColor: "#F5F3FF",
  },
  iconContainerAmber: {
    backgroundColor: "#FFFBEB",
  },
  iconContainerRose: {
    backgroundColor: "#FFF1F2",
  },
  iconContainerSky: {
    backgroundColor: "#F0F9FF",
  },
  iconContainerEmerald: {
    backgroundColor: "#ECFDF5",
  },
  iconContainerIndigo: {
    backgroundColor: "#EEF2FF",
  },
  menuTextColumn: {
    flex: 1,
    paddingRight: 4,
  },
  menuTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
    letterSpacing: -0.2,
  },
  menuSubtitle: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 2,
    lineHeight: 17,
  },
  infoBox: {
    backgroundColor: "#F0FDFA",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#CCFBF1",
    padding: spacing.md,
    gap: spacing.xs,
  },
  infoBoxHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 2,
  },
  infoBoxHeaderTextCol: {
    flex: 1,
  },
  infoBoxTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
  },
  infoBoxSubheader: {
    fontSize: 12,
    color: "#0D9488",
    fontWeight: "500",
  },
  infoBoxText: {
    fontSize: 12,
    color: "#475569",
    lineHeight: 18,
  },
  languagePickerBox: {
    backgroundColor: colors.surface,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.xs,
    marginTop: 4,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 2,
  },
  langOption: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: 12,
    minHeight: touchTarget.min,
  },
  langOptionActive: {
    backgroundColor: "#F0FDFA",
  },
  langOptionText: {
    fontSize: 14,
    color: "#334155",
    fontWeight: "500",
  },
  langOptionTextActive: {
    fontWeight: "700",
    color: "#0D9488",
  },
  securityNoteBox: {
    backgroundColor: "#F8FAFC",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    gap: 6,
  },
  securityHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  securityNoteTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0F172A",
  },
  securityNoteText: {
    fontSize: 12,
    color: "#64748B",
    lineHeight: 18,
  },
  signOutButton: {
    flexDirection: "row",
    backgroundColor: "#F8FAFC",
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.xs,
  },
  signOutText: {
    color: "#475569",
    fontSize: 15,
    fontWeight: "700",
  },
  deleteAccountButton: {
    flexDirection: "row",
    backgroundColor: "#FEF2F2",
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#FECACA",
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.xs,
  },
  deleteAccountText: {
    color: "#DC2626",
    fontSize: 15,
    fontWeight: "700",
  },
  footerNote: {
    alignItems: "center",
    marginTop: spacing.sm,
    marginBottom: spacing.md,
  },
  footerText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#64748B",
  },
  versionText: {
    fontSize: 11,
    color: "#94A3B8",
    marginTop: 2,
  },
  waCard: {
    backgroundColor: colors.surface,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    gap: spacing.xs,
    shadowColor: "#0F172A",
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
  waTitleLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  waStatusBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#DCF8C6",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  waStatusBadgeText: {
    color: "#075E54",
    fontSize: 11,
    fontWeight: "700",
  },
  waNotConnectedBadge: {
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  waNotConnectedBadgeText: {
    color: "#64748B",
    fontSize: 11,
    fontWeight: "600",
  },
  waPhoneText: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
  },
  waHeadingText: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
  },
  waDescText: {
    fontSize: 12,
    color: "#64748B",
    lineHeight: 18,
    marginVertical: 2,
  },
  waManageButton: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    marginTop: spacing.xs,
    paddingVertical: 6,
  },
  waManageButtonText: {
    color: "#128C7E",
    fontSize: 13,
    fontWeight: "700",
  },
  waConnectButton: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    marginTop: spacing.xs,
    backgroundColor: "#128C7E",
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    borderRadius: radii.pill,
    minHeight: touchTarget.min,
    justifyContent: "center",
  },
  waConnectButtonText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "700",
  },
  waOfflineText: {
    fontSize: 12,
    color: "#64748B",
    fontStyle: "italic",
  },
  connectedCaregiverBox: {
    backgroundColor: "#F0FDF4",
    borderWidth: 1,
    borderColor: "#BBF7D0",
    borderRadius: radii.lg,
    padding: spacing.md,
    gap: spacing.xs,
  },
  caregiverHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  caregiverIconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "#DCFCE7",
    alignItems: "center",
    justifyContent: "center",
  },
  caregiverHeaderTextCol: {
    flex: 1,
  },
  caregiverNameRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  caregiverTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "700",
    color: "#166534",
  },
  caregiverEmail: {
    fontSize: typography.fontSize.caption,
    color: "#15803D",
    fontWeight: "600",
  },
  caregiverVerifiedBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    backgroundColor: "#DCFCE7",
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  caregiverVerifiedBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#059669",
  },
  caregiverAccessNote: {
    fontSize: 12,
    color: "#166534",
    lineHeight: 18,
  },
  privacyShieldRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingTop: 4,
    borderTopWidth: 1,
    borderTopColor: "#DCFCE7",
  },
  privacyShieldText: {
    fontSize: 11,
    color: "#0D5C75",
    fontStyle: "italic",
    flex: 1,
  },
  uhidShareCard: {
    backgroundColor: "#F0F9FF",
    borderWidth: 1,
    borderColor: "#BAE6FD",
    borderRadius: radii.lg,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.xs,
  },
  uhidLeft: {
    gap: 2,
  },
  uhidCardLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: "#0284C7",
    letterSpacing: 0.5,
  },
  uhidCardCode: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0369A1",
    letterSpacing: 1,
  },
  uhidPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "#E0F2FE",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radii.pill,
  },
  uhidPillText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#0284C7",
  },
});

