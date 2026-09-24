import React, { useState } from "react";
import {
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../auth/AuthProvider";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { Button } from "../../components/primitives/Button";
import { Divider } from "../../components/primitives/Divider";
import { EmptyState } from "../../components/primitives/EmptyState";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { caregiverPalette, caregiverRadii, caregiverShadow } from "./caregiverDesign";
import { GlucoseEntryForm } from "../glucose/GlucoseEntryForm";
import { GlucoseTimeline } from "../glucose/GlucoseTimeline";
import { useGlucoseFeed } from "../glucose/useGlucoseFeed";
import { useIngestGlucose } from "../glucose/useIngestGlucose";
import { caregiverKeys } from "./useCaregiverPatients";
import { CaregiverMealEntryForm } from "./CaregiverMealEntryForm";
import { CaregiverDailyTimeline } from "./CaregiverDailyTimeline";
import { CaregiverTasksSection } from "./CaregiverTasksSection";
import {
  canReadCaregiverGlucose,
  canRecordCaregiverGlucose,
  canRecordCaregiverMeal,
  canReadCaregiverTasks,
  canCompleteCaregiverTasks,
  type CaregiverPatientListItem,
} from "../../services/schemas/caregiver";
import type { ApiErrorDetails } from "../../services/api/errors";
import type { IngestGlucoseResponse } from "../../services/schemas/clinical";

export type CaregiverPatientGlucoseScreenProps = {
  patient: CaregiverPatientListItem;
  onBack?: () => void;
  onAccessLost?: () => void;
  testID?: string;
};

type WorkspaceTab = "glucose" | "timeline" | "meal" | "tasks" | "info";

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "PT";
  const first = parts[0] ?? "";
  if (parts.length === 1) return first.slice(0, 2).toUpperCase() || "PT";
  const last = parts[parts.length - 1] ?? "";
  return ((first[0] ?? "") + (last[0] ?? "")).toUpperCase() || "PT";
}

export function CaregiverPatientGlucoseScreen({
  patient,
  onBack,
  onAccessLost,
  testID,
}: CaregiverPatientGlucoseScreenProps) {
  const { state } = useAuth();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("glucose");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const authUser = state.name === "authenticated" ? state.user : null;
  const isCaregiverRole = authUser?.role === "Caregiver";
  const relationshipCapabilities = patient.capabilities;

  const canRead = canReadCaregiverGlucose(relationshipCapabilities);
  const canRecord = canRecordCaregiverGlucose(relationshipCapabilities);
  const canRecordMeal = canRecordCaregiverMeal(relationshipCapabilities);
  const canTasks = canReadCaregiverTasks(relationshipCapabilities);
  const canCompleteTasks = canCompleteCaregiverTasks(relationshipCapabilities);

  const initials = getInitials(patient.name);

  const feed = useGlucoseFeed(patient.patient_id, {
    enabled: isCaregiverRole && canRead,
  });

  const ingest = useIngestGlucose({
    patientId: patient.patient_id,
    onSuccess: (response: IngestGlucoseResponse) => {
      setErrorMessage(null);
      setSuccessMessage(`Reading of ${response.value_mg_dl} mg/dL recorded successfully.`);
      void queryClient.invalidateQueries({ queryKey: ["caregivers", "timeline", patient.patient_id] });
    },
    onError: (error) => {
      setSuccessMessage(null);
      const apiError = error as ApiErrorDetails | undefined;

      if (apiError?.httpStatus === 403) {
        void queryClient.invalidateQueries({ queryKey: caregiverKeys.patients() });
        onAccessLost?.();
        return;
      }
      if (apiError?.httpStatus === 409) {
        setErrorMessage("A conflicting submission is already in progress. Please wait a moment.");
      } else if (apiError?.httpStatus === 429) {
        const retry = apiError.retryAfterSeconds;
        setErrorMessage(
          retry
            ? `Too many requests. Please wait ${retry} seconds before recording again.`
            : "Too many requests. Please wait a moment before trying again."
        );
      } else if (apiError?.kind === "NETWORK_ERROR") {
        setErrorMessage("Unable to connect. The reading has not been submitted.");
      } else {
        setErrorMessage(apiError?.message ?? "An unexpected error occurred. Please try again.");
      }
    },
  });

  if (!isCaregiverRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Patient Glucose"
          onBack={onBack}
          leadingLabel={onBack ? "Back" : undefined}
        />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="Patient glucose is only available in Caregiver mode."
          />
          {onBack ? (
            <Button label="Return to Patient List" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  // 403 on the observation feed means this patient's access boundary closed
  if (feed.isError && (feed.error as ApiErrorDetails | undefined)?.httpStatus === 403) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Patient Glucose"
          onBack={onBack}
          leadingLabel={onBack ? "Back" : undefined}
        />
        <View style={styles.content}>
          <View testID="caregiver-access-revoked">
            <EmptyState
              title="Access Revoked"
              message="Your relationship with this patient was revoked or expired. Returning to your patient list."
            />
          </View>
          {onAccessLost ? (
            <Button label="Back to Patient List" variant="primary" onPress={onAccessLost} />
          ) : null}
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Patient Glucose"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
      />

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Patient Hero Care Banner */}
        <View style={styles.patientBannerCard}>
          <View style={styles.bannerRow}>
            <View style={styles.avatarWrapper}>
              <View style={styles.patientInitialsBadge}>
                <Text style={styles.patientInitialsText} allowFontScaling>
                  {initials}
                </Text>
              </View>
              <View style={styles.bannerActiveDot}>
                <View style={styles.bannerActiveDotInner} />
              </View>
            </View>

            <View style={styles.bannerTextCol}>
              <View style={styles.bannerTitleRow}>
                <Text style={styles.bannerPatientName} allowFontScaling numberOfLines={1}>
                  {patient.name}
                </Text>
                <View style={styles.verifiedPill}>
                  <Ionicons name="shield-checkmark" size={11} color={caregiverPalette.emeraldDark} />
                  <Text style={styles.verifiedPillText} allowFontScaling>
                    Verified
                  </Text>
                </View>
              </View>

              <Text style={styles.bannerSubtitle} allowFontScaling numberOfLines={1}>
                {patient.relationship_label || "Primary Family Caregiver"} • Authorized daily care
              </Text>
            </View>
          </View>
        </View>

        {/* Action / Segmented Tab Switcher */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.tabBarScroll}
        >
          <TouchableOpacity
            style={[styles.tabButton, activeTab === "glucose" && styles.tabButtonActive]}
            onPress={() => setActiveTab("glucose")}
            accessibilityRole="button"
            accessibilityLabel="Glucose Log Tab"
          >
            <Ionicons
              name="water"
              size={15}
              color={activeTab === "glucose" ? caregiverPalette.primary : caregiverPalette.muted}
            />
            <Text
              style={[styles.tabText, activeTab === "glucose" && styles.tabTextActive]}
              allowFontScaling
            >
              Glucose Log
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tabButton, activeTab === "timeline" && styles.tabButtonActive]}
            onPress={() => setActiveTab("timeline")}
            accessibilityRole="button"
            accessibilityLabel="Daily Inputs Tab"
          >
            <Ionicons
              name="time"
              size={15}
              color={activeTab === "timeline" ? caregiverPalette.primary : caregiverPalette.muted}
            />
            <Text
              style={[styles.tabText, activeTab === "timeline" && styles.tabTextActive]}
              allowFontScaling
            >
              Daily Inputs
            </Text>
          </TouchableOpacity>

          {canRecordMeal ? (
            <TouchableOpacity
              style={[styles.tabButton, activeTab === "meal" && styles.tabButtonActive]}
              onPress={() => setActiveTab("meal")}
              accessibilityRole="button"
              accessibilityLabel="Log Meal Tab"
            >
              <Ionicons
                name="restaurant"
                size={15}
                color={activeTab === "meal" ? caregiverPalette.primary : caregiverPalette.muted}
              />
              <Text
                style={[styles.tabText, activeTab === "meal" && styles.tabTextActive]}
                allowFontScaling
              >
                Log Meal
              </Text>
            </TouchableOpacity>
          ) : null}

          {canTasks ? (
            <TouchableOpacity
              style={[styles.tabButton, activeTab === "tasks" && styles.tabButtonActive]}
              onPress={() => setActiveTab("tasks")}
              accessibilityRole="button"
              accessibilityLabel="Care Tasks Tab"
            >
              <Ionicons
                name="checkbox"
                size={15}
                color={activeTab === "tasks" ? caregiverPalette.primary : caregiverPalette.muted}
              />
              <Text
                style={[styles.tabText, activeTab === "tasks" && styles.tabTextActive]}
                allowFontScaling
              >
                Care Tasks
              </Text>
            </TouchableOpacity>
          ) : null}

          <TouchableOpacity
            style={[styles.tabButton, activeTab === "info" && styles.tabButtonActive]}
            onPress={() => setActiveTab("info")}
            accessibilityRole="button"
            accessibilityLabel="Patient Info Tab"
          >
            <Ionicons
              name="information-circle"
              size={15}
              color={activeTab === "info" ? caregiverPalette.primary : caregiverPalette.muted}
            />
            <Text
              style={[styles.tabText, activeTab === "info" && styles.tabTextActive]}
              allowFontScaling
            >
              Info
            </Text>
          </TouchableOpacity>
        </ScrollView>

        {/* Tab 1: Glucose Log (Preserves exact test requirements) */}
        {activeTab === "glucose" ? (
          <View style={styles.tabContentBlock}>
            {successMessage ? (
              <AlertBanner tone="success" title="Recorded" message={successMessage} />
            ) : null}

            {errorMessage ? (
              <AlertBanner tone="critical" title="Submission Failed" message={errorMessage} />
            ) : null}

            {canRecord ? (
              <GlucoseEntryForm
                onSubmit={(data) => {
                  setSuccessMessage(null);
                  setErrorMessage(null);
                  ingest.mutate(data);
                }}
                isSubmitting={ingest.isPending}
                testID="caregiver-glucose-form"
              />
            ) : canRead ? (
              <AlertBanner
                tone="info"
                title="View-only access"
                message="Your relationship allows viewing this patient's glucose records but not recording new readings."
              />
            ) : null}

            {canRead ? (
              <>
                <Divider label="Observation Feed" />
                <GlucoseTimeline
                  readings={feed.readings}
                  isLoading={feed.isLoading}
                  isError={feed.isError}
                  onRetry={() => feed.refetch()}
                  testID="caregiver-glucose-timeline"
                />
              </>
            ) : null}
          </View>
        ) : null}

        {/* Tab 2: Daily Chronological Inputs Timeline */}
        {activeTab === "timeline" ? (
          <CaregiverDailyTimeline patientId={patient.patient_id} />
        ) : null}

        {/* Tab 3: Meal Entry Form */}
        {activeTab === "meal" && canRecordMeal ? (
          <CaregiverMealEntryForm
            patientId={patient.patient_id}
            onSuccess={() => {
              void feed.refetch();
              void queryClient.invalidateQueries({ queryKey: ["caregivers", "timeline", patient.patient_id] });
            }}
          />
        ) : null}

        {/* Tab 4: Care Tasks */}
        {activeTab === "tasks" && canTasks ? (
          <CaregiverTasksSection
            patientId={patient.patient_id}
            canComplete={canCompleteTasks}
          />
        ) : null}

        {/* Tab 5: Relationship & Authorization Info */}
        {activeTab === "info" ? (
          <View style={styles.infoCard}>
            <View style={styles.infoHeader}>
              <View style={styles.infoIconCircle}>
                <Ionicons name="shield-checkmark" size={18} color={caregiverPalette.primary} />
              </View>
              <View>
                <Text style={styles.infoTitle} allowFontScaling>
                  Delegated Care Authorization
                </Text>
                <Text style={styles.infoSubtitle} allowFontScaling>
                  Legal and medical caregiving boundary
                </Text>
              </View>
            </View>

            <View style={styles.infoField}>
              <Text style={styles.infoFieldLabel} allowFontScaling>
                Patient Name
              </Text>
              <Text style={styles.infoFieldValue} allowFontScaling>
                {patient.name}
              </Text>
            </View>

            <View style={styles.infoField}>
              <Text style={styles.infoFieldLabel} allowFontScaling>
                Relationship Status
              </Text>
              <Text style={styles.infoFieldValue} allowFontScaling>
                {patient.relationship_label || "Primary Family Caregiver"} (Verified)
              </Text>
            </View>

            <View style={styles.infoField}>
              <Text style={styles.infoFieldLabel} allowFontScaling>
                Granted Permissions
              </Text>
              <View style={styles.capsBadgeList}>
                {patient.capabilities.map((cap) => (
                  <View key={cap} style={styles.capTokenBadge}>
                    <Ionicons name="checkmark-circle" size={12} color={caregiverPalette.emeraldDark} />
                    <Text style={styles.capTokenText} allowFontScaling>
                      {cap.replace(/_/g, " ")}
                    </Text>
                  </View>
                ))}
              </View>
            </View>

            <View style={styles.privacyNoticeBox}>
              <Ionicons name="lock-closed" size={15} color={caregiverPalette.sky} />
              <Text style={styles.privacyNoticeText} allowFontScaling>
                <Text style={styles.boldText}>Information Asymmetry Protection:</Text> Medical prescriptions, doctor notes, and internal risk calculations remain confidential to clinicians. Caregivers see food intake, logged blood sugars, and routine tasks to assist loved ones safely.
              </Text>
            </View>
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: caregiverPalette.appBackground,
  },
  content: {
    padding: 16,
    gap: 14,
  },
  scrollContent: {
    padding: 16,
    gap: 14,
    paddingBottom: spacing.xxl,
  },
  patientBannerCard: {
    backgroundColor: caregiverPalette.surface,
    borderRadius: caregiverRadii.lg,
    padding: 15,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    ...caregiverShadow.card,
  },
  bannerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  avatarWrapper: {
    position: "relative",
  },
  patientInitialsBadge: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: caregiverPalette.surfaceTeal,
    borderWidth: 1.5,
    borderColor: caregiverPalette.tealSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  patientInitialsText: {
    fontSize: 16,
    fontWeight: "800",
    color: caregiverPalette.tealDark,
    letterSpacing: 0.5,
  },
  bannerActiveDot: {
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
  bannerActiveDotInner: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: caregiverPalette.emerald,
  },
  bannerTextCol: {
    flex: 1,
    gap: 3,
  },
  bannerTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  bannerPatientName: {
    fontSize: 17,
    fontWeight: "800",
    color: caregiverPalette.ink,
    letterSpacing: -0.2,
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
  bannerSubtitle: {
    fontSize: 12,
    color: caregiverPalette.muted,
  },
  tabBarScroll: {
    flexDirection: "row",
    backgroundColor: caregiverPalette.surfaceSoft,
    borderRadius: caregiverRadii.md,
    padding: 4,
    gap: 4,
  },
  tabButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: caregiverRadii.sm,
  },
  tabButtonActive: {
    backgroundColor: caregiverPalette.surface,
    ...caregiverShadow.subtle,
  },
  tabText: {
    fontSize: 12,
    fontWeight: "600",
    color: caregiverPalette.muted,
  },
  tabTextActive: {
    color: caregiverPalette.primary,
    fontWeight: "800",
  },
  tabContentBlock: {
    gap: 14,
  },
  infoCard: {
    backgroundColor: caregiverPalette.surface,
    borderRadius: caregiverRadii.lg,
    padding: 16,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    gap: 14,
    ...caregiverShadow.card,
  },
  infoHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  infoIconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: caregiverPalette.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  infoTitle: {
    fontSize: 15,
    fontWeight: "800",
    color: caregiverPalette.ink,
  },
  infoSubtitle: {
    fontSize: 11,
    color: caregiverPalette.muted,
  },
  infoField: {
    gap: 4,
  },
  infoFieldLabel: {
    fontSize: 11,
    fontWeight: "800",
    color: caregiverPalette.muted,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  infoFieldValue: {
    fontSize: 14,
    fontWeight: "700",
    color: caregiverPalette.ink,
  },
  capsBadgeList: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 4,
  },
  capTokenBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: caregiverPalette.emeraldSoft,
    paddingHorizontal: 9,
    paddingVertical: 3.5,
    borderRadius: caregiverRadii.pill,
    borderWidth: 1,
    borderColor: caregiverPalette.emeraldBorder,
  },
  capTokenText: {
    fontSize: 11,
    color: caregiverPalette.emeraldDark,
    fontWeight: "700",
    textTransform: "capitalize",
  },
  privacyNoticeBox: {
    flexDirection: "row",
    gap: 10,
    backgroundColor: caregiverPalette.surfaceBlue,
    borderRadius: caregiverRadii.md,
    padding: 12,
    borderWidth: 1,
    borderColor: caregiverPalette.skyBorder,
    alignItems: "flex-start",
  },
  privacyNoticeText: {
    flex: 1,
    fontSize: 11,
    color: "#0369A1",
    lineHeight: 17,
  },
  boldText: {
    fontWeight: "700",
  },
});