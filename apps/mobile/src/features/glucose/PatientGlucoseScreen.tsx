import React, { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../auth/AuthProvider";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { Divider } from "../../components/primitives/Divider";
import { Button } from "../../components/primitives/Button";
import { EmptyState } from "../../components/primitives/EmptyState";
import { colors, radii, spacing } from "../../theming/tokens";
import { GlucoseEntryForm } from "./GlucoseEntryForm";
import { GlucoseTimeline } from "./GlucoseTimeline";
import { useGlucoseFeed } from "./useGlucoseFeed";
import { useIngestGlucose } from "./useIngestGlucose";
import { evaluateGlucose } from "./glucoseRanges";
import type { ApiErrorDetails } from "../../services/api/errors";
import type { IngestGlucoseResponse } from "../../services/schemas/clinical";

export type PatientGlucoseScreenProps = {
  patientId?: string;
  onBack?: () => void;
  testID?: string;
};

/**
 * Consistent clinical palettes for the logbook (anchored to design tokens).
 */
const palette = {
  teal700: "#0F766E",
  teal600: "#0D9488",
  tealBg: "#F0FDFA",
  tealBorder: "#A7F3D2",
  green: "#6EE7B7",
  body: "#334155",
  border: "rgba(15, 23, 42, 0.07)",
} as const;

export function PatientGlucoseScreen({
  patientId: propPatientId,
  onBack,
  testID,
}: PatientGlucoseScreenProps) {
  const { state } = useAuth();
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const authUser = state.name === "authenticated" ? state.user : null;
  const isPatientRole = authUser?.role === "Patient";
  const resolvedPatientId = propPatientId ?? authUser?.patient_id ?? null;

  // Query and mutation hooks
  const feed = useGlucoseFeed(resolvedPatientId, {
    enabled: isPatientRole && Boolean(resolvedPatientId),
  });

  const ingest = useIngestGlucose({
    patientId: resolvedPatientId,
    onSuccess: (response: IngestGlucoseResponse) => {
      setErrorMessage(null);
      if ((response as any).sync_status === "SAVED_LOCALLY") {
        setSuccessMessage(`Reading of ${response.value_mg_dl} mg/dL saved on this device (Waiting to sync).`);
      } else {
        setSuccessMessage(`Reading of ${response.value_mg_dl} mg/dL recorded and synced successfully.`);
      }
    },
    onError: (error: unknown) => {
      setSuccessMessage(null);
      const apiError = error as ApiErrorDetails | undefined;

      if (apiError?.httpStatus === 403) {
        setErrorMessage("Access denied. Your patient record is inactive or access has been revoked.");
      } else if (apiError?.httpStatus === 409) {
        setErrorMessage("A conflicting submission is already in progress. Please wait a moment.");
      } else if (apiError?.httpStatus === 429) {
        const retry = apiError.retryAfterSeconds;
        setErrorMessage(
          retry
            ? `Too many requests. Please wait ${retry} seconds before recording again.`
            : "Too many requests. Please wait a moment before trying again."
        );
      } else if (apiError?.kind === "NETWORK_ERROR") {
        setErrorMessage("Unable to connect. Your glucose reading has not been submitted.");
      } else {
        setErrorMessage(apiError?.message ?? "An unexpected error occurred. Please try again.");
      }
    },
  });

  // Guard: Role must be Patient
  if (!isPatientRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Glucose"
          onBack={onBack}
          leadingLabel={onBack ? "Back" : undefined}
        />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="The glucose logging screen is only available in Patient mode."
          />
          {onBack ? (
            <Button label="Return to Main Menu" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  // Guard: Patient identity must be linked
  if (!resolvedPatientId) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Glucose"
          onBack={onBack}
          leadingLabel={onBack ? "Back" : undefined}
        />
        <View style={styles.content}>
          <View testID="unlinked-patient-state">
            <EmptyState
              title="Account Linking Required"
              message="Your account is not yet linked to a patient profile. Please contact your clinic coordinator to activate your patient record."
            />
          </View>
          {onBack ? (
            <Button label="Return to Main Menu" variant="outline" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  // Calculate high-level metrics if readings are available
  const readings = feed.readings ?? [];
  type ValidReading = (typeof readings)[number] & { value_mg_dl: number };
  const validReadings = readings.filter(
    (r): r is ValidReading => typeof r.value_mg_dl === "number" && !isNaN(r.value_mg_dl)
  );
  const totalCount = validReadings.length;
  const inTargetCount = validReadings.filter(
    (r) => r.value_mg_dl >= 70 && r.value_mg_dl <= 140
  ).length;
  const inTargetPct = totalCount > 0 ? Math.round((inTargetCount / totalCount) * 100) : null;
  const sorted = [...validReadings].sort((a, b) => {
    const timeA = new Date(a.taken_at).getTime() || 0;
    const timeB = new Date(b.taken_at).getTime() || 0;
    return timeB - timeA;
  });
  const latestReading = sorted[0];
  const latestStatus = latestReading
    ? evaluateGlucose(latestReading.value_mg_dl, latestReading.tag)
    : null;

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Glucose Logbook"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
        actions={
          <View style={styles.headerProtocolPill}>
            <View style={styles.headerProtocolDot} />
            <Text style={styles.headerProtocolText} allowFontScaling>
              Active Log
            </Text>
          </View>
        }
      />

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {successMessage ? (
          <AlertBanner
            tone="success"
            title="Recorded"
            message={successMessage}
          />
        ) : null}

        {errorMessage ? (
          <AlertBanner
            tone="critical"
            title="Submission Failed"
            message={errorMessage}
          />
        ) : null}

        {/* Metabolic Summary Hero (When readings exist) */}
        {totalCount > 0 ? (
          <View style={styles.summaryCard}>
            <View style={styles.summaryDeco} pointerEvents="none" />
            <View style={styles.metricsRow}>
              <View style={styles.metricItem}>
                <View style={styles.metricLabelRow}>
                  <Ionicons name="pulse" size={11} color="rgba(255,255,255,0.65)" />
                  <Text style={styles.metricLabel} allowFontScaling>
                    Latest Reading
                  </Text>
                </View>
                <View style={styles.metricValueRow}>
                  <Text style={styles.metricValue} allowFontScaling>
                    {latestReading ? latestReading.value_mg_dl : "—"}
                  </Text>
                  {latestReading ? (
                    <Text style={styles.metricUnit} allowFontScaling>
                      mg/dL
                    </Text>
                  ) : null}
                </View>
              </View>

              <View style={styles.metricDivider} />

              <View style={styles.metricItem}>
                <View style={styles.metricLabelRow}>
                  <Ionicons name="checkmark-circle" size={11} color={palette.green} />
                  <Text style={styles.metricLabel} allowFontScaling>
                    In Target Range
                  </Text>
                </View>
                <View style={styles.metricValueRow}>
                  <Text style={[styles.metricValue, { color: palette.green }]} allowFontScaling>
                    {inTargetPct !== null ? `${inTargetPct}%` : "—"}
                  </Text>
                </View>
              </View>

              <View style={styles.metricDivider} />

              <View style={styles.metricItem}>
                <View style={styles.metricLabelRow}>
                  <Ionicons name="albums-outline" size={11} color="rgba(255,255,255,0.65)" />
                  <Text style={styles.metricLabel} allowFontScaling>
                    Total Readings
                  </Text>
                </View>
                <View style={styles.metricValueRow}>
                  <Text style={styles.metricValue} allowFontScaling>
                    {totalCount}
                  </Text>
                </View>
              </View>
            </View>

            {latestStatus ? (
              <View style={styles.latestStatusRow}>
                <Ionicons
                  name={
                    latestStatus.category === "target"
                      ? "checkmark-circle"
                      : latestStatus.category === "elevated"
                      ? "trending-up"
                      : latestStatus.category === "low"
                      ? "alert-circle"
                      : "warning"
                  }
                  size={13}
                  color={latestStatus.color}
                />
                <Text style={styles.latestStatusText} allowFontScaling>
                  {latestStatus.label}
                </Text>
                <Text style={styles.latestStatusDesc} numberOfLines={1} allowFontScaling>
                  {latestStatus.description}
                </Text>
              </View>
            ) : null}
          </View>
        ) : null}

        {/* Clinical Target Ranges Reference Card */}
        <View style={styles.targetGuideCard}>
          <View style={styles.targetGuideHeader}>
            <View style={styles.targetGuideIcon}>
              <Ionicons name="information" size={14} color={palette.teal700} />
            </View>
            <View style={styles.targetGuideTitles}>
              <Text style={styles.targetGuideTitle} allowFontScaling>
                Standard Glycemic Targets
              </Text>
              <Text style={styles.targetGuideSub} allowFontScaling>
                Indicative ranges in mg/dL
              </Text>
            </View>
          </View>
          <View style={styles.targetGuideRow}>
            <View style={styles.targetChip}>
              <View style={[styles.targetDot, { backgroundColor: palette.green }]} />
              <Text style={styles.targetChipLabel} allowFontScaling>
                Fasting: 70–99
              </Text>
            </View>
            <View style={styles.targetChip}>
              <View style={[styles.targetDot, { backgroundColor: palette.green }]} />
              <Text style={styles.targetChipLabel} allowFontScaling>
                Post-Meal: &lt;140
              </Text>
            </View>
            <View style={styles.targetChip}>
              <View style={[styles.targetDot, { backgroundColor: "#FBBF24" }]} />
              <Text style={styles.targetChipLabel} allowFontScaling>
                Elevated: 140+
              </Text>
            </View>
          </View>
        </View>

        {/* Record Blood Glucose Entry Form */}
        <GlucoseEntryForm
          onSubmit={(data) => {
            setSuccessMessage(null);
            setErrorMessage(null);
            ingest.mutate(data);
          }}
          isSubmitting={ingest.isPending}
          testID="patient-glucose-form"
        />

        {/* Divider / Feed Separator */}
        <Divider label="Observation Feed" />

        {/* Historical Timeline */}
        <GlucoseTimeline
          readings={feed.readings}
          isLoading={feed.isLoading}
          isError={feed.isError}
          onRetry={() => feed.refetch()}
          testID="patient-glucose-timeline"
        />
      </ScrollView>
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
    gap: spacing.md,
  },
  scrollContent: {
    padding: spacing.md,
    gap: spacing.sm,
    paddingBottom: spacing.xxl + 20,
  },
  headerProtocolPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: palette.border,
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderRadius: radii.pill,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1,
  },
  headerProtocolDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: palette.teal600,
  },
  headerProtocolText: {
    fontSize: 10,
    fontWeight: "700",
    color: palette.teal700,
    letterSpacing: 0.2,
  },
  summaryCard: {
    backgroundColor: colors.primary,
    borderRadius: 20,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    gap: 12,
    overflow: "hidden",
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.22,
    shadowRadius: 20,
    elevation: 5,
  },
  summaryDeco: {
    position: "absolute",
    top: -70,
    right: -50,
    width: 170,
    height: 170,
    borderRadius: 85,
    backgroundColor: "rgba(255, 255, 255, 0.07)",
  },
  metricsRow: {
    flexDirection: "row",
    alignItems: "stretch",
  },
  metricItem: {
    flex: 1,
    alignItems: "center",
    gap: 4,
  },
  metricLabelRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  metricLabel: {
    fontSize: 9,
    fontWeight: "800",
    color: "rgba(255, 255, 255, 0.66)",
    textTransform: "uppercase",
    letterSpacing: 0.8,
  },
  metricValueRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 3,
  },
  metricValue: {
    fontSize: 21,
    fontWeight: "800",
    color: "#FFFFFF",
    letterSpacing: -0.4,
  },
  metricUnit: {
    fontSize: 10,
    fontWeight: "700",
    color: "rgba(255, 255, 255, 0.66)",
  },
  metricDivider: {
    width: 1,
    alignSelf: "stretch",
    backgroundColor: "rgba(255, 255, 255, 0.16)",
  },
  latestStatusRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(255, 255, 255, 0.08)",
    borderRadius: radii.lg,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  latestStatusText: {
    fontSize: 11,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  latestStatusDesc: {
    flex: 1,
    fontSize: 11,
    fontWeight: "500",
    color: "rgba(255, 255, 255, 0.75)",
  },
  targetGuideCard: {
    backgroundColor: palette.tealBg,
    borderRadius: 16,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderWidth: 1,
    borderColor: palette.tealBorder,
    gap: spacing.xs,
  },
  targetGuideHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  targetGuideIcon: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: palette.tealBorder,
    alignItems: "center",
    justifyContent: "center",
  },
  targetGuideTitles: {
    flex: 1,
  },
  targetGuideTitle: {
    fontSize: 12,
    fontWeight: "800",
    color: palette.teal700,
  },
  targetGuideSub: {
    fontSize: 10,
    fontWeight: "500",
    color: palette.body,
  },
  targetGuideRow: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  targetChip: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
    borderRadius: radii.pill,
    paddingHorizontal: 6,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: palette.border,
    gap: 5,
  },
  targetDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  targetChipLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: palette.body,
  },
});