import React, { useCallback, useMemo, useRef, useState } from "react";
import {
  Animated,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  doctorPalette,
  doctorRadii,
  doctorSoftShadow,
} from "../doctorDesign";
import type { PatientSummaryResponse } from "../../../services/schemas/patients";
import {
  useCohortClinicalSummary,
  COHORT_PERIOD_DAYS,
  type CohortPeriodKey,
} from "../useCohortClinicalSummary";
import {
  DoctorHomeHeader,
  ClinicalSnapshot,
  AttentionPatients,
  CohortControlCard,
  GlucoseTrendCard,
  PatientStatusDistribution,
  MonitoringStatusCard,
  ClinicalTrendsCard,
  CareGapsCard,
  CardiometabolicCard,
  AIReviewSummaryCard,
  ReportsSummaryCard,
  DoctorQuickActions,
  DoctorQrModal,
  SectionHeader,
  SegmentControl,
} from "../home";

export type DoctorHomeTabProps = {
  doctorName?: string | null;
  doctorAccountId?: string | null;
  doctorDisplayName?: string | null;
  facilityId?: string | null;
  patients: PatientSummaryResponse[];
  reviewCount: number;
  taskCount: number;
  isLoading?: boolean;
  onRefresh: () => Promise<void> | void;
  onSelectPatient: (patient: PatientSummaryResponse) => void;
  onNavigateToPatients: () => void;
  onNavigateToReview: () => void;
  onNavigateToTasks: () => void;
  onNavigateToWorkspaceHub: () => void;
  onNavigateToSubWorkspace: (
    sub: "monitoring" | "reports" | "plans" | "documents" | "messages" | "audit"
  ) => void;
  onSignOut?: () => void;
};

const PERIOD_OPTIONS = [
  { key: "7d", label: "7D" },
  { key: "30d", label: "30D" },
  { key: "90d", label: "90D" },
];

export function DoctorHomeTab({
  facilityId: propFacilityId,
  doctorAccountId,
  doctorDisplayName,
  patients,
  reviewCount: propReviewCount,
  taskCount: propTaskCount,
  isLoading = false,
  onRefresh,
  onSelectPatient,
  onNavigateToPatients,
  onNavigateToReview,
  onNavigateToTasks,
  onNavigateToWorkspaceHub,
  onNavigateToSubWorkspace,
}: DoctorHomeTabProps) {
  const facilityId = propFacilityId || "Facility 1";
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [period, setPeriod] = useState<CohortPeriodKey>("30d");
  const [qrModalVisible, setQrModalVisible] = useState(false);

  const summary = useCohortClinicalSummary(patients);

  const cohortHasData =
    summary.cohortByPeriod["7d"].sampleSize > 0 ||
    summary.cohortByPeriod["30d"].sampleSize > 0 ||
    summary.cohortByPeriod["90d"].sampleSize > 0;

  // Derived "last synced": the most recent successful clinician-feed fetch
  // (react-query dataUpdatedAt) — no effect/setState cascade needed.
  const lastSyncedAt = summary.hasFeedQueriesSettled ? summary.latestFeedUpdateAt : null;

  const handlePullToRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([onRefresh(), summary.refreshCohort()]);
    } finally {
      setIsRefreshing(false);
    }
  }, [onRefresh, summary]);

  const activePatients = patients.filter((p) => p.active).length;

  const hypoAlerts = useMemo(
    () =>
      summary.attentionPatients.filter((entry) =>
        entry.flags.some((flag) => /hypoglycem/i.test(flag.label))
      ).length,
    [summary.attentionPatients]
  );

  const statusDist = summary.statusByPeriod[period];
  const selectedTrend = summary.trendsByPeriod[period];
  const selectedMean = summary.meanByWindow[period];

  const trendHasData =
    selectedTrend.tir.current !== null ||
    selectedTrend.mean.current !== null ||
    selectedTrend.gmi.current !== null;

  const quickActions = [
    {
      key: "patients",
      label: "Patient Directory",
      subLabel: `${activePatients} active cohort records`,
      icon: "people-outline" as const,
      onPress: onNavigateToPatients,
      badges: activePatients || undefined,
    },
    {
      key: "review",
      label: "AI Decision Queue",
      subLabel: summary.reviewTotal > 0 ? `${summary.reviewTotal} to validate` : "Queue clear",
      icon: "sparkles-outline" as const,
      onPress: onNavigateToReview,
      badges: summary.isReviewLoading ? undefined : summary.reviewTotal,
    },
    {
      key: "tasks",
      label: "Care Tasks & Gaps",
      subLabel: `${summary.careTaskTotal} pending items`,
      icon: "clipboard-outline" as const,
      onPress: onNavigateToTasks,
      badges: summary.isTasksLoading ? undefined : summary.careTaskTotal,
    },
    {
      key: "telemetry",
      label: "Live Telemetry",
      subLabel: "Real-time glucose feed",
      icon: "pulse-outline" as const,
      onPress: () => onNavigateToSubWorkspace("monitoring"),
    },
    {
      key: "reports",
      label: "Official Reports",
      subLabel: "Downloadable PDF engine",
      icon: "document-text-outline" as const,
      onPress: () => onNavigateToSubWorkspace("reports"),
    },
    {
      key: "hub",
      label: "Clinical Workspace Hub",
      subLabel: "Sub-workspaces & audits",
      icon: "grid-outline" as const,
      onPress: onNavigateToWorkspaceHub,
    },
  ];

  return (
    <>
      <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={isRefreshing || isLoading}
          onRefresh={handlePullToRefresh}
          tintColor={doctorPalette.primary}
          colors={[doctorPalette.primary]}
        />
      }
    >
      {/* Search bar (existing Doctor Home DNA) */}
      <View style={styles.searchBarContainer}>
        <View style={styles.searchBar}>
          <Ionicons name="search" size={20} color={doctorPalette.muted} style={styles.searchIcon} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search patients, UHID, symptoms…"
            placeholderTextColor={doctorPalette.quiet}
            value={searchQuery}
            onChangeText={(text) => {
              setSearchQuery(text);
              if (text.trim().length > 1) {
                onNavigateToPatients();
              }
            }}
            autoCapitalize="none"
            autoCorrect={false}
          />
        </View>
        <DoctorHomeQrButton onPress={() => setQrModalVisible(true)} />
      </View>

      {/* Facility + last-synced strip */}
      <DoctorHomeHeader facilityId={facilityId} lastSyncedAt={lastSyncedAt} />

      {/* Clinical Workflows */}
      <View style={styles.workflowRow}>
        <WorkflowSquare
          icon="people"
          label="Cohort"
          active
          count={patients.length}
          accessibilityLabel={`Patient Cohort, ${patients.length} records`}
          onPress={() => {
            setPeriod("30d");
            onNavigateToPatients();
          }}
        />
        <WorkflowSquare
          icon="sparkles"
          label="AI Review"
          tint="#D97706"
          count={summary.reviewTotal > 0 ? summary.reviewTotal : undefined}
          dot={summary.isReviewLoading ? false : summary.reviewTotal > 0}
          accessibilityLabel={`AI Review Queue, ${summary.isReviewLoading ? "…" : summary.reviewTotal} pending`}
          onPress={onNavigateToReview}
        />
        <WorkflowSquare
          icon="pulse"
          label="Telemetry"
          tint="#7C3AED"
          accessibilityLabel="Longitudinal Telemetry Monitoring"
          onPress={() => onNavigateToSubWorkspace("monitoring")}
        />
        <WorkflowSquare
          icon="document-text"
          label="Reports PDF"
          tint={doctorPalette.primary}
          accessibilityLabel="Official clinical PDF reports"
          onPress={() => onNavigateToSubWorkspace("reports")}
        />
      </View>

      {/* 1. Today's Clinical Snapshot */}
      <ClinicalSnapshot
        activePatients={activePatients}
        needAttention={summary.attentionPatients.length}
        cohortTir={summary.cohortByPeriod["30d"].tirPct}
        hypoAlerts={hypoAlerts}
        isLoading={summary.isLoadingFeed}
        hasCohortData={cohortHasData}
      />

      {/* 2. AI Review Summary */}
      <AIReviewSummaryCard
        total={summary.reviewTotal}
        kinds={summary.reviewKinds}
        onOpen={onNavigateToReview}
        isLoading={summary.isReviewLoading}
      />

      {/* 3. Reports Summary */}
      <ReportsSummaryCard onOpen={() => onNavigateToSubWorkspace("reports")} lastSyncedDays={null} />

      {/* 4. Patients Who Need Attention */}
      <AttentionPatients
        patients={summary.attentionPatients}
        onSelectPatient={(id) => {
          const patient = patients.find((p) => p.patient_id === id);
          if (patient) onSelectPatient(patient);
        }}
        onViewAll={onNavigateToPatients}
        isLoading={summary.isLoadingFeed}
        emptyMessage="All analyzed patients are meeting their glycemic targets within the 14-day monitoring window."
      />

      {/* 5-10. Command Center — period-aware */}
      <View style={styles.periodBlock}>
        <View style={styles.periodHead}>
          <View>
            <SectionHeader title="Command Center" />
            <Text style={styles.periodSub} allowFontScaling>
              Whole-cohort analysis & trends
            </Text>
          </View>
          <SegmentControl
            options={PERIOD_OPTIONS}
            selected={period}
            onSelect={(key) => setPeriod(key as CohortPeriodKey)}
            accessibilityHint={(o) => `Analyze the cohort over the last ${COHORT_PERIOD_DAYS[o.key as CohortPeriodKey]} days`}
          />
        </View>

        <CohortControlCard
          metrics={summary.cohortByPeriod[period]}
          analyzedCount={summary.analyzedCount}
          periodLabel={`last ${COHORT_PERIOD_DAYS[period]} days`}
          isLoading={summary.isLoadingFeed}
        />

        <GlucoseTrendCard
          dailySeries={summary.dailySeriesByWindow[period]}
          mean7d={summary.meanByWindow["7d"]}
          mean30d={summary.meanByWindow["30d"]}
          mean90d={summary.meanByWindow["90d"]}
          previous7d={summary.previousMeanByWindow["7d"]}
          isLoading={summary.isLoadingFeed}
          hasData={selectedMean !== null}
        />

        <PatientStatusDistribution distribution={statusDist} analyzedCount={summary.analyzedCount} onViewAll={onNavigateToPatients} />

        <MonitoringStatusCard
          upToDate={summary.monitoring30d.upToDate}
          limited={summary.monitoring30d.limited}
          noRecentData={summary.monitoring30d.noRecentData}
          analyzed={summary.monitoring30d.analyzed}
        />

        <ClinicalTrendsCard
          trend={selectedTrend}
          isLoading={summary.isLoadingFeed}
          hasData={trendHasData}
          onViewAll={onNavigateToReview}
        />
      </View>

      {/* 11. Care Gaps */}
      <CareGapsCard
        counts={summary.careGaps}
        totalTasks={summary.careTaskTotal}
        onViewAll={onNavigateToTasks}
        isLoading={summary.isTasksLoading}
        hasNumericData={summary.careGaps.total > 0}
      />

      {/* 12. Cardiometabolic Health */}
      <CardiometabolicCard isLoading={false} hasNumericData={false} />

      {/* 13. Quick Actions */}
      <DoctorQuickActions actions={quickActions} />

      {/* Clinical Safety & Decision Support Governance */}
      <View style={styles.safetyCard}>
        <View style={styles.safetyHeader}>
          <View style={styles.safetyIconBadge}>
            <Ionicons name="shield-checkmark" size={18} color={doctorPalette.primary} />
          </View>
          <View style={styles.safetyHeaderTextCol}>
            <Text style={styles.safetyTitle} allowFontScaling>
              Deterministic Clinical Intelligence
            </Text>
            <Text style={styles.safetySubtitle} allowFontScaling>
              ADA / EASD Mathematical Compliance
            </Text>
          </View>
        </View>
        <Text style={styles.safetyBodyText} allowFontScaling>
          All glycemic indices, time-in-range measurements, and longitudinal baselines on this dashboard
          are computed with strict mathematical determinism from confirmed observations. Cohort figures
          reflect real glucose data only — no synthetic fill across the {summary.analyzedCount} patients
          analyzed. Machine-generated observations require human doctor sign-off before entering
          authoritative medical records.
        </Text>
        <View style={styles.safetyBadgesRow}>
          <View style={styles.safetyPill}>
            <Ionicons name="checkmark-circle" size={12} color="#15803D" />
            <Text style={styles.safetyPillText} allowFontScaling>ADA 2024 Standards</Text>
          </View>
          <View style={styles.safetyPill}>
            <Ionicons name="calculator" size={12} color={doctorPalette.primary} />
            <Text style={styles.safetyPillText} allowFontScaling>Deterministic Math</Text>
          </View>
          <View style={styles.safetyPill}>
            <Ionicons name="person-circle" size={12} color="#7C3AED" />
            <Text style={styles.safetyPillText} allowFontScaling>Clinician Sign-off</Text>
          </View>
        </View>
      </View>
    </ScrollView>

      <DoctorQrModal
        visible={qrModalVisible}
        doctorAccountId={doctorAccountId}
        doctorDisplayName={doctorDisplayName}
        facilityId={facilityId}
        onClose={() => setQrModalVisible(false)}
      />
    </>
  );
}

function DoctorHomeQrButton({ onPress }: { onPress: () => void }) {
  const pressAnim = useRef(new Animated.Value(0)).current;

  const handlePressIn = () => {
    Animated.spring(pressAnim, {
      toValue: 1,
      speed: 25,
      bounciness: 0,
      useNativeDriver: false,
    }).start();
  };

  const handlePressOut = () => {
    Animated.spring(pressAnim, {
      toValue: 0,
      friction: 4,
      tension: 80,
      useNativeDriver: false,
    }).start();
  };

  const handlePress = () => {
    Animated.sequence([
      Animated.timing(pressAnim, {
        toValue: 1.25,
        duration: 75,
        useNativeDriver: false,
      }),
      Animated.spring(pressAnim, {
        toValue: 0,
        friction: 3.5,
        tension: 85,
        useNativeDriver: false,
      }),
    ]).start();
    onPress();
  };

  const scale = pressAnim.interpolate({
    inputRange: [0, 1, 1.25],
    outputRange: [1, 0.90, 0.84],
  });

  const rotate = pressAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "-6deg"],
  });

  const backgroundColor = pressAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [doctorPalette.surface, doctorPalette.surfaceLime],
  });

  const borderColor = pressAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [doctorPalette.borderSubtle, doctorPalette.primary],
  });

  return (
    <Pressable
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
      onPress={handlePress}
      accessibilityRole="button"
      accessibilityLabel="Open doctor account QR code"
      hitSlop={6}
    >
      <Animated.View
        style={[
          styles.qrButton,
          {
            backgroundColor,
            borderColor,
            transform: [{ scale }, { rotate }],
          },
        ]}
      >
        <Ionicons name="qr-code-outline" size={22} color={doctorPalette.ink} />
      </Animated.View>
    </Pressable>
  );
}

function WorkflowSquare({
  icon,
  label,
  active,
  tint,
  dot,
  count,
  onPress,
  accessibilityLabel,
}: {
  icon: React.ComponentProps<typeof Ionicons>["name"];
  label: string;
  active?: boolean;
  tint?: string;
  dot?: boolean;
  count?: number | string;
  onPress: () => void;
  accessibilityLabel: string;
}) {
  const iconColor = active ? doctorPalette.ink : (tint ?? doctorPalette.primary);
  return (
    <TouchableOpacity
      style={[styles.categorySquare, active ? styles.categorySquareActive : styles.categorySquareDefault]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      activeOpacity={0.75}
    >
      <View style={styles.categoryIconWrap}>
        <View
          style={[
            styles.categoryIconCircle,
            active
              ? { backgroundColor: "rgba(255, 255, 255, 0.65)" }
              : tint
              ? { backgroundColor: `${tint}15` }
              : { backgroundColor: doctorPalette.surfaceBlue },
          ]}
        >
          <Ionicons name={icon} size={19} color={iconColor} />
        </View>
        {count !== undefined && Number(count) > 0 ? (
          <View style={styles.categoryBadge}>
            <Text style={styles.categoryBadgeText} allowFontScaling numberOfLines={1}>
              {count}
            </Text>
          </View>
        ) : dot ? (
          <View style={styles.categoryDot} />
        ) : null}
      </View>
      <Text style={[styles.categoryLabel, active ? styles.categoryLabelActive : null]} allowFontScaling numberOfLines={1}>
        {label}
      </Text>
    </TouchableOpacity>
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
    paddingBottom: 130,
    gap: 22,
  },
  searchBarContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  searchBar: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 16,
    height: 50,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    ...doctorSoftShadow,
  },
  searchIcon: {
    marginRight: 10,
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    color: doctorPalette.ink,
    paddingVertical: 8,
  },
  qrButton: {
    width: 50,
    height: 50,
    borderRadius: 14,
    backgroundColor: doctorPalette.surface,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    ...doctorSoftShadow,
  },
  workflowRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 10,
  },
  categorySquare: {
    flex: 1,
    height: 80,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  categorySquareActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderWidth: 1,
    borderColor: doctorPalette.limeBorder,
    ...doctorSoftShadow,
  },
  categorySquareDefault: {
    backgroundColor: doctorPalette.surface,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    ...doctorSoftShadow,
  },
  categoryIconWrap: {
    position: "relative",
  },
  categoryIconCircle: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: "center",
    justifyContent: "center",
  },
  categoryBadge: {
    position: "absolute",
    top: -4,
    right: -6,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: doctorPalette.primary,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 4,
    borderWidth: 1.5,
    borderColor: doctorPalette.surface,
  },
  categoryBadgeText: {
    fontSize: 9,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  categoryDot: {
    position: "absolute",
    top: -2,
    right: -3,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#F59E0B",
  },
  categoryLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  categoryLabelActive: {
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  periodBlock: {
    gap: 22,
  },
  periodHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    gap: 12,
  },
  periodSub: {
    fontSize: 12,
    color: doctorPalette.muted,
    marginTop: 2,
  },
  safetyCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    padding: 18,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    gap: 12,
    ...doctorSoftShadow,
  },
  safetyHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  safetyIconBadge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  safetyHeaderTextCol: {
    flex: 1,
  },
  safetyTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  safetySubtitle: {
    fontSize: 11,
    color: doctorPalette.muted,
    marginTop: 1,
  },
  safetyBodyText: {
    fontSize: 12,
    lineHeight: 18,
    color: doctorPalette.muted,
  },
  safetyBadgesRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    paddingTop: 4,
  },
  safetyPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: doctorPalette.surfaceSoft,
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
  },
  safetyPillText: {
    fontSize: 10,
    fontWeight: "700",
    color: doctorPalette.inkSecondary,
  },
});