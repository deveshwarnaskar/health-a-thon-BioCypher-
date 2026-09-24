import React, { useState } from "react";
import {
  Platform,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../auth/AuthProvider";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { Button } from "../../components/primitives/Button";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { caregiverPalette, caregiverRadii, caregiverShadow } from "./caregiverDesign";
import { CaregiverPatientCard } from "./CaregiverPatientCard";
import { LinkPatientModal } from "./LinkPatientModal";
import { CaregiverAccountModal } from "./CaregiverAccountModal";
import { useCaregiverPatients } from "./useCaregiverPatients";
import type { CaregiverPatientListItem } from "../../services/schemas/caregiver";

export type CaregiverPatientsScreenProps = {
  onSelect?: (patient: CaregiverPatientListItem) => void;
  onBack?: () => void;
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

export function CaregiverPatientsScreen({
  onSelect,
  onBack,
  onSignOut,
  testID,
}: CaregiverPatientsScreenProps) {
  const { state } = useAuth();
  const authUser = state.name === "authenticated" ? state.user : null;
  const isCaregiverRole = authUser?.role === "Caregiver";

  const [showLinkModal, setShowLinkModal] = useState(false);
  const [showAccountModal, setShowAccountModal] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const list = useCaregiverPatients({ enabled: isCaregiverRole });

  if (!isCaregiverRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Caregiver Portal"
          onBack={onBack}
          leadingLabel={onBack ? "Back" : undefined}
        />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="The patient discovery screen is only available in Caregiver mode."
          />
          {onBack ? (
            <Button label="Return to Main Menu" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  const caregiverEmail = authUser?.email || "Caregiver";
  const caregiverDisplayName = (authUser as any)?.name || caregiverEmail.split("@")[0] || "Caregiver";
  const caregiverInitials = getInitials(caregiverDisplayName);

  const filteredPatients = list.patients.filter((p) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      p.name.toLowerCase().includes(q) ||
      (p.relationship_label && p.relationship_label.toLowerCase().includes(q))
    );
  });

  return (
    <View style={styles.container} testID={testID}>
      {/* Top App Bar with Caregiver Profile Avatar */}
      <TopAppBar
        title="My Patients"
        onBack={onBack}
        leadingLabel={onBack ? "Menu" : undefined}
      />

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={list.isLoading}
            onRefresh={() => list.refetch()}
            tintColor={caregiverPalette.primary}
          />
        }
      >
        {/* Caregiver Welcome & Identity Hub Card */}
        <View style={styles.heroCard}>
          <View style={styles.heroTopRow}>
            <TouchableOpacity
              style={styles.heroAvatarBtn}
              onPress={() => setShowAccountModal(true)}
              activeOpacity={0.8}
              accessibilityRole="button"
              accessibilityLabel="View Caregiver Account & Profile"
            >
              <View style={styles.heroAvatar}>
                <Text style={styles.heroAvatarText} allowFontScaling>
                  {caregiverInitials}
                </Text>
              </View>
              <View style={styles.heroOnlineBadge}>
                <View style={styles.heroOnlineDot} />
              </View>
            </TouchableOpacity>

            <View style={styles.heroInfoCol}>
              <View style={styles.roleBadgeRow}>
                <View style={styles.roleBadge}>
                  <Ionicons name="heart" size={11} color={caregiverPalette.tealDark} />
                  <Text style={styles.roleBadgeText} allowFontScaling>
                    Family Caregiver
                  </Text>
                </View>
                <View style={styles.verifiedBadge}>
                  <Ionicons name="shield-checkmark" size={10} color={caregiverPalette.emeraldDark} />
                  <Text style={styles.verifiedText} allowFontScaling>
                    Verified
                  </Text>
                </View>
              </View>

              <Text style={styles.caregiverGreeting} numberOfLines={1} allowFontScaling>
                {caregiverEmail}
              </Text>

              <Text style={styles.surveillanceSubtitle} allowFontScaling>
                {list.patients.length === 1
                  ? "1 patient under active daily care"
                  : `${list.patients.length} patients under active daily care`}
              </Text>
            </View>
          </View>

          {/* Quick Action Buttons Row */}
          <View style={styles.heroActionsRow}>
            <TouchableOpacity
              style={styles.linkButton}
              onPress={() => setShowLinkModal(true)}
              activeOpacity={0.82}
              accessibilityRole="button"
              accessibilityLabel="Link new patient"
            >
              <Ionicons name="person-add" size={15} color="#FFFFFF" />
              <Text style={styles.linkButtonText} allowFontScaling>
                Link Patient
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.accountButton}
              onPress={() => setShowAccountModal(true)}
              activeOpacity={0.82}
              accessibilityRole="button"
              accessibilityLabel="Caregiver Account"
            >
              <Ionicons name="person-circle-outline" size={16} color={caregiverPalette.primary} />
              <Text style={styles.accountButtonText} allowFontScaling>
                Account
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Quick Search Bar if multiple patients */}
        {list.patients.length > 2 ? (
          <View style={styles.searchBar}>
            <Ionicons name="search" size={16} color={caregiverPalette.muted} />
            <TextInput
              style={styles.searchInput}
              placeholder="Search patients by name or relation…"
              placeholderTextColor={caregiverPalette.subtle}
              value={searchQuery}
              onChangeText={setSearchQuery}
            />
            {searchQuery.length > 0 ? (
              <TouchableOpacity onPress={() => setSearchQuery("")}>
                <Ionicons name="close-circle" size={16} color={caregiverPalette.muted} />
              </TouchableOpacity>
            ) : null}
          </View>
        ) : null}

        {/* Linking Procedure Accordion / Explainer */}
        <TouchableOpacity
          style={styles.guideCard}
          onPress={() => setShowGuide(!showGuide)}
          activeOpacity={0.85}
          accessibilityRole="button"
          accessibilityLabel="How to Connect with a Patient Account"
        >
          <View style={styles.guideHeader}>
            <View style={styles.guideIcon}>
              <Ionicons name="information-circle" size={18} color={caregiverPalette.sky} />
            </View>
            <View style={styles.guideTitleCol}>
              <Text style={styles.guideTitle} allowFontScaling>
                How to Connect with a Patient Account
              </Text>
              <Text style={styles.guideSubtitle} allowFontScaling>
                Quick 3-step setup to monitor loved ones
              </Text>
            </View>
            <View style={styles.guideChevronCircle}>
              <Ionicons
                name={showGuide ? "chevron-up" : "chevron-down"}
                size={16}
                color={caregiverPalette.sky}
              />
            </View>
          </View>

          {showGuide ? (
            <View style={styles.guideBody}>
              <View style={styles.stepItem}>
                <View style={styles.stepBadge}>
                  <Text style={styles.stepBadgeText}>1</Text>
                </View>
                <Text style={styles.stepContent} allowFontScaling>
                  <Text style={styles.boldText}>Patient shares UHID:</Text> The patient opens their THALI mobile app, goes to <Text style={styles.codeText}>Profile / You</Text> tab, and notes their Patient UHID (e.g. <Text style={styles.codeText}>UHID-C3AA6104</Text>).
                </Text>
              </View>

              <View style={styles.stepItem}>
                <View style={styles.stepBadge}>
                  <Text style={styles.stepBadgeText}>2</Text>
                </View>
                <Text style={styles.stepContent} allowFontScaling>
                  <Text style={styles.boldText}>Enter UHID & Relationship:</Text> Tap the <Text style={styles.boldText}>"+ Link Patient"</Text> button above, enter the UHID, and select your relationship (Spouse, Parent, Child, Guardian, etc.).
                </Text>
              </View>

              <View style={styles.stepItem}>
                <View style={styles.stepBadge}>
                  <Text style={styles.stepBadgeText}>3</Text>
                </View>
                <Text style={styles.stepContent} allowFontScaling>
                  <Text style={styles.boldText}>Instant Daily Care:</Text> Once connected, you can view the patient's daily meals scanned, glucose readings & timing, log entries on their behalf, and check off routine care tasks.
                </Text>
              </View>
            </View>
          ) : null}
        </TouchableOpacity>

        {/* State Renderers */}
        {list.isLoading ? (
          <LoadingState label="Loading your patients…" />
        ) : null}

        {!list.isLoading && list.isError ? (
          <View style={styles.content}>
            <ErrorState
              title="Could not load patients"
              message="Unable to connect to your caregiver record. Please try again."
              onRetry={() => list.refetch()}
            />
          </View>
        ) : null}

        {!list.isLoading && !list.isError && list.patients.length === 0 ? (
          <View style={styles.emptyContainer}>
            <EmptyState
              title="No authorized patients"
              message="You are not currently authorized to view any patients. A clinic coordinator adds and verifies caregiver relationships, or you can link directly via UHID."
            />
            <Button
              label="+ Link Patient Account"
              variant="primary"
              onPress={() => setShowLinkModal(true)}
            />
          </View>
        ) : null}

        {!list.isError && list.patients.length > 0 ? (
          <View style={styles.patientListSection}>
            <View style={styles.sectionHeaderRow}>
              <View style={styles.sectionHeaderTitleRow}>
                <Ionicons name="people" size={14} color={caregiverPalette.muted} />
                <Text style={styles.sectionHeaderTitle} allowFontScaling>
                  PATIENTS UNDER YOUR CARE
                </Text>
              </View>
              <View style={styles.activePillBadge}>
                <View style={styles.greenLiveDot} />
                <Text style={styles.sectionHeaderBadge} allowFontScaling>
                  {list.patients.length} ACTIVE
                </Text>
              </View>
            </View>

            {filteredPatients.map((patient) => (
              <CaregiverPatientCard
                key={patient.patient_id}
                patient={patient}
                onSelect={(selected) => onSelect?.(selected)}
              />
            ))}
          </View>
        ) : null}
      </ScrollView>

      {/* Link Patient Modal */}
      <LinkPatientModal
        visible={showLinkModal}
        onClose={() => setShowLinkModal(false)}
        onSuccess={(linked) => {
          setShowLinkModal(false);
          onSelect?.(linked);
        }}
      />

      {/* Caregiver Account Modal */}
      <CaregiverAccountModal
        visible={showAccountModal}
        onClose={() => setShowAccountModal(false)}
        patients={list.patients}
        onOpenLinkModal={() => setShowLinkModal(true)}
        onSignOut={onSignOut}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: caregiverPalette.appBackground,
  },
  content: {
    padding: spacing.md,
    gap: spacing.md,
  },
  scrollContent: {
    padding: 16,
    gap: 14,
    paddingBottom: spacing.xxl,
  },
  heroCard: {
    backgroundColor: caregiverPalette.surface,
    borderRadius: caregiverRadii.lg,
    padding: 16,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    gap: 14,
    ...caregiverShadow.card,
  },
  heroTopRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  heroAvatarBtn: {
    position: "relative",
  },
  heroAvatar: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: caregiverPalette.surfaceTeal,
    borderWidth: 2,
    borderColor: caregiverPalette.tealSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  heroAvatarText: {
    fontSize: 17,
    fontWeight: "800",
    color: caregiverPalette.tealDark,
    letterSpacing: 0.5,
  },
  heroOnlineBadge: {
    position: "absolute",
    bottom: -1,
    right: -1,
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: caregiverPalette.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  heroOnlineDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: caregiverPalette.emerald,
  },
  heroInfoCol: {
    flex: 1,
    gap: 3,
  },
  roleBadgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  roleBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: caregiverPalette.surfaceTeal,
    paddingHorizontal: 8,
    paddingVertical: 2.5,
    borderRadius: caregiverRadii.pill,
    borderWidth: 1,
    borderColor: caregiverPalette.tealSoft,
  },
  roleBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: caregiverPalette.tealDark,
  },
  verifiedBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    backgroundColor: caregiverPalette.emeraldSoft,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: caregiverRadii.pill,
    borderWidth: 1,
    borderColor: caregiverPalette.emeraldBorder,
  },
  verifiedText: {
    fontSize: 10,
    fontWeight: "700",
    color: caregiverPalette.emeraldDark,
  },
  caregiverGreeting: {
    fontSize: 16,
    fontWeight: "800",
    color: caregiverPalette.ink,
    marginTop: 1,
  },
  surveillanceSubtitle: {
    fontSize: 12,
    color: caregiverPalette.muted,
  },
  heroActionsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: caregiverPalette.borderLight,
  },
  linkButton: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    backgroundColor: caregiverPalette.primary,
    paddingVertical: 10,
    borderRadius: caregiverRadii.md,
    ...caregiverShadow.button,
  },
  linkButtonText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "700",
  },
  accountButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 5,
    backgroundColor: caregiverPalette.primaryLight,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: caregiverRadii.md,
    borderWidth: 1,
    borderColor: caregiverPalette.primaryBorder,
  },
  accountButtonText: {
    color: caregiverPalette.primary,
    fontSize: 13,
    fontWeight: "700",
  },
  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: caregiverPalette.surface,
    borderRadius: caregiverRadii.md,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 13,
    color: caregiverPalette.ink,
  },
  guideCard: {
    backgroundColor: caregiverPalette.surfaceBlue,
    borderWidth: 1,
    borderColor: caregiverPalette.skyBorder,
    borderRadius: caregiverRadii.lg,
    padding: 14,
    gap: 10,
    ...caregiverShadow.subtle,
  },
  guideHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  guideIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: caregiverPalette.skySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  guideTitleCol: {
    flex: 1,
  },
  guideTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: caregiverPalette.sky,
  },
  guideSubtitle: {
    fontSize: 11,
    color: "#0369A1",
    marginTop: 1,
  },
  guideChevronCircle: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: caregiverPalette.skySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  guideBody: {
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: caregiverPalette.skyBorder,
    gap: 10,
  },
  stepItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 9,
  },
  stepBadge: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: caregiverPalette.sky,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 1,
  },
  stepBadgeText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  stepContent: {
    flex: 1,
    fontSize: 12,
    color: "#0C4A6E",
    lineHeight: 18,
  },
  boldText: {
    fontWeight: "700",
  },
  codeText: {
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
    fontWeight: "700",
    color: caregiverPalette.sky,
  },
  emptyContainer: {
    gap: spacing.md,
    marginTop: spacing.md,
  },
  patientListSection: {
    gap: 12,
    marginTop: 2,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 2,
  },
  sectionHeaderTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  sectionHeaderTitle: {
    fontSize: 11,
    fontWeight: "800",
    color: caregiverPalette.muted,
    letterSpacing: 0.6,
  },
  activePillBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: caregiverPalette.emeraldSoft,
    paddingHorizontal: 8,
    paddingVertical: 2.5,
    borderRadius: caregiverRadii.pill,
    borderWidth: 1,
    borderColor: caregiverPalette.emeraldBorder,
  },
  greenLiveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: caregiverPalette.emerald,
  },
  sectionHeaderBadge: {
    fontSize: 10,
    fontWeight: "800",
    color: caregiverPalette.emeraldDark,
  },
});