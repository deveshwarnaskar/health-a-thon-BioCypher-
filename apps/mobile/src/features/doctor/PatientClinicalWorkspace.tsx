import React, { useState, useMemo } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, useWindowDimensions, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../auth/AuthProvider";
import { usePatientDetail } from "./usePatientDetail";
import { useClinicianFeed } from "./useClinicianFeed";
import { useMedicationPlans } from "./useMedicationPlans";
import { useDoctorDocuments } from "./useDoctorDocuments";
import { useClinicalInsights } from "./useClinicalInsights";
import { useCareTasks } from "./useCareTasks";
import { useDoctorNotifications } from "./useDoctorNotifications";
import { useGenerateReport } from "./useGenerateReport";
import { usePatientClinicalState } from "./usePatientClinicalState";
import { CreateMedicationPlanScreen } from "./CreateMedicationPlanScreen";
import { ArtifactDetailScreen } from "./ArtifactDetailScreen";
import {
  calculateGlycemicMetrics,
  calculatePersonalBaseline,
  calculateTemporalAlignment,
  calculateDataCoverage,
  type GlucoseInputObservation,
  type MealInputObservation,
} from "../../services/clinical/deterministicIntelligence";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { LoadingState } from "../../components/primitives/LoadingState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { EmptyState } from "../../components/primitives/EmptyState";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { ReportViewerModal } from "./ReportViewerModal";
import type { ClinicalDocumentItem } from "./api";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import type { PatientSummaryResponse } from "../../services/schemas/patients";
import type {
  ClinicianGlucoseObservation,
  ClinicianMealObservation,
} from "../../services/schemas/clinical";
import { READING_TAG_LABELS, type ReadingTag } from "../../services/schemas/clinical";

export type PatientWorkspaceTab =
  | "snapshot"
  | "reports"
  | "timeline"
  | "glucose"
  | "meals"
  | "medications"
  | "tasks"
  | "documents"
  | "ai-review"
  | "communication"
  | "audit";

function formatObservationDay(isoString: string): string {
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString.slice(0, 10);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const isYesterday = d.toDateString() === yesterday.toDateString();

    const formatted = d.toLocaleDateString("en-IN", {
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
    });

    if (isToday) return `Today · ${formatted}`;
    if (isYesterday) return `Yesterday · ${formatted}`;
    return formatted;
  } catch {
    return isoString.slice(0, 10);
  }
}

function formatObservationTime(isoString: string): string {
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString.slice(11, 16);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return isoString.slice(11, 16);
  }
}

export type PatientClinicalWorkspaceProps = {
  patient: PatientSummaryResponse;
  onBack: () => void;
  initialTab?: PatientWorkspaceTab;
  testID?: string;
};

export function PatientClinicalWorkspace({
  patient,
  onBack,
  initialTab = "snapshot",
  testID,
}: PatientClinicalWorkspaceProps) {
  const { width } = useWindowDimensions();
  const isCompact = width < 760;
  const { state } = useAuth();
  const authUser = state.name === "authenticated" ? state.user : null;
  const isDoctorRole = authUser?.role === "Doctor";

  const patientId = patient.patient_id;
  const detail = usePatientDetail(patientId, { enabled: isDoctorRole });
  const feed = useClinicianFeed(patientId, { enabled: isDoctorRole });
  const plans = useMedicationPlans(patientId, { enabled: isDoctorRole });
  const docs = useDoctorDocuments(patientId, { enabled: isDoctorRole });
  const insights = useClinicalInsights(patientId, { enabled: isDoctorRole });
  const tasks = useCareTasks(patientId, { enabled: isDoctorRole });
  const notifications = useDoctorNotifications(patientId, { enabled: isDoctorRole });
  const reportGen = useGenerateReport(patientId);

  const [windowDays, setWindowDays] = useState<number>(14);
  const clinicalStateQuery = usePatientClinicalState(patientId, windowDays, { enabled: isDoctorRole });
  const cs = clinicalStateQuery.state;

  const [activeTab, setActiveTab] = useState<PatientWorkspaceTab>(initialTab);
  const [showCreatePlanModal, setShowCreatePlanModal] = useState(false);
  const [showCreateTaskModal, setShowCreateTaskModal] = useState(false);
  const [showUploadDocModal, setShowUploadDocModal] = useState(false);
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [selectedViewerDoc, setSelectedViewerDoc] = useState<ClinicalDocumentItem | null>(null);

  // New task form state
  const [taskDescription, setTaskDescription] = useState("");
  // Upload doc form state
  const [docFilename, setDocFilename] = useState("");
  const [docKind, setDocKind] = useState("chart_image");

  // Selected item inspector state for timeline/glucose/meals
  const [inspectedObservation, setInspectedObservation] = useState<any | null>(null);

  const shown = detail.patient ?? patient;
  const feedItems = feed.feed?.items || [];

  const glucoseItems: GlucoseInputObservation[] = feedItems
    .filter(
      (item): item is ClinicianGlucoseObservation & { kind: "glucose" } =>
        item.kind === "glucose" && item.value_mg_dl != null
    )
    .map((g) => ({
      id: g.observation_id,
      value_mg_dl: g.value_mg_dl!,
      taken_at: g.taken_at,
      tag: g.tag,
    }));

  const mealItems: MealInputObservation[] = feedItems
    .filter(
      (item): item is ClinicianMealObservation & { kind: "meal" } =>
        item.kind === "meal"
    )
    .map((m) => ({
      id: m.observation_id,
      description: m.description,
      recorded_at: m.recorded_at,
      portion_label: m.portion_label,
      carbs_grams: m.carbs_grams,
    }));

  // Authoritative Deterministic Backend State (Primary single source of truth)
  const backendMetrics = cs?.glycemic_metrics;
  const backendCoverage = cs?.data_quality;
  const backendLongitudinal = cs?.longitudinal_comparison;
  const backendPatterns = cs?.temporal_patterns;
  const backendMealAssocs = cs?.meal_associations;
  const backendLab = cs?.laboratory_profile;
  const backendCardio = cs?.cardiometabolic_profile;
  const backendScreenings = cs?.complication_screenings;
  const backendAlerts = cs?.patient_summary?.clinical_alerts || [];

  const metrics = backendMetrics
    ? {
        meanMgDl: backendMetrics.mean_glucose,
        standardDeviationMgDl: backendMetrics.standard_deviation,
        coefficientOfVariationPct: backendMetrics.coefficient_of_variation_pct,
        timeInRangePct: backendMetrics.tir_in_range_pct,
        timeBelowRangePct: backendMetrics.tbr_below_range_pct,
        timeAboveRangePct: backendMetrics.tar_above_range_pct,
        estimatedA1cPct: backendMetrics.estimated_a1c_pct,
        gmiPct: backendMetrics.gmi_pct,
        variabilityCategory: backendMetrics.variability_category,
        interpretationSummary: backendMetrics.clinical_summary_note,
      }
    : calculateGlycemicMetrics(glucoseItems, windowDays);

  const variabilityCategory = backendMetrics?.variability_category ?? (
    (metrics.coefficientOfVariationPct != null && metrics.coefficientOfVariationPct > 36)
      ? "HIGH_VARIABILITY"
      : "STABLE"
  );

  const baseline = calculatePersonalBaseline(glucoseItems, windowDays);
  const coverage = backendCoverage
    ? {
        isContinuous: backendCoverage.is_adequate_coverage,
        coverageText: `${backendCoverage.coverage_pct}% (${backendCoverage.active_logging_days}/${backendCoverage.window_days} active days)`,
        glucoseReadingCount: backendCoverage.total_valid_readings,
        mealRecordCount: mealItems.length,
      }
    : calculateDataCoverage(glucoseItems, mealItems, windowDays);

  const temporalAlignments = calculateTemporalAlignment(mealItems, glucoseItems, 240);
  const [timelineFilter, setTimelineFilter] = useState<"all" | "meal" | "glucose">("all");

  const dailyGroups = useMemo(() => {
    const sorted = [...feedItems].sort((a, b) => {
      const timeA = new Date(a.kind === "glucose" ? (a as any).taken_at : (a as any).recorded_at).getTime();
      const timeB = new Date(b.kind === "glucose" ? (b as any).taken_at : (b as any).recorded_at).getTime();
      return timeB - timeA;
    });

    const groupsMap = new Map<string, {
      dateKey: string;
      dayLabel: string;
      items: any[];
      glucoseValues: number[];
      mealCount: number;
      glucoseCount: number;
    }>();

    for (const item of sorted) {
      const isGlucose = item.kind === "glucose";
      const isoTime = isGlucose ? (item as any).taken_at : (item as any).recorded_at;
      if (!isoTime) continue;
      const dateKey = isoTime.slice(0, 10);

      if (!groupsMap.has(dateKey)) {
        groupsMap.set(dateKey, {
          dateKey,
          dayLabel: formatObservationDay(isoTime),
          items: [],
          glucoseValues: [],
          mealCount: 0,
          glucoseCount: 0,
        });
      }

      const group = groupsMap.get(dateKey)!;

      if (isGlucose) {
        group.glucoseCount += 1;
        const val = (item as any).value_mg_dl;
        if (typeof val === "number" && !isNaN(val)) {
          group.glucoseValues.push(val);
        }
      } else {
        group.mealCount += 1;
      }

      let associatedExcursion = null;
      if (!isGlucose) {
        const align = temporalAlignments.find(
          (ta) => ta.mealId === item.observation_id && ta.deltaMinutes > 0
        );
        if (align) {
          associatedExcursion = align;
        }
      }

      group.items.push({
        ...item,
        isoTime,
        formattedTime: formatObservationTime(isoTime),
        associatedExcursion,
      });
    }

    return Array.from(groupsMap.values()).map((g) => ({
      ...g,
      meanGlucose: g.glucoseValues.length > 0
        ? Math.round(g.glucoseValues.reduce((a, b) => a + b, 0) / g.glucoseValues.length)
        : null,
    }));
  }, [feedItems, temporalAlignments]);

  if (selectedArtifactId) {
    return (
      <ArtifactDetailScreen
        artifactId={selectedArtifactId}
        onBack={() => setSelectedArtifactId(null)}
      />
    );
  }

  if (showCreatePlanModal) {
    return (
      <CreateMedicationPlanScreen
        patient={shown}
        onCancel={() => setShowCreatePlanModal(false)}
        onCreated={() => {
          setShowCreatePlanModal(false);
          plans.refetch();
        }}
      />
    );
  }

  const handleCreateTask = async () => {
    if (!taskDescription.trim()) return;
    try {
      await tasks.createTask({
        patient_id: patientId,
        assigned_to_user_id: patientId,
        description: taskDescription.trim(),
      });
      setTaskDescription("");
      setShowCreateTaskModal(false);
    } catch {
      // Handled by hook error state
    }
  };

  const handleUploadDoc = async () => {
    if (!docFilename.trim()) return;
    try {
      await docs.uploadDocument({
        filename: docFilename.trim(),
        mime_type: "application/pdf",
        content_base64: "JVBERi0xLjQKJcTl8uXrCg==", // Safe standard PDF header placeholder
        kind: docKind,
      });
      setDocFilename("");
      setShowUploadDocModal(false);
    } catch {
      // Handled by hook error state
    }
  };

  const handleGenerateReport = async () => {
    try {
      const doc = await reportGen.generateReport();
      if (doc) {
        setSelectedViewerDoc(doc);
      }
    } catch {
      // Handled by hook error state
    }
  };

  const tabs: { key: PatientWorkspaceTab; label: string; icon: React.ComponentProps<typeof Ionicons>["name"] }[] = [
    { key: "snapshot", label: "Snapshot", icon: "pulse" },
    { key: "reports", label: "Reports & PDF", icon: "document-text" },
    { key: "timeline", label: "Daily Inputs", icon: "calendar" },
    { key: "glucose", label: "Glucose", icon: "water" },
    { key: "meals", label: "Meals & Nutrition", icon: "restaurant" },
    { key: "medications", label: "Medications", icon: "medkit" },
    { key: "tasks", label: "Care Tasks", icon: "checkbox" },
    { key: "documents", label: "Docs & Archive", icon: "folder-open" },
    { key: "ai-review", label: "AI & Evidence", icon: "sparkles" },
    { key: "communication", label: "Messages", icon: "chatbubble-ellipses" },
    { key: "audit", label: "Audit", icon: "shield-checkmark" },
  ];

  return (
    <View style={styles.container} testID={testID}>
      {/* 1. Compact Pinned Top App Bar */}
      <View style={styles.topAppBar}>
        <View style={styles.topAppRow}>
          <TouchableOpacity
            accessibilityRole="button"
            accessibilityLabel="Back to surveillance"
            style={styles.backButton}
            onPress={onBack}
          >
            <Ionicons name="arrow-back" size={18} color={doctorPalette.ink} />
          </TouchableOpacity>

          <View style={styles.topPatientHeaderCol}>
            <View style={styles.topPatientTitleRow}>
              <Text style={styles.topPatientName} numberOfLines={1}>{shown.name}</Text>
              <Badge
                label={shown.active ? "Active" : "Inactive"}
                tone={shown.active ? "success" : "neutral"}
              />
            </View>
            <Text style={styles.topPatientMeta} numberOfLines={1}>
              UHID: <Text style={styles.metaBold}>{shown.uh_id}</Text>
            </Text>
          </View>

          <View style={styles.topActionsRow}>
            <Pressable
              style={styles.topActionBtnOutline}
              disabled={reportGen.isGenerating}
              onPress={handleGenerateReport}
              accessibilityRole="button"
              accessibilityLabel="Compile PDF report"
            >
              <Ionicons name="document-text-outline" size={13} color={doctorPalette.ink} />
              <Text style={styles.topActionBtnText}>
                {reportGen.isGenerating ? "Compiling…" : "PDF"}
              </Text>
            </Pressable>
            <Pressable
              style={styles.topActionBtnPrimary}
              onPress={() => setShowCreatePlanModal(true)}
              accessibilityRole="button"
              accessibilityLabel="Author medication plan"
            >
              <Ionicons name="add" size={14} color="#FFFFFF" />
              <Text style={styles.topActionBtnPrimaryText}>+ Plan</Text>
            </Pressable>
          </View>
        </View>

        {/* Sub-Navigation Tabs */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.tabsRowContainer}
          style={styles.tabsRow}
        >
          {tabs.map((tab) => {
            const isActive = activeTab === tab.key;
            return (
              <Pressable
                key={tab.key}
                style={[styles.tabButton, isActive ? styles.tabButtonActive : null]}
                onPress={() => setActiveTab(tab.key)}
              >
                <Ionicons
                  name={tab.icon}
                  size={15}
                  color={isActive ? doctorPalette.ink : doctorPalette.muted}
                />
                <Text style={[styles.tabText, isActive ? styles.tabTextActive : null]}>
                  {tab.label}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {/* 2. Floating Modals */}
      <Modal
        visible={showCreateTaskModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowCreateTaskModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Ionicons name="checkbox-outline" size={20} color={doctorPalette.primary} />
              <Text style={styles.modalTitle}>Add Care Task for {shown.name}</Text>
            </View>
            <TextInput
              style={styles.modalInput}
              placeholder="Directives for care team or patient follow-up…"
              placeholderTextColor={colors.textSecondary}
              value={taskDescription}
              onChangeText={setTaskDescription}
              multiline
            />
            <View style={styles.modalActions}>
              <Button
                label="Cancel"
                variant="ghost"
                onPress={() => setShowCreateTaskModal(false)}
              />
              <Button
                label={tasks.isCreating ? "Saving…" : "Save Task"}
                variant="primary"
                disabled={tasks.isCreating || !taskDescription.trim()}
                onPress={handleCreateTask}
              />
            </View>
          </View>
        </View>
      </Modal>

      <Modal
        visible={showUploadDocModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowUploadDocModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Ionicons name="cloud-upload-outline" size={20} color={doctorPalette.primary} />
              <Text style={styles.modalTitle}>Upload Document for {shown.name}</Text>
            </View>
            <TextInput
              style={styles.modalInput}
              placeholder="Document filename (e.g. Lab_Report_Lipid.pdf)…"
              placeholderTextColor={colors.textSecondary}
              value={docFilename}
              onChangeText={setDocFilename}
            />
            <View style={styles.kindSelectorRow}>
              {["chart_image", "lab_report", "referral"].map((k) => (
                <Pressable
                  key={k}
                  style={[styles.kindPill, docKind === k ? styles.kindPillActive : null]}
                  onPress={() => setDocKind(k)}
                >
                  <Text style={[styles.kindText, docKind === k ? styles.kindTextActive : null]}>
                    {k.replace("_", " ")}
                  </Text>
                </Pressable>
              ))}
            </View>
            <View style={styles.modalActions}>
              <Button
                label="Cancel"
                variant="ghost"
                onPress={() => setShowUploadDocModal(false)}
              />
              <Button
                label={docs.isUploading ? "Uploading…" : "Upload to S3"}
                variant="primary"
                disabled={docs.isUploading || !docFilename.trim()}
                onPress={handleUploadDoc}
              />
            </View>
          </View>
        </View>
      </Modal>

      {/* 3. Tab Contents Scrollable Body */}
      <ScrollView
        style={styles.tabContentScroll}
        contentContainerStyle={styles.tabContentContainer}
        showsVerticalScrollIndicator={true}
      >
        {/* Patient Hero / Context Card */}
        <View style={styles.heroCard}>
          <View style={styles.heroMainRow}>
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>{shown.name.charAt(0)}</Text>
            </View>
            <View style={styles.heroInfoCol}>
              <View style={styles.heroTitleRow}>
                <Text style={styles.heroPatientName} numberOfLines={1}>{shown.name}</Text>
                <Badge
                  label={shown.active ? "Active" : "Inactive"}
                  tone={shown.active ? "success" : "neutral"}
                />
              </View>
              <Text style={styles.heroMetaLine} numberOfLines={1}>
                UHID: <Text style={styles.metaBold}>{shown.uh_id}</Text>
                {shown.facility_id ? (
                  <>
                    {" "}· Facility:{" "}
                    <Text style={styles.metaBold}>
                      {shown.facility_id.length > 12 ? `${shown.facility_id.slice(0, 8)}…` : shown.facility_id}
                    </Text>
                  </>
                ) : null}
              </Text>
            </View>
          </View>
          <View style={styles.heroSecondaryActionsRow}>
            <TouchableOpacity
              style={styles.heroActionPill}
              onPress={() => setShowCreateTaskModal(true)}
              accessibilityRole="button"
              accessibilityLabel="Add care task"
            >
              <Ionicons name="add-circle-outline" size={13} color={doctorPalette.ink} />
              <Text style={styles.heroActionPillText}>+ Care Task</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.heroActionPill}
              onPress={() => setShowUploadDocModal(true)}
              accessibilityRole="button"
              accessibilityLabel="Upload document"
            >
              <Ionicons name="cloud-upload-outline" size={13} color={doctorPalette.ink} />
              <Text style={styles.heroActionPillText}>Upload Document</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Analytics Reporting Period Bar */}
        <View style={styles.periodBarCard}>
          <View style={styles.periodBarLeft}>
            <Ionicons name="calendar-outline" size={13} color={doctorPalette.muted} />
            <Text style={styles.periodLabel}>Window:</Text>
            <View style={styles.periodButtonsRow}>
              {[7, 14, 30, 90].map((days) => (
                <Pressable
                  key={days}
                  style={[
                    styles.periodBtn,
                    windowDays === days ? styles.periodBtnActive : null,
                  ]}
                  onPress={() => setWindowDays(days)}
                  accessibilityRole="button"
                  accessibilityLabel={`${days} day reporting window`}
                >
                  <Text
                    style={[
                      styles.periodBtnText,
                      windowDays === days ? styles.periodBtnTextActive : null,
                    ]}
                  >
                    {days}d
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
          {cs?.engine_metadata ? (
            <View style={styles.engineBadgeContainer}>
              <Text style={styles.engineBadgeText}>
                ⚙ {cs.engine_metadata.version}
              </Text>
            </View>
          ) : null}
        </View>

        {/* Quick Glycemic Metrics Bar */}
        <View style={styles.metricsBarContainer}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.metricsBarScroll}
            style={styles.metricsBar}
          >
            <View style={styles.metricPill}>
              <Text style={styles.metricPillLabel}>Time in Range (70-180)</Text>
              <Text style={[styles.metricPillValue, { color: colors.leafGreen }]}>
                {metrics.timeInRangePct != null ? `${metrics.timeInRangePct}%` : "—"}
              </Text>
            </View>
            <View style={styles.metricPill}>
              <Text style={styles.metricPillLabel}>TBR (&lt;70 mg/dL)</Text>
              <Text style={[styles.metricPillValue, { color: colors.critical }]}>
                {metrics.timeBelowRangePct != null ? `${metrics.timeBelowRangePct}%` : "—"}
              </Text>
            </View>
            <View style={styles.metricPill}>
              <Text style={styles.metricPillLabel}>TAR (&gt;180 mg/dL)</Text>
              <Text style={[styles.metricPillValue, { color: colors.warning }]}>
                {metrics.timeAboveRangePct != null ? `${metrics.timeAboveRangePct}%` : "—"}
              </Text>
            </View>
            <View style={styles.metricPill}>
              <Text style={styles.metricPillLabel}>Mean Glucose</Text>
              <Text style={styles.metricPillValue}>
                {metrics.meanMgDl != null ? `${metrics.meanMgDl} mg/dL` : "—"}
              </Text>
            </View>
            <View style={styles.metricPill}>
              <Text style={styles.metricPillLabel}>Est. A1c / GMI</Text>
              <Text style={styles.metricPillValue}>
                {metrics.estimatedA1cPct != null ? `${metrics.estimatedA1cPct}%` : "—"}
              </Text>
            </View>
            <View style={styles.metricPill}>
              <Text style={styles.metricPillLabel}>Variability (CV)</Text>
              <Text style={[styles.metricPillValue, { color: (metrics.coefficientOfVariationPct ?? 0) > 36 ? colors.critical : colors.textPrimary }]}>
                {metrics.coefficientOfVariationPct != null ? `${metrics.coefficientOfVariationPct}%` : "—"}
              </Text>
            </View>
          </ScrollView>
        </View>

        {/* General Reference Ranges Banner */}
        <View style={styles.referenceBanner}>
          <Ionicons name="information-circle-outline" size={14} color={doctorPalette.muted} style={{ marginTop: 1 }} />
          <Text style={styles.referenceNoticeText}>
            General Reference Ranges: Fasting 80–130 mg/dL · Post-meal &lt;180 mg/dL · HbA1c &lt;7.0%.
            These are population reference thresholds and may not apply to this patient&apos;s
            individualized care plan. Authorize personalized targets when clinically indicated.
          </Text>
        </View>

        {reportGen.isSuccess && reportGen.generatedDocument ? (
          <View style={styles.reportSuccessBanner}>
            <View style={styles.reportSuccessHeader}>
              <Ionicons name="checkmark-circle" size={18} color="#15803D" />
              <View style={styles.reportSuccessTextCol}>
                <Text style={styles.reportSuccessTitle}>Clinical Report Ready</Text>
                <Text style={styles.reportSuccessText}>
                  {reportGen.generatedDocument.filename} (
                  {Math.round(reportGen.generatedDocument.file_size_bytes / 1024)} KB)
                </Text>
              </View>
            </View>
            <View style={styles.reportSuccessBtnRow}>
              <TouchableOpacity
                style={styles.reportActionBtnPrimary}
                onPress={() => setSelectedViewerDoc(reportGen.generatedDocument ?? null)}
                accessibilityRole="button"
                accessibilityLabel="View report in app"
                activeOpacity={0.8}
              >
                <Ionicons name="eye-outline" size={14} color="#FFFFFF" />
                <Text style={styles.reportActionBtnPrimaryText}>View In-App</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.reportActionBtnSecondary}
                onPress={() => setSelectedViewerDoc(reportGen.generatedDocument ?? null)}
                accessibilityRole="button"
                accessibilityLabel="Download report PDF"
                activeOpacity={0.8}
              >
                <Ionicons name="download-outline" size={14} color="#15803D" />
                <Text style={styles.reportActionBtnSecondaryText}>Download PDF</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : null}

        {/* TAB: SNAPSHOT */}
        {activeTab === "snapshot" && (
          <View style={styles.tabPane}>
            {/* Section A: Active Clinical Risk Flags */}
            {backendAlerts.length > 0 ? (
              <View style={styles.alertsContainer}>
                {backendAlerts.map((al, idx) => (
                  <View
                    key={idx}
                    style={[
                      styles.alertCard,
                      al.level === "HIGH" ? styles.alertCardHigh : styles.alertCardMod,
                    ]}
                  >
                    <Ionicons
                      name={al.level === "HIGH" ? "alert-circle" : "warning"}
                      size={18}
                      color={al.level === "HIGH" ? colors.critical : colors.warning}
                    />
                    <View style={styles.alertContent}>
                      <Text style={styles.alertCodeText}>[{al.level}] {al.code}</Text>
                      <Text style={styles.alertMsgText}>{al.message}</Text>
                    </View>
                  </View>
                ))}
              </View>
            ) : null}

            {/* Section B: Data Quality & Completeness Gate */}
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardTitleCol}>
                  <Text style={styles.cardTitle}>Data Quality & Completeness</Text>
                  <Text style={styles.cardSubtitle}>({windowDays}-Day Evaluation Window)</Text>
                </View>
                <Badge
                  label={backendCoverage?.is_adequate_coverage ? "Adequate Coverage" : "Suboptimal Telemetry"}
                  tone={backendCoverage?.is_adequate_coverage ? "success" : "warning"}
                />
              </View>
              <View style={styles.grid3}>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Coverage Ratio</Text>
                  <Text style={styles.gridCellValue}>{backendCoverage?.coverage_pct ?? "—"}%</Text>
                  <Text style={styles.gridCellSub}>{backendCoverage ? `${backendCoverage.active_logging_days}/${backendCoverage.window_days} active days` : "—"}</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Valid Readings</Text>
                  <Text style={styles.gridCellValue}>{backendCoverage?.total_valid_readings ?? "—"}</Text>
                  <Text style={styles.gridCellSub}>Expected: {backendCoverage?.expected_readings ?? "—"}</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Missing Days</Text>
                  <Text style={[styles.gridCellValue, { color: (backendCoverage?.missing_days_count ?? 0) > 3 ? colors.warning : colors.textPrimary }]}>
                    {backendCoverage?.missing_days_count ?? 0} days
                  </Text>
                  <Text style={styles.gridCellSub}>Last Sync: {backendCoverage?.last_sync ? backendCoverage.last_sync.slice(0, 10) : "N/A"}</Text>
                </View>
              </View>
            </View>

            {/* Section C: Authoritative Deterministic Glycemic Summary */}
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardTitleCol}>
                  <Text style={styles.cardTitle}>{windowDays}-Day Glycemic Summary</Text>
                  <Text style={styles.cardSubtitle}>Authoritative deterministic calculation</Text>
                </View>
                <Badge
                  label={`Variability: ${variabilityCategory}`}
                  tone={variabilityCategory === "HIGH_VARIABILITY" ? "warning" : "success"}
                />
              </View>

              <View style={styles.grid3}>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Mean Glucose</Text>
                  <Text style={styles.gridCellValue}>
                    {metrics.meanMgDl != null ? `${metrics.meanMgDl} mg/dL` : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>SD: ±{metrics.standardDeviationMgDl ?? "—"} mg/dL</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Glycemic Variability (CV)</Text>
                  <Text style={[styles.gridCellValue, { color: (metrics.coefficientOfVariationPct ?? 0) > 36 ? colors.critical : colors.textPrimary }]}>
                    {metrics.coefficientOfVariationPct != null ? `${metrics.coefficientOfVariationPct}%` : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>Target: &le; 36%</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>GMI / Est. A1c</Text>
                  <Text style={styles.gridCellValue}>
                    {metrics.gmiPct != null ? `${metrics.gmiPct}%` : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>eA1c: {metrics.estimatedA1cPct ?? "—"}%</Text>
                </View>
              </View>

              {/* Time in Range Breakdown */}
              <View style={styles.tirBreakdownRow}>
                <View style={[styles.tirPill, { backgroundColor: "#DCFCE7" }]}>
                  <Text style={[styles.tirPillNum, { color: "#166534" }]}>{metrics.timeInRangePct ?? "—"}%</Text>
                  <Text style={[styles.tirPillLabel, { color: "#166534" }]}>In Range (70-180)</Text>
                </View>
                <View style={[styles.tirPill, { backgroundColor: "#FEF3C7" }]}>
                  <Text style={[styles.tirPillNum, { color: "#92400E" }]}>{metrics.timeAboveRangePct ?? "—"}%</Text>
                  <Text style={[styles.tirPillLabel, { color: "#92400E" }]}>Above Range (&gt;180)</Text>
                </View>
                <View style={[styles.tirPill, { backgroundColor: "#FEE2E2" }]}>
                  <Text style={[styles.tirPillNum, { color: "#991B1B" }]}>{metrics.timeBelowRangePct ?? "—"}%</Text>
                  <Text style={[styles.tirPillLabel, { color: "#991B1B" }]}>Below Range (&lt;70)</Text>
                </View>
              </View>

              <Text style={styles.interpretationText}>{metrics.interpretationSummary}</Text>
            </View>

            {/* Section D: Longitudinal Glycemic Comparison */}
            {backendLongitudinal ? (
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <View style={styles.cardTitleCol}>
                    <Text style={styles.cardTitle}>Longitudinal Comparison</Text>
                    <Text style={styles.cardSubtitle}>({windowDays}d Current vs Preceding)</Text>
                  </View>
                  <Badge
                    label={backendLongitudinal.has_sufficient_history ? "Historical Active" : "Baseline Building"}
                    tone="neutral"
                  />
                </View>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View style={[styles.comparisonTable, { minWidth: 500 }]}>
                    <View style={styles.comparisonHeaderRow}>
                      <Text style={[styles.compCol, styles.compColHeader, { flex: 2.2 }]}>Metric</Text>
                      <Text style={[styles.compCol, styles.compColHeader]}>Current</Text>
                      <Text style={[styles.compCol, styles.compColHeader]}>Preceding</Text>
                      <Text style={[styles.compCol, styles.compColHeader]}>Delta</Text>
                      <Text style={[styles.compCol, styles.compColHeader]}>Trend</Text>
                    </View>
                    <View style={styles.comparisonRow}>
                      <Text style={[styles.compCol, { flex: 2.2, fontWeight: "600" }]}>Time in Range</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.tir_comparison.current_value ?? "—"}%</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.tir_comparison.previous_value ?? "—"}%</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.tir_comparison.delta != null ? `${backendLongitudinal.tir_comparison.delta > 0 ? "+" : ""}${backendLongitudinal.tir_comparison.delta}%` : "—"}</Text>
                      <Text style={[styles.compCol, { fontWeight: "700", color: backendLongitudinal.tir_comparison.trend_direction === "improving" ? colors.leafGreen : colors.textPrimary }]}>
                        {backendLongitudinal.tir_comparison.trend_direction}
                      </Text>
                    </View>
                    <View style={styles.comparisonRow}>
                      <Text style={[styles.compCol, { flex: 2.2, fontWeight: "600" }]}>Mean Glucose</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.mean_comparison.current_value ?? "—"}</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.mean_comparison.previous_value ?? "—"}</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.mean_comparison.delta != null ? `${backendLongitudinal.mean_comparison.delta > 0 ? "+" : ""}${backendLongitudinal.mean_comparison.delta}` : "—"}</Text>
                      <Text style={[styles.compCol, { fontWeight: "700", color: backendLongitudinal.mean_comparison.trend_direction === "improving" ? colors.leafGreen : colors.textPrimary }]}>
                        {backendLongitudinal.mean_comparison.trend_direction}
                      </Text>
                    </View>
                    <View style={styles.comparisonRow}>
                      <Text style={[styles.compCol, { flex: 2.2, fontWeight: "600" }]}>Variability (CV)</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.cv_comparison.current_value ?? "—"}%</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.cv_comparison.previous_value ?? "—"}%</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.cv_comparison.delta != null ? `${backendLongitudinal.cv_comparison.delta > 0 ? "+" : ""}${backendLongitudinal.cv_comparison.delta}%` : "—"}</Text>
                      <Text style={[styles.compCol, { fontWeight: "700", color: backendLongitudinal.cv_comparison.trend_direction === "improving" ? colors.leafGreen : colors.textPrimary }]}>
                        {backendLongitudinal.cv_comparison.trend_direction}
                      </Text>
                    </View>
                  </View>
                </ScrollView>
              </View>
            ) : null}

            {/* Section E: Diurnal & Time-Slot Patterns */}
            {backendPatterns ? (
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <View style={styles.cardTitleCol}>
                    <Text style={styles.cardTitle}>Diurnal Time-Slot Patterns</Text>
                    <Text style={styles.cardSubtitle}>
                      Weekday/Weekend: {backendPatterns.weekday_mean ?? "—"} / {backendPatterns.weekend_mean ?? "—"} mg/dL
                      {backendPatterns.weekday_weekend_delta != null ? ` (Δ ${backendPatterns.weekday_weekend_delta} mg/dL)` : ""}
                    </Text>
                  </View>
                </View>
                <View style={styles.slotsGrid}>
                  {[
                    { label: "Morning", slot: backendPatterns.morning },
                    { label: "Afternoon", slot: backendPatterns.afternoon },
                    { label: "Evening", slot: backendPatterns.evening },
                    { label: "Overnight", slot: backendPatterns.overnight },
                  ].map(({ label, slot }) => (
                    <View key={label} style={styles.slotCard}>
                      <Text style={styles.slotTitle}>{label} ({slot.hours_label})</Text>
                      <Text style={styles.slotMean}>{slot.mean_glucose != null ? `${slot.mean_glucose} mg/dL` : "—"}</Text>
                      <Text style={styles.slotCount}>{slot.count} observations</Text>
                      <Text style={styles.slotNote}>{slot.pattern_note}</Text>
                    </View>
                  ))}
                </View>
              </View>
            ) : null}

            {/* Section F: Meal ↔ Glucose Temporal Associations */}
            {backendMealAssocs && backendMealAssocs.length > 0 ? (
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <View style={styles.cardTitleCol}>
                    <Text style={styles.cardTitle}>Meal ↔ Glucose Associations</Text>
                    <Text style={styles.cardSubtitle}>Deterministic non-causal temporal analysis</Text>
                  </View>
                  <Badge label={`${backendMealAssocs.length} Analyzed`} tone="neutral" />
                </View>
                <View style={styles.mealAssocList}>
                  {backendMealAssocs.slice(0, 5).map((ma, idx) => (
                    <View key={idx} style={styles.mealAssocItem}>
                      <View style={styles.mealAssocHeader}>
                        <Text style={styles.mealAssocTitle}>{ma.description || "Meal Intake"}</Text>
                        <Text style={styles.mealAssocTime}>{ma.meal_timestamp ? ma.meal_timestamp.slice(11, 16) : ""}</Text>
                      </View>
                      <View style={styles.mealAssocMetrics}>
                        <Text style={styles.mealAssocMetric}>Pre: {ma.pre_meal_glucose_mg_dl ?? "—"} mg/dL</Text>
                        <Text style={styles.mealAssocMetric}>Peak: {ma.post_meal_peak_mg_dl ?? "—"} mg/dL</Text>
                        <Text style={[styles.mealAssocMetric, { fontWeight: "700", color: (ma.observed_delta_mg_dl ?? 0) > 50 ? colors.warning : colors.leafGreen }]}>
                          Δ {ma.observed_delta_mg_dl != null ? `+${ma.observed_delta_mg_dl}` : "—"} mg/dL
                        </Text>
                        <Text style={styles.mealAssocMetric}>TTP: {ma.time_to_peak_minutes ?? "—"}m</Text>
                      </View>
                    </View>
                  ))}
                </View>
              </View>
            ) : null}

            {/* Section G: Laboratory Profile & Section H: Cardiometabolic */}
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardTitle}>Laboratory & Cardiometabolic Profile</Text>
                <Badge label="Validated Biomarkers" tone="info" />
              </View>
              <View style={styles.grid3}>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>HbA1c</Text>
                  <Text style={styles.gridCellValue}>{backendLab?.hba1c?.latest?.value != null ? `${backendLab.hba1c.latest.value}%` : "—"}</Text>
                  <Text style={styles.gridCellSub}>{backendLab?.hba1c?.latest?.observed_at ? backendLab.hba1c.latest.observed_at.slice(0, 10) : "No lab record"}</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Serum Creatinine</Text>
                  <Text style={styles.gridCellValue}>{backendLab?.creatinine?.latest?.value != null ? `${backendLab.creatinine.latest.value} mg/dL` : "—"}</Text>
                  <Text style={styles.gridCellSub}>{backendLab?.creatinine?.latest?.observed_at ? backendLab.creatinine.latest.observed_at.slice(0, 10) : "Target: 0.6-1.2"}</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>eGFR (2021 CKD-EPI)</Text>
                  <Text style={styles.gridCellValue}>{backendLab?.egfr?.latest?.value != null ? `${backendLab.egfr.latest.value}` : "—"}</Text>
                  <Text style={styles.gridCellSub}>mL/min/1.73m2</Text>
                </View>
              </View>
              <View style={[styles.grid3, { marginTop: spacing.sm }]}>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Blood Pressure</Text>
                  <Text style={styles.gridCellValue}>
                    {backendCardio?.blood_pressure?.latest_systolic?.value != null && backendCardio?.blood_pressure?.latest_diastolic?.value != null
                      ? `${backendCardio.blood_pressure.latest_systolic.value}/${backendCardio.blood_pressure.latest_diastolic.value} mmHg`
                      : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>Target: &lt;130/80</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Body Weight</Text>
                  <Text style={styles.gridCellValue}>{backendCardio?.weight?.latest?.value != null ? `${backendCardio.weight.latest.value} kg` : "—"}</Text>
                  <Text style={styles.gridCellSub}>Target BMI &lt; 23</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Urine Albumin (uACR)</Text>
                  <Text style={styles.gridCellValue}>{backendLab?.uacr?.latest?.value != null ? `${backendLab.uacr.latest.value} mg/g` : "—"}</Text>
                  <Text style={styles.gridCellSub}>Normal: &lt;30 mg/g</Text>
                </View>
              </View>
            </View>

            {/* Section I: Preventive Complication Screening Schedule */}
            {backendScreenings && backendScreenings.length > 0 ? (
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <Text style={styles.cardTitle}>Preventive Complication Screening Schedule</Text>
                </View>
                <View style={styles.screeningsList}>
                  {backendScreenings.map((scr, idx) => (
                    <View key={idx} style={styles.screeningRow}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.screeningTitle}>{scr.category}</Text>
                        <Text style={styles.screeningMeta}>
                          Last: {scr.last_completed_at ?? "No Record"} · Due: {scr.due_date}
                        </Text>
                      </View>
                      <Badge
                        label={scr.status}
                        tone={scr.status === "OVERDUE" ? "critical" : (scr.status === "DUE_SOON" ? "warning" : "success")}
                      />
                    </View>
                  ))}
                </View>
              </View>
            ) : null}

            {/* Section L: Assistive AI Clinical Intelligence */}
            {insights.isLoading ? (
              <LoadingState label="Loading assistive AI clinical insights…" />
            ) : insights.insights ? (
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <View style={styles.cardTitleCol}>
                    <Text style={styles.cardTitle}>Assistive AI Clinical Interpretation</Text>
                    <Text style={styles.cardSubtitle}>Evidence-grounded documentation assistance</Text>
                  </View>
                  <Badge label={`Provider: ${insights.insights.provider}`} tone="info" />
                </View>
                <Text style={styles.aiNoteText}>
                  {insights.insights.metrics.clinical_summary_note ||
                    "Metabolic patterns analyzed with Indian dietary reference tables."}
                </Text>
                <View style={styles.aiFlagsRow}>
                  {insights.insights.metrics.dawn_phenomenon_suspected ? (
                    <Badge label="Dawn Phenomenon Suspected" tone="warning" />
                  ) : null}
                  <Badge
                    label={`Variability: ${insights.insights.metrics.variability_category}`}
                    tone="neutral"
                  />
                </View>
                <Text style={styles.disclaimerText}>
                  Note: Assistive clinical summaries are strictly downstream of deterministic calculations. Clinician retains sole prescribing authority.
                </Text>
              </View>
            ) : null}
          </View>
        )}

        {/* TAB: REPORTS & PDF */}
        {activeTab === "reports" && (
          <View style={styles.tabPane}>
            <View style={styles.paneHeaderRow}>
              <View style={styles.cardTitleCol}>
                <Text style={styles.paneTitle}>Clinical Analytics & Official Reports</Text>
                <Text style={styles.paneSub}>
                  Deterministic AGP evaluation, longitudinal trajectories, and exportable PDF summaries
                </Text>
              </View>
              <Button
                label={reportGen.isGenerating ? "Compiling PDF…" : "Compile Official PDF"}
                variant="primary"
                disabled={reportGen.isGenerating}
                onPress={handleGenerateReport}
              />
            </View>

            {/* Generated Report Ready Banner */}
            {reportGen.isSuccess && reportGen.generatedDocument ? (
              <View style={styles.reportSuccessBanner}>
                <View style={styles.reportSuccessHeader}>
                  <Ionicons name="checkmark-circle" size={18} color="#15803D" />
                  <View style={styles.reportSuccessTextCol}>
                    <Text style={styles.reportSuccessTitle}>Official Report Compiled Successfully</Text>
                    <Text style={styles.reportSuccessText}>
                      {reportGen.generatedDocument.filename} (
                      {Math.round(reportGen.generatedDocument.file_size_bytes / 1024)} KB)
                    </Text>
                  </View>
                </View>
                <View style={styles.reportSuccessBtnRow}>
                  <TouchableOpacity
                    style={styles.reportActionBtnPrimary}
                    onPress={() => setSelectedViewerDoc(reportGen.generatedDocument ?? null)}
                    accessibilityRole="button"
                    accessibilityLabel="View report in app"
                    activeOpacity={0.8}
                  >
                    <Ionicons name="eye-outline" size={14} color="#FFFFFF" />
                    <Text style={styles.reportActionBtnPrimaryText}>View In-App</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.reportActionBtnSecondary}
                    onPress={() => setSelectedViewerDoc(reportGen.generatedDocument ?? null)}
                    accessibilityRole="button"
                    accessibilityLabel="Download report PDF"
                    activeOpacity={0.8}
                  >
                    <Ionicons name="download-outline" size={14} color="#15803D" />
                    <Text style={styles.reportActionBtnSecondaryText}>Download PDF</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ) : null}

            {/* Section 1: Standardized Ambulatory Glucose Profile (AGP) Report */}
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardTitleCol}>
                  <Text style={styles.cardTitle}>Ambulatory Glucose Profile (AGP) Standards</Text>
                  <Text style={styles.cardSubtitle}>
                    International consensus metrics for {windowDays}-day surveillance period
                  </Text>
                </View>
                <Badge
                  label={backendCoverage?.is_adequate_coverage ? "Adequate Telemetry" : "Suboptimal Telemetry"}
                  tone={backendCoverage?.is_adequate_coverage ? "success" : "warning"}
                />
              </View>

              <View style={styles.grid3}>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Time in Range (70–180)</Text>
                  <Text style={[styles.gridCellValue, { color: colors.leafGreen }]}>
                    {metrics.timeInRangePct != null ? `${metrics.timeInRangePct}%` : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>Consensus Target: &gt;70%</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Below Range (&lt;70)</Text>
                  <Text style={[styles.gridCellValue, { color: colors.critical }]}>
                    {metrics.timeBelowRangePct != null ? `${metrics.timeBelowRangePct}%` : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>Target: &lt;4% (L1) &lt;1% (L2)</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Above Range (&gt;180)</Text>
                  <Text style={[styles.gridCellValue, { color: colors.warning }]}>
                    {metrics.timeAboveRangePct != null ? `${metrics.timeAboveRangePct}%` : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>Target: &lt;25%</Text>
                </View>
              </View>

              <View style={[styles.grid3, { marginTop: 4 }]}>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Mean Glucose</Text>
                  <Text style={styles.gridCellValue}>
                    {metrics.meanMgDl != null ? `${metrics.meanMgDl} mg/dL` : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>SD: ±{metrics.standardDeviationMgDl ?? "—"} mg/dL</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Variability (CV)</Text>
                  <Text style={[styles.gridCellValue, { color: (metrics.coefficientOfVariationPct ?? 0) > 36 ? colors.critical : colors.textPrimary }]}>
                    {metrics.coefficientOfVariationPct != null ? `${metrics.coefficientOfVariationPct}%` : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>Target: &le;36%</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>GMI / Est. A1c</Text>
                  <Text style={styles.gridCellValue}>
                    {metrics.gmiPct != null ? `${metrics.gmiPct}%` : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>eA1c: {metrics.estimatedA1cPct ?? "—"}%</Text>
                </View>
              </View>

              <View style={styles.tirBreakdownRow}>
                <View style={[styles.tirPill, { backgroundColor: "#DCFCE7" }]}>
                  <Text style={[styles.tirPillNum, { color: "#166534" }]}>{metrics.timeInRangePct ?? "—"}%</Text>
                  <Text style={[styles.tirPillLabel, { color: "#166534" }]}>In Range (70–180)</Text>
                </View>
                <View style={[styles.tirPill, { backgroundColor: "#FEF3C7" }]}>
                  <Text style={[styles.tirPillNum, { color: "#92400E" }]}>{metrics.timeAboveRangePct ?? "—"}%</Text>
                  <Text style={[styles.tirPillLabel, { color: "#92400E" }]}>Above Range (&gt;180)</Text>
                </View>
                <View style={[styles.tirPill, { backgroundColor: "#FEE2E2" }]}>
                  <Text style={[styles.tirPillNum, { color: "#991B1B" }]}>{metrics.timeBelowRangePct ?? "—"}%</Text>
                  <Text style={[styles.tirPillLabel, { color: "#991B1B" }]}>Below Range (&lt;70)</Text>
                </View>
              </View>

              <View style={styles.agpSufficiencyBox}>
                <Text style={styles.agpSufficiencyText}>
                  Telemetry Completeness: {backendCoverage?.active_logging_days ?? "—"}/{backendCoverage?.window_days ?? windowDays} days active ({backendCoverage?.coverage_pct ?? "—"}% coverage) · {backendCoverage?.total_valid_readings ?? glucoseItems.length} validated SMBG readings indexed.
                </Text>
              </View>
            </View>

            {/* Section 2: Longitudinal Comparative Trajectory */}
            {backendLongitudinal ? (
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <View style={styles.cardTitleCol}>
                    <Text style={styles.cardTitle}>Longitudinal Glycemic Trajectory</Text>
                    <Text style={styles.cardSubtitle}>Current {windowDays}-day period vs preceding period</Text>
                  </View>
                  <Badge
                    label={backendLongitudinal.has_sufficient_history ? "Longitudinal Active" : "Baseline Phase"}
                    tone="neutral"
                  />
                </View>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View style={[styles.comparisonTable, { minWidth: 500 }]}>
                    <View style={styles.comparisonHeaderRow}>
                      <Text style={[styles.compCol, styles.compColHeader, { flex: 2.2 }]}>Metric</Text>
                      <Text style={[styles.compCol, styles.compColHeader]}>Current</Text>
                      <Text style={[styles.compCol, styles.compColHeader]}>Preceding</Text>
                      <Text style={[styles.compCol, styles.compColHeader]}>Delta</Text>
                      <Text style={[styles.compCol, styles.compColHeader]}>Direction</Text>
                    </View>
                    <View style={styles.comparisonRow}>
                      <Text style={[styles.compCol, { flex: 2.2, fontWeight: "600" }]}>Time in Range (TIR)</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.tir_comparison.current_value ?? "—"}%</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.tir_comparison.previous_value ?? "—"}%</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.tir_comparison.delta != null ? `${backendLongitudinal.tir_comparison.delta > 0 ? "+" : ""}${backendLongitudinal.tir_comparison.delta}%` : "—"}</Text>
                      <Text style={[styles.compCol, { fontWeight: "700", color: backendLongitudinal.tir_comparison.trend_direction === "improving" ? colors.leafGreen : colors.textPrimary }]}>
                        {backendLongitudinal.tir_comparison.trend_direction}
                      </Text>
                    </View>
                    <View style={styles.comparisonRow}>
                      <Text style={[styles.compCol, { flex: 2.2, fontWeight: "600" }]}>Mean Glucose</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.mean_comparison.current_value ?? "—"} mg/dL</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.mean_comparison.previous_value ?? "—"} mg/dL</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.mean_comparison.delta != null ? `${backendLongitudinal.mean_comparison.delta > 0 ? "+" : ""}${backendLongitudinal.mean_comparison.delta}` : "—"}</Text>
                      <Text style={[styles.compCol, { fontWeight: "700", color: backendLongitudinal.mean_comparison.trend_direction === "improving" ? colors.leafGreen : colors.textPrimary }]}>
                        {backendLongitudinal.mean_comparison.trend_direction}
                      </Text>
                    </View>
                    <View style={styles.comparisonRow}>
                      <Text style={[styles.compCol, { flex: 2.2, fontWeight: "600" }]}>Variability (CV)</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.cv_comparison.current_value ?? "—"}%</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.cv_comparison.previous_value ?? "—"}%</Text>
                      <Text style={styles.compCol}>{backendLongitudinal.cv_comparison.delta != null ? `${backendLongitudinal.cv_comparison.delta > 0 ? "+" : ""}${backendLongitudinal.cv_comparison.delta}%` : "—"}</Text>
                      <Text style={[styles.compCol, { fontWeight: "700", color: backendLongitudinal.cv_comparison.trend_direction === "improving" ? colors.leafGreen : colors.textPrimary }]}>
                        {backendLongitudinal.cv_comparison.trend_direction}
                      </Text>
                    </View>
                  </View>
                </ScrollView>
              </View>
            ) : null}

            {/* Section 3: Organ System Biomarkers & Cardiometabolic Surveillance */}
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardTitleCol}>
                  <Text style={styles.cardTitle}>Renal & Cardiometabolic Staging</Text>
                  <Text style={styles.cardSubtitle}>Authoritative biomarker evaluations</Text>
                </View>
                <Badge label="Validated Labs" tone="info" />
              </View>
              <View style={styles.grid3}>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>HbA1c Laboratory</Text>
                  <Text style={styles.gridCellValue}>{backendLab?.hba1c?.latest?.value != null ? `${backendLab.hba1c.latest.value}%` : "—"}</Text>
                  <Text style={styles.gridCellSub}>{backendLab?.hba1c?.latest?.observed_at ? backendLab.hba1c.latest.observed_at.slice(0, 10) : "No lab test"}</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Serum Creatinine</Text>
                  <Text style={styles.gridCellValue}>{backendLab?.creatinine?.latest?.value != null ? `${backendLab.creatinine.latest.value} mg/dL` : "—"}</Text>
                  <Text style={styles.gridCellSub}>Target: 0.6–1.2</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>eGFR (CKD-EPI 2021)</Text>
                  <Text style={styles.gridCellValue}>{backendLab?.egfr?.latest?.value != null ? `${backendLab.egfr.latest.value}` : "—"}</Text>
                  <Text style={styles.gridCellSub}>mL/min/1.73m²</Text>
                </View>
              </View>
              <View style={[styles.grid3, { marginTop: 4 }]}>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Urine Albumin (uACR)</Text>
                  <Text style={styles.gridCellValue}>{backendLab?.uacr?.latest?.value != null ? `${backendLab.uacr.latest.value} mg/g` : "—"}</Text>
                  <Text style={styles.gridCellSub}>Normal: &lt;30 mg/g</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Blood Pressure</Text>
                  <Text style={styles.gridCellValue}>
                    {backendCardio?.blood_pressure?.latest_systolic?.value != null && backendCardio?.blood_pressure?.latest_diastolic?.value != null
                      ? `${backendCardio.blood_pressure.latest_systolic.value}/${backendCardio.blood_pressure.latest_diastolic.value} mmHg`
                      : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>Target: &lt;130/80</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Body Weight</Text>
                  <Text style={styles.gridCellValue}>{backendCardio?.weight?.latest?.value != null ? `${backendCardio.weight.latest.value} kg` : "—"}</Text>
                  <Text style={styles.gridCellSub}>Target BMI &lt;23</Text>
                </View>
              </View>
            </View>

            {/* Section 4: Document & Prescription Archive */}
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardTitleCol}>
                  <Text style={styles.cardTitle}>Patient Documents & Compiled Reports Archive</Text>
                  <Text style={styles.cardSubtitle}>
                    Official PDF summaries, prescriptions, and diagnostic uploads
                  </Text>
                </View>
                <Badge label={`${docs.documents.length} Files`} tone="neutral" />
              </View>

              {docs.isLoading ? (
                <LoadingState label="Loading patient documents…" />
              ) : docs.documents.length === 0 ? (
                <EmptyState
                  title="No documents yet"
                  message="Generate an official report or upload clinical documents to view them here."
                />
              ) : (
                <View style={styles.docList}>
                  {docs.documents.map((d) => (
                    <View key={d.id} style={styles.docRow}>
                      <View style={[styles.docIconBox, d.kind === "prescription" ? styles.docIconBoxPrescription : null]}>
                        <Ionicons
                          name={
                            d.kind === "prescription"
                              ? "medical"
                              : d.kind === "lab_report"
                              ? "flask"
                              : "document-text"
                          }
                          size={18}
                          color={d.kind === "prescription" ? "#0D9488" : doctorPalette.primary}
                        />
                      </View>
                      <View style={styles.docMetaCol}>
                        <View style={styles.docTitleRow}>
                          <Text style={styles.docTitle} numberOfLines={1}>{d.filename}</Text>
                          <Badge
                            label={d.kind.replace("_", " ").toUpperCase()}
                            tone={d.kind === "prescription" ? "success" : "info"}
                          />
                        </View>
                        <Text style={styles.docSub}>
                          {Math.round(d.file_size_bytes / 1024)} KB · Uploaded {new Date(d.created_at).toLocaleDateString()}
                        </Text>
                      </View>
                      <View style={styles.docBtnGroup}>
                        <TouchableOpacity
                          style={styles.docActionBtn}
                          onPress={() => setSelectedViewerDoc(d)}
                          accessibilityRole="button"
                          accessibilityLabel={`View document ${d.filename}`}
                          activeOpacity={0.8}
                        >
                          <Ionicons name="eye-outline" size={13} color={doctorPalette.primary} />
                          <Text style={styles.docActionBtnText}>View</Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                          style={styles.docActionBtn}
                          onPress={() => setSelectedViewerDoc(d)}
                          accessibilityRole="button"
                          accessibilityLabel={`Download document ${d.filename}`}
                          activeOpacity={0.8}
                        >
                          <Ionicons name="download-outline" size={13} color={doctorPalette.ink} />
                        </TouchableOpacity>
                      </View>
                    </View>
                  ))}
                </View>
              )}
            </View>
          </View>
        )}

        {/* TAB: TIMELINE (DAILY PATIENT INPUTS) */}
        {activeTab === "timeline" && (
          <View style={styles.tabPane}>
            <View style={styles.paneHeaderRow}>
              <View style={styles.cardTitleCol}>
                <Text style={styles.paneTitle}>Daily Patient Inputs (Meals & Glucose)</Text>
                <Text style={styles.paneSub}>
                  Chronological diary of food scans, exact intake timing, glucose measurements, and excursions
                </Text>
              </View>
            </View>

            {/* Filter Pills: All / Meals / Glucose */}
            <View style={styles.dailyFilterBar}>
              <Pressable
                style={[
                  styles.dailyFilterPill,
                  timelineFilter === "all" ? styles.dailyFilterPillActive : null,
                ]}
                onPress={() => setTimelineFilter("all")}
                accessibilityRole="button"
                accessibilityLabel="Show all inputs"
              >
                <Text
                  style={[
                    styles.dailyFilterPillText,
                    timelineFilter === "all" ? styles.dailyFilterPillTextActive : null,
                  ]}
                >
                  All Inputs ({feedItems.length})
                </Text>
              </Pressable>
              <Pressable
                style={[
                  styles.dailyFilterPill,
                  timelineFilter === "meal" ? styles.dailyFilterPillActive : null,
                ]}
                onPress={() => setTimelineFilter("meal")}
                accessibilityRole="button"
                accessibilityLabel="Show meals only"
              >
                <Ionicons
                  name="restaurant"
                  size={12}
                  color={timelineFilter === "meal" ? "#FFFFFF" : doctorPalette.muted}
                />
                <Text
                  style={[
                    styles.dailyFilterPillText,
                    timelineFilter === "meal" ? styles.dailyFilterPillTextActive : null,
                  ]}
                >
                  Meals Scanned ({mealItems.length})
                </Text>
              </Pressable>
              <Pressable
                style={[
                  styles.dailyFilterPill,
                  timelineFilter === "glucose" ? styles.dailyFilterPillActive : null,
                ]}
                onPress={() => setTimelineFilter("glucose")}
                accessibilityRole="button"
                accessibilityLabel="Show glucose only"
              >
                <Ionicons
                  name="water"
                  size={12}
                  color={timelineFilter === "glucose" ? "#FFFFFF" : doctorPalette.muted}
                />
                <Text
                  style={[
                    styles.dailyFilterPillText,
                    timelineFilter === "glucose" ? styles.dailyFilterPillTextActive : null,
                  ]}
                >
                  Glucose Readings ({glucoseItems.length})
                </Text>
              </Pressable>
            </View>

            {feed.isLoading ? (
              <LoadingState label="Loading daily inputs feed…" />
            ) : feedItems.length === 0 ? (
              <EmptyState
                title="No patient inputs"
                message="No verified meal scans or glucose readings recorded for this patient."
              />
            ) : dailyGroups.length === 0 ? (
              <EmptyState
                title="No matching entries"
                message="No records found matching the active filter."
              />
            ) : (
              <View style={styles.dailyGroupsList}>
                {dailyGroups.map((group) => {
                  const filteredItems = group.items.filter(
                    (it) => timelineFilter === "all" || it.kind === timelineFilter
                  );
                  if (filteredItems.length === 0) return null;

                  return (
                    <View key={group.dateKey} style={styles.dayGroupCard}>
                      {/* Day Header Row */}
                      <View style={styles.dayHeaderRow}>
                        <View style={styles.dayTitleRow}>
                          <Ionicons name="calendar" size={14} color={doctorPalette.primary} />
                          <Text style={styles.dayTitle}>{group.dayLabel}</Text>
                        </View>
                        <View style={styles.daySummaryChips}>
                          <View style={styles.dayChip}>
                            <Ionicons name="restaurant" size={11} color="#047857" />
                            <Text style={styles.dayChipText}>{group.mealCount} meals</Text>
                          </View>
                          <View style={styles.dayChip}>
                            <Ionicons name="water" size={11} color="#0284C7" />
                            <Text style={styles.dayChipText}>{group.glucoseCount} readings</Text>
                          </View>
                          {group.meanGlucose != null ? (
                            <View style={styles.dayChipMean}>
                              <Text style={styles.dayChipMeanText}>Avg: {group.meanGlucose} mg/dL</Text>
                            </View>
                          ) : null}
                        </View>
                      </View>

                      {/* Day Entries List */}
                      <View style={styles.dayEntriesList}>
                        {filteredItems.map((item, idx) => {
                          const isGlucose = item.kind === "glucose";
                          const isInspected = inspectedObservation?.observation_id === item.observation_id;

                          if (isGlucose) {
                            const val = (item as any).value_mg_dl;
                            const isLow = val < 70;
                            const isHigh = val > 180;
                            const tagLabel = item.tag
                              ? READING_TAG_LABELS[item.tag as ReadingTag] || item.tag
                              : "Glucose Reading";

                            return (
                              <Pressable
                                key={idx}
                                style={[
                                  styles.dailyEntryCard,
                                  styles.glucoseEntryCard,
                                  isInspected ? styles.feedCardSelected : null,
                                ]}
                                onPress={() => setInspectedObservation(isInspected ? null : item)}
                              >
                                <View style={styles.entryTopRow}>
                                  <View style={styles.glucoseIconWrap}>
                                    <Ionicons name="water" size={16} color="#0284C7" />
                                  </View>
                                  <View style={styles.entryMainCol}>
                                    <View style={styles.entryHeaderLine}>
                                      <Text style={styles.glucoseValueText}>
                                        {val} <Text style={styles.unitText}>mg/dL</Text>
                                      </Text>
                                      <View style={styles.timingPill}>
                                        <Ionicons name="time-outline" size={11} color={doctorPalette.muted} />
                                        <Text style={styles.timingText}>Measured at {item.formattedTime}</Text>
                                      </View>
                                    </View>
                                    <View style={styles.entryMetaLine}>
                                      <Badge
                                        label={tagLabel}
                                        tone="neutral"
                                      />
                                      <Badge
                                        label={isLow ? "HYPOGLYCEMIA" : isHigh ? "HIGH" : "TARGET RANGE"}
                                        tone={isLow ? "critical" : isHigh ? "warning" : "success"}
                                      />
                                      {baseline.medianMgDl != null ? (
                                        <Text style={styles.baselineDeltaText}>
                                          Δ vs baseline: {val - baseline.medianMgDl > 0 ? "+" : ""}{val - baseline.medianMgDl} mg/dL
                                        </Text>
                                      ) : null}
                                    </View>
                                  </View>
                                </View>

                                {isInspected ? (
                                  <View style={styles.inspectorDetail}>
                                    <Text style={styles.inspectorTitle}>CANONICAL PROVENANCE</Text>
                                    <Text style={styles.inspectorField}>
                                      Observation ID: <Text style={styles.boldText}>{item.observation_id}</Text>
                                    </Text>
                                    <Text style={styles.inspectorField}>
                                      Taken At: <Text style={styles.boldText}>{(item as any).taken_at}</Text>
                                    </Text>
                                    <Text style={styles.inspectorField}>
                                      Confirmation: <Text style={styles.boldText}>{(item as any).confirmation}</Text>
                                    </Text>
                                  </View>
                                ) : null}
                              </Pressable>
                            );
                          }

                          // Meal Entry
                          const meal = item as ClinicianMealObservation & { formattedTime: string; associatedExcursion?: any };
                          return (
                            <Pressable
                              key={idx}
                              style={[
                                styles.dailyEntryCard,
                                styles.mealEntryCard,
                                isInspected ? styles.feedCardSelected : null,
                              ]}
                              onPress={() => setInspectedObservation(isInspected ? null : item)}
                            >
                              <View style={styles.entryTopRow}>
                                <View style={styles.mealIconWrap}>
                                  <Ionicons name="restaurant" size={16} color="#047857" />
                                </View>
                                <View style={styles.entryMainCol}>
                                  <View style={styles.entryHeaderLine}>
                                    <Text style={styles.mealTitleText} numberOfLines={2}>
                                      {meal.description || "Meal Intake"}
                                    </Text>
                                    <View style={styles.timingPillMeal}>
                                      <Ionicons name="time-outline" size={11} color="#065F46" />
                                      <Text style={styles.timingTextMeal}>Scanned at {item.formattedTime}</Text>
                                    </View>
                                  </View>
                                  <View style={styles.entryMetaLine}>
                                    <Text style={styles.mealNutritionChip}>
                                      Portion: <Text style={styles.boldText}>{meal.portion_label || "Standard"}</Text>
                                    </Text>
                                    <Text style={styles.mealNutritionChip}>
                                      Carbs: <Text style={styles.boldText}>{meal.carbs_grams != null ? `${meal.carbs_grams}g` : "Unestimated"}</Text>
                                    </Text>
                                    {meal.glycemic_index ? (
                                      <Text style={styles.mealNutritionChip}>
                                        GI: <Text style={styles.boldText}>{meal.glycemic_index}</Text>
                                      </Text>
                                    ) : null}
                                  </View>
                                </View>
                              </View>

                              {/* Temporal Excursion Callout if meal was followed by glucose */}
                              {item.associatedExcursion ? (
                                <View style={styles.excursionCalloutBox}>
                                  <View style={styles.excursionHeaderRow}>
                                    <Ionicons name="pulse" size={14} color="#B45309" />
                                    <Text style={styles.excursionTitle}>
                                      Post-Meal Glucose Excursion: {item.associatedExcursion.glucoseMgDl} mg/dL
                                    </Text>
                                    <Badge label={item.associatedExcursion.windowLabel} tone="warning" />
                                  </View>
                                  <Text style={styles.excursionSubNote}>
                                    {item.associatedExcursion.relationshipNote}
                                  </Text>
                                </View>
                              ) : null}

                              {isInspected ? (
                                <View style={styles.inspectorDetail}>
                                  <Text style={styles.inspectorTitle}>CANONICAL PROVENANCE</Text>
                                  <Text style={styles.inspectorField}>
                                    Observation ID: <Text style={styles.boldText}>{item.observation_id}</Text>
                                  </Text>
                                  <Text style={styles.inspectorField}>
                                    Recorded At: <Text style={styles.boldText}>{meal.recorded_at}</Text>
                                  </Text>
                                  <Text style={styles.inspectorField}>
                                    Status: <Text style={styles.boldText}>{meal.confirmation}</Text>
                                  </Text>
                                </View>
                              ) : null}
                            </Pressable>
                          );
                        })}
                      </View>
                    </View>
                  );
                })}
              </View>
            )}
          </View>
        )}

        {/* TAB: GLUCOSE */}
        {activeTab === "glucose" && (
          <View style={styles.tabPane}>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>SMBG Glucose Distribution</Text>
              <View style={styles.glucoseDistributionRow}>
                <View style={[styles.distPill, { backgroundColor: "#DCFCE7" }]}>
                  <Text style={[styles.distNum, { color: "#166534" }]}>
                    {metrics.timeInRangePct ?? 0}%
                  </Text>
                  <Text style={styles.distLabel}>In Target (70–180)</Text>
                </View>
                <View style={[styles.distPill, { backgroundColor: "#FEF3C7" }]}>
                  <Text style={[styles.distNum, { color: "#92400E" }]}>
                    {metrics.timeAboveRangePct ?? 0}%
                  </Text>
                  <Text style={styles.distLabel}>High (&gt;180)</Text>
                </View>
                <View style={[styles.distPill, { backgroundColor: "#FEE2E2" }]}>
                  <Text style={[styles.distNum, { color: "#991B1B" }]}>
                    {metrics.timeBelowRangePct ?? 0}%
                  </Text>
                  <Text style={styles.distLabel}>Low (&lt;70)</Text>
                </View>
              </View>
            </View>

            {/* Glucose table */}
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Verified Glucose Readings Log</Text>
              {glucoseItems.length === 0 ? (
                <Text style={styles.emptyText}>No glucose readings available.</Text>
              ) : (
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View style={[styles.table, { minWidth: 440 }]}>
                    <View style={styles.tableHead}>
                      <Text style={[styles.th, { flex: 1.5 }]}>VALUE</Text>
                      <Text style={[styles.th, { flex: 1.5 }]}>TAG</Text>
                      <Text style={[styles.th, { flex: 2 }]}>TIMESTAMP</Text>
                      <Text style={[styles.th, { flex: 1 }]}>STATUS</Text>
                    </View>
                    {glucoseItems.map((g, idx) => (
                      <Pressable
                        key={idx}
                        style={styles.tableRow}
                        onPress={() => setInspectedObservation(g)}
                      >
                        <Text style={[styles.tdValue, { flex: 1.5 }]}>{g.value_mg_dl} mg/dL</Text>
                        <Text style={[styles.td, { flex: 1.5 }]}>{g.tag ?? "General"}</Text>
                        <Text style={[styles.td, { flex: 2 }]}>{g.taken_at}</Text>
                        <View style={{ flex: 1 }}>
                          <Badge
                            label={
                              g.value_mg_dl < 70
                                ? "LOW"
                                : g.value_mg_dl > 180
                                ? "HIGH"
                                : "NORMAL"
                            }
                            tone={
                              g.value_mg_dl < 70
                                ? "critical"
                                : g.value_mg_dl > 180
                                ? "warning"
                                : "success"
                            }
                          />
                        </View>
                      </Pressable>
                    ))}
                  </View>
                </ScrollView>
              )}
            </View>
          </View>
        )}

        {/* TAB: MEALS */}
        {activeTab === "meals" && (
          <View style={styles.tabPane}>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Temporal Food & Glucose Excursions (4-Hour Window)</Text>
              <Text style={styles.cardSubtitle}>
                Non-causal deterministic correlation of meal intakes with subsequent glucose peaks
              </Text>

              {temporalAlignments.length === 0 ? (
                <Text style={styles.emptyText}>No aligned meal-glucose pairs within 4 hours.</Text>
              ) : (
                <View style={styles.alignmentsList}>
                  {temporalAlignments.map((align, idx) => (
                    <View key={idx} style={styles.alignCard}>
                      <View style={styles.alignHeader}>
                        <Text style={styles.alignMealName}>{align.mealDescription}</Text>
                        <Badge label={align.windowLabel} tone="info" />
                      </View>
                      <Text style={styles.alignGlucose}>
                        Associated Glucose: {align.glucoseMgDl} mg/dL
                      </Text>
                      <Text style={styles.alignNote}>{align.relationshipNote}</Text>
                    </View>
                  ))}
                </View>
              )}
            </View>

            {/* Meal Items with ICMR-NIN nutrition */}
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Indian Dietary Intake Records (ICMR-NIN Taxonomy)</Text>
              {mealItems.length === 0 ? (
                <Text style={styles.emptyText}>No meal records recorded.</Text>
              ) : (
                <View style={styles.mealList}>
                  {mealItems.map((m, idx) => (
                    <View key={idx} style={styles.mealCard}>
                      <Text style={styles.mealTitle}>{m.description}</Text>
                      <Text style={styles.mealMeta}>
                        Portion: {m.portion_label || "Standard"} · Carbs:{" "}
                        {m.carbs_grams != null ? `${m.carbs_grams}g` : "n/a"} · Recorded:{" "}
                        {m.recorded_at}
                      </Text>
                    </View>
                  ))}
                </View>
              )}
            </View>
          </View>
        )}

        {/* TAB: MEDICATIONS */}
        {activeTab === "medications" && (
          <View style={styles.tabPane}>
            <View style={styles.paneHeaderRow}>
              <View style={styles.cardTitleCol}>
                <Text style={styles.paneTitle}>Medication Management</Text>
                <Text style={styles.paneSub}>Active clinician-authored pharmacotherapy regimens</Text>
              </View>
              <Button
                label="+ Author Plan"
                variant="primary"
                onPress={() => setShowCreatePlanModal(true)}
              />
            </View>

            {plans.isLoading ? (
              <LoadingState label="Loading medication plans…" />
            ) : plans.plans.length === 0 ? (
              <EmptyState
                title="No medication plans"
                message="No clinician-authored medication plans exist for this patient."
              />
            ) : (
              <View style={styles.plansList}>
                {plans.plans.map((p) => (
                  <View key={p.medication_plan_id} style={styles.card}>
                    <View style={styles.cardHeader}>
                      <Text style={styles.medName}>{p.medication}</Text>
                      <Badge
                        label={p.active ? "ACTIVE" : "SUPERSEDED"}
                        tone={p.active ? "success" : "neutral"}
                      />
                    </View>
                    <Text style={styles.medInstruction}>
                      {p.instruction || "No specific instructions provided."}
                    </Text>
                    <Text style={styles.metaSub}>
                      Prescribed by {p.prescribed_by_role} on {new Date(p.created_at).toLocaleDateString()}
                    </Text>
                  </View>
                ))}
              </View>
            )}
          </View>
        )}

        {/* TAB: TASKS */}
        {activeTab === "tasks" && (
          <View style={styles.tabPane}>
            <View style={styles.paneHeaderRow}>
              <View style={styles.cardTitleCol}>
                <Text style={styles.paneTitle}>Patient Care Tasks</Text>
                <Text style={styles.paneSub}>Interventions and follow-up duties</Text>
              </View>
              <Button
                label="+ Add Task"
                variant="primary"
                onPress={() => setShowCreateTaskModal(true)}
              />
            </View>

            {tasks.isLoading ? (
              <LoadingState label="Loading tasks…" />
            ) : tasks.tasks.length === 0 ? (
              <EmptyState title="No care tasks" message="No tasks assigned for this patient." />
            ) : (
              <View style={styles.taskList}>
                {tasks.tasks.map((t) => (
                  <View key={t.care_task_id} style={styles.card}>
                    <View style={styles.cardHeader}>
                      <Badge
                        label={t.status.toUpperCase()}
                        tone={t.status === "completed" ? "success" : "warning"}
                      />
                      <Text style={styles.taskDate}>
                        {new Date(t.created_at).toLocaleDateString()}
                      </Text>
                    </View>
                    <Text style={styles.taskText}>{t.description}</Text>
                    <View style={styles.taskBtnRow}>
                      {t.status === "open" ? (
                        <Button
                          label="Start Task"
                          variant="outline"
                          onPress={() => tasks.startTask(t.care_task_id)}
                        />
                      ) : null}
                      {t.status === "in_progress" ? (
                        <Button
                          label="Mark Complete"
                          variant="primary"
                          onPress={() => tasks.completeTask(t.care_task_id)}
                        />
                      ) : null}
                    </View>
                  </View>
                ))}
              </View>
            )}
          </View>
        )}

        {/* TAB: DOCUMENTS & REPORTS */}
        {activeTab === "documents" && (
          <View style={styles.tabPane}>
            <View style={styles.paneHeaderRow}>
              <View style={styles.cardTitleCol}>
                <Text style={styles.paneTitle}>Documents & Server Reports</Text>
                <Text style={styles.paneSub}>Clinical records and PDF summary documents</Text>
              </View>
              <View style={styles.buttonRow}>
                <Button
                  label="Upload"
                  variant="outline"
                  onPress={() => setShowUploadDocModal(true)}
                />
                <Button
                  label="Compile Report"
                  variant="primary"
                  disabled={reportGen.isGenerating}
                  onPress={handleGenerateReport}
                />
              </View>
            </View>

            {docs.isLoading ? (
              <LoadingState label="Loading patient documents…" />
            ) : docs.documents.length === 0 ? (
              <EmptyState title="No documents" message="No documents uploaded for this patient." />
            ) : (
              <View style={styles.docList}>
                {docs.documents.map((d) => (
                  <View key={d.id} style={styles.docRow}>
                    <Ionicons name="document-text" size={20} color={doctorPalette.primary} />
                    <View style={styles.docMetaCol}>
                      <Text style={styles.docTitle} numberOfLines={1}>{d.filename}</Text>
                      <Text style={styles.docSub}>
                        {d.kind} · {Math.round(d.file_size_bytes / 1024)} KB ·{" "}
                        {new Date(d.created_at).toLocaleDateString()}
                      </Text>
                    </View>
                    <View style={styles.docBtnGroup}>
                      <TouchableOpacity
                        style={styles.docActionBtn}
                        onPress={() => setSelectedViewerDoc(d)}
                        accessibilityRole="button"
                        accessibilityLabel={`View document ${d.filename}`}
                        activeOpacity={0.8}
                      >
                        <Ionicons name="eye-outline" size={14} color={doctorPalette.primary} />
                        <Text style={styles.docActionBtnText}>View</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={styles.docActionBtn}
                        onPress={() => setSelectedViewerDoc(d)}
                        accessibilityRole="button"
                        accessibilityLabel={`Download document ${d.filename}`}
                        activeOpacity={0.8}
                      >
                        <Ionicons name="download-outline" size={14} color={doctorPalette.ink} />
                      </TouchableOpacity>
                    </View>
                  </View>
                ))}
              </View>
            )}
          </View>
        )}

        {/* TAB: AI & EVIDENCE */}
        {activeTab === "ai-review" && (
          <View style={styles.tabPane}>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Assistive AI Evidence Drawer</Text>
              <Text style={styles.cardSubtitle}>
                Every clinical insight statement links directly to canonical observation timestamps
              </Text>

              {insights.isLoading ? (
                <LoadingState label="Loading AI clinical insights…" />
              ) : insights.insights ? (
                <View style={styles.evidenceBody}>
                  <View style={styles.evidenceStatement}>
                    <Text style={styles.evidenceTitle}>Glycemic Analysis & Pattern Identification</Text>
                    <Text style={styles.evidenceText}>
                      {insights.insights.metrics.clinical_summary_note}
                    </Text>
                    <View style={styles.evidenceFootnote}>
                      <Text style={styles.footnoteText}>
                        Linked to {insights.insights.metrics.total_readings} canonical observations.
                        Mean: {insights.insights.metrics.mean_glucose_mg_dl} mg/dL, CV:{" "}
                        {insights.insights.metrics.coefficient_of_variation_pct}%.
                      </Text>
                    </View>
                  </View>
                </View>
              ) : (
                <Text style={styles.emptyText}>No AI insights generated yet.</Text>
              )}
            </View>
          </View>
        )}

        {/* TAB: COMMUNICATION */}
        {activeTab === "communication" && (
          <View style={styles.tabPane}>
            <View style={styles.paneHeader}>
              <Text style={styles.paneTitle}>Patient Notification History</Text>
              <Text style={styles.paneSub}>Logged WhatsApp and SMS metabolic alerts</Text>
            </View>

            {notifications.isLoading ? (
              <LoadingState label="Loading notifications…" />
            ) : notifications.notifications.length === 0 ? (
              <EmptyState
                title="No logged alerts"
                message="No notifications currently sent to this patient."
              />
            ) : (
              <View style={styles.notifList}>
                {notifications.notifications.map((n) => (
                  <View key={n.id} style={styles.card}>
                    <View style={styles.cardHeader}>
                      <Badge label={n.status.toUpperCase()} tone="info" />
                      <Text style={styles.taskDate}>
                        {new Date(n.created_at).toLocaleString()}
                      </Text>
                    </View>
                    <Text style={styles.notifText}>
                      {n.template_name || n.notification_type || "Direct Alert"}
                    </Text>
                    <Text style={styles.metaSub}>Recipient: {n.recipient_phone}</Text>
                  </View>
                ))}
              </View>
            )}
          </View>
        )}

        {/* TAB: AUDIT */}
        {activeTab === "audit" && (
          <View style={styles.tabPane}>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Patient Record Audit Trail</Text>
              <Text style={styles.cardSubtitle}>
                Verifiable event log for Patient UHID: {shown.uh_id}
              </Text>
              <View style={styles.auditEventRow}>
                <View style={styles.auditDot} />
                <View style={styles.auditInfo}>
                  <Text style={styles.auditEventTitle}>Patient Record Initialized</Text>
                  <Text style={styles.auditMeta}>
                    Canonical record enrolled on {new Date(shown.created_at).toLocaleString()}
                  </Text>
                </View>
              </View>
              <View style={styles.auditEventRow}>
                <View style={styles.auditDot} />
                <View style={styles.auditInfo}>
                  <Text style={styles.auditEventTitle}>Telemetry Observations Streamed</Text>
                  <Text style={styles.auditMeta}>
                    {feedItems.length} verified observations indexed with immutable observation IDs
                  </Text>
                </View>
              </View>
              <View style={styles.auditEventRow}>
                <View style={styles.auditDot} />
                <View style={styles.auditInfo}>
                  <Text style={styles.auditEventTitle}>Medication Regimens Authorized</Text>
                  <Text style={styles.auditMeta}>
                    {plans.plans.length} clinician-authored medication plans logged
                  </Text>
                </View>
              </View>
            </View>
          </View>
        )}
      </ScrollView>

      <ReportViewerModal
        visible={!!selectedViewerDoc}
        document={selectedViewerDoc}
        patientName={shown.name}
        uhid={shown.uh_id}
        onClose={() => setSelectedViewerDoc(null)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  topAppBar: {
    backgroundColor: doctorPalette.surface,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.border,
    paddingTop: 2,
    ...doctorSoftShadow,
  },
  topAppRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    gap: 6,
  },
  backButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: doctorPalette.surfaceSoft,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  topPatientHeaderCol: {
    flex: 1,
    minWidth: 0,
    gap: 1,
  },
  topPatientTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flexShrink: 1,
  },
  topPatientName: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.ink,
    flexShrink: 1,
  },
  topPatientMeta: {
    fontSize: 10.5,
    color: doctorPalette.muted,
  },
  topActionsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    flexShrink: 0,
  },
  topActionBtnOutline: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: doctorRadii.sm,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    backgroundColor: doctorPalette.surface,
  },
  topActionBtnText: {
    fontSize: 10.5,
    fontWeight: "700",
    color: doctorPalette.ink,
  },
  topActionBtnPrimary: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: doctorRadii.sm,
    backgroundColor: doctorPalette.ink,
  },
  topActionBtnPrimaryText: {
    fontSize: 10.5,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  tabsRow: {
    flexDirection: "row",
    paddingVertical: 3,
  },
  tabsRowContainer: {
    paddingHorizontal: spacing.sm,
    paddingBottom: 4,
    gap: 4,
  },
  tabButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    marginRight: 2,
  },
  tabButtonActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.surfaceLime,
  },
  tabText: {
    fontSize: 11,
    color: doctorPalette.muted,
    fontWeight: "700",
  },
  tabTextActive: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.55)",
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.lg,
  },
  modalCard: {
    width: "100%",
    maxWidth: 480,
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.xl,
    padding: spacing.lg,
    gap: spacing.md,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    ...doctorSoftShadow,
  },
  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  modalTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  modalInput: {
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    borderRadius: doctorRadii.md,
    padding: spacing.sm,
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.ink,
    minHeight: 44,
  },
  kindSelectorRow: {
    flexDirection: "row",
    gap: spacing.xs,
    flexWrap: "wrap",
  },
  kindPill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
  },
  kindPillActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.surfaceLime,
  },
  kindText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.ink,
  },
  kindTextActive: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  modalActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: spacing.sm,
  },
  heroCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    gap: spacing.xs,
    ...doctorSoftShadow,
  },
  heroMainRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  avatar: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: doctorPalette.surfaceLime,
    alignItems: "center",
    justifyContent: "center",
    ...doctorSoftShadow,
  },
  avatarText: {
    color: doctorPalette.ink,
    fontSize: 16,
    fontWeight: "800",
  },
  heroInfoCol: {
    flex: 1,
    minWidth: 0,
    gap: 1,
  },
  heroTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flexShrink: 1,
  },
  heroPatientName: {
    fontSize: 16,
    lineHeight: 22,
    fontWeight: "800",
    color: doctorPalette.ink,
    flexShrink: 1,
  },
  heroMetaLine: {
    fontSize: 10.5,
    color: doctorPalette.muted,
  },
  metaBold: {
    fontWeight: "700",
    color: doctorPalette.ink,
  },
  heroSecondaryActionsRow: {
    flexDirection: "row",
    gap: 6,
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: doctorPalette.surfaceSoft,
    flexWrap: "wrap",
  },
  heroActionPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
  },
  heroActionPillText: {
    fontSize: 10.5,
    fontWeight: "700",
    color: doctorPalette.ink,
  },
  periodBarCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    flexWrap: "wrap",
    gap: spacing.xs,
    ...doctorSoftShadow,
  },
  periodBarLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flexWrap: "wrap",
    flex: 1,
    minWidth: 0,
  },
  periodLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.textSecondary,
  },
  periodButtonsRow: {
    flexDirection: "row",
    gap: 4,
  },
  periodBtn: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: doctorRadii.sm,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
  },
  periodBtnActive: {
    backgroundColor: doctorPalette.primary,
    borderColor: doctorPalette.primary,
  },
  periodBtnText: {
    fontSize: 10.5,
    fontWeight: "700",
    color: colors.textSecondary,
  },
  periodBtnTextActive: {
    color: "#ffffff",
  },
  engineBadgeContainer: {
    marginLeft: "auto",
    backgroundColor: "#EFF6FF",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: doctorRadii.sm,
  },
  engineBadgeText: {
    fontSize: 9.5,
    color: "#1D4ED8",
    fontWeight: "600",
  },
  metricsBarContainer: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    padding: 6,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    ...doctorSoftShadow,
  },
  metricsBar: {
    flexDirection: "row",
  },
  metricsBarScroll: {
    flexDirection: "row",
    gap: 6,
    paddingVertical: 2,
  },
  metricPill: {
    minWidth: 100,
    backgroundColor: doctorPalette.surfaceSoft,
    borderRadius: doctorRadii.sm,
    paddingHorizontal: 8,
    paddingVertical: 5,
    gap: 2,
  },
  metricPillLabel: {
    fontSize: 9.5,
    fontWeight: "700",
    color: doctorPalette.muted,
    textTransform: "uppercase",
  },
  metricPillValue: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  referenceBanner: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 6,
    backgroundColor: "rgba(255, 255, 255, 0.75)",
    borderWidth: 1,
    borderColor: doctorPalette.border,
    borderRadius: doctorRadii.md,
    paddingHorizontal: 8,
    paddingVertical: 6,
  },
  referenceNoticeText: {
    flex: 1,
    fontSize: 9.5,
    color: doctorPalette.muted,
    lineHeight: 13,
  },
  reportSuccessBanner: {
    backgroundColor: "#DCFCE7",
    padding: 10,
    borderRadius: doctorRadii.md,
    borderWidth: 1,
    borderColor: "#86EFAC",
    gap: 6,
  },
  reportSuccessHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  reportSuccessTextCol: {
    flex: 1,
  },
  reportSuccessTitle: {
    fontSize: 12,
    fontWeight: "800",
    color: "#15803D",
  },
  reportSuccessText: {
    fontSize: 11,
    color: "#166534",
    fontWeight: "500",
  },
  reportSuccessBtnRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flexWrap: "wrap",
    marginTop: 2,
  },
  reportActionBtnPrimary: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "#15803D",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: doctorRadii.sm,
  },
  reportActionBtnPrimaryText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  reportActionBtnSecondary: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#86EFAC",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: doctorRadii.sm,
  },
  reportActionBtnSecondaryText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#15803D",
  },
  tabContentScroll: {
    flex: 1,
  },
  tabContentContainer: {
    padding: spacing.sm,
    paddingBottom: 130,
    gap: spacing.sm,
  },
  tabPane: {
    gap: spacing.sm,
  },
  card: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.sm,
    gap: spacing.xs,
    ...doctorSoftShadow,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 6,
  },
  cardTitleCol: {
    flex: 1,
    minWidth: 140,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.ink,
    flexShrink: 1,
  },
  cardSubtitle: {
    fontSize: 11,
    color: doctorPalette.muted,
  },
  grid3: {
    flexDirection: "row",
    gap: 6,
    marginVertical: 4,
    flexWrap: "wrap",
  },
  gridCell: {
    flex: 1,
    minWidth: 78,
    backgroundColor: doctorPalette.surfaceSoft,
    borderRadius: doctorRadii.md,
    padding: 8,
    gap: 2,
  },
  gridCellLabel: {
    fontSize: 9.5,
    fontWeight: "700",
    color: doctorPalette.muted,
    textTransform: "uppercase",
  },
  gridCellValue: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  gridCellSub: {
    fontSize: 9.5,
    color: doctorPalette.muted,
  },
  interpretationText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textPrimary,
    lineHeight: 20,
  },
  baselineDivider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.xs,
  },
  subHeading: {
    fontSize: typography.fontSize.caption,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  bulletText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  aiNoteText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textPrimary,
    lineHeight: 20,
  },
  aiFlagsRow: {
    flexDirection: "row",
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  paneHeader: {
    gap: 2,
    marginBottom: spacing.xs,
  },
  paneHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  paneTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  paneSub: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  feedList: {
    gap: spacing.xs,
  },
  feedCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.sm,
    gap: spacing.xs,
  },
  feedCardSelected: {
    borderColor: doctorPalette.primary,
    backgroundColor: doctorPalette.surfaceBlue,
  },
  feedCardTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  feedCardIcon: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  feedCardMain: {
    flex: 1,
  },
  feedTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  feedSub: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  inspectorDetail: {
    marginTop: spacing.xs,
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: doctorPalette.border,
    gap: 2,
  },
  inspectorTitle: {
    fontSize: 10,
    fontWeight: "800",
    color: doctorPalette.primary,
    letterSpacing: 0,
  },
  inspectorField: {
    fontSize: 11,
    color: doctorPalette.muted,
  },
  boldText: {
    fontWeight: "700",
    color: doctorPalette.ink,
  },
  glucoseDistributionRow: {
    flexDirection: "row",
    gap: 6,
    marginTop: 4,
  },
  distPill: {
    flex: 1,
    padding: 8,
    borderRadius: doctorRadii.md,
    alignItems: "center",
    gap: 2,
  },
  distNum: {
    fontSize: 18,
    fontWeight: "800",
  },
  distLabel: {
    fontSize: 10,
    fontWeight: "600",
    color: doctorPalette.ink,
    textAlign: "center",
  },
  table: {
    marginTop: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
  },
  tableHead: {
    flexDirection: "row",
    backgroundColor: colors.background,
    padding: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  th: {
    fontSize: 10,
    fontWeight: "800",
    color: colors.textSecondary,
  },
  tableRow: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  td: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  tdValue: {
    fontSize: typography.fontSize.caption,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  emptyText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    fontStyle: "italic",
  },
  alignmentsList: {
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  alignCard: {
    backgroundColor: colors.background,
    borderRadius: radii.sm,
    padding: spacing.sm,
    gap: 2,
  },
  alignHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  alignMealName: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  alignGlucose: {
    fontSize: typography.fontSize.caption,
    fontWeight: "600",
    color: colors.primary,
  },
  alignNote: {
    fontSize: 11,
    color: colors.textSecondary,
  },
  mealList: {
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  mealCard: {
    backgroundColor: colors.background,
    borderRadius: radii.sm,
    padding: spacing.sm,
    gap: 2,
  },
  mealTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  mealMeta: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  plansList: {
    gap: spacing.md,
  },
  medName: {
    fontSize: typography.fontSize.body,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  medInstruction: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textPrimary,
    lineHeight: 20,
  },
  metaSub: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  taskList: {
    gap: spacing.md,
  },
  taskDate: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  taskText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textPrimary,
  },
  taskBtnRow: {
    flexDirection: "row",
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  docList: {
    gap: spacing.xs,
  },
  docRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    padding: spacing.sm,
    gap: spacing.sm,
  },
  docIcon: {
    fontSize: 20,
  },
  docMetaCol: {
    flex: 1,
  },
  docTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  docSub: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  docBtnGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  docActionBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 6,
    borderRadius: doctorRadii.sm,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
  },
  docActionBtnText: {
    fontSize: 11,
    fontWeight: "700",
    color: doctorPalette.primary,
  },
  evidenceBody: {
    marginTop: spacing.xs,
  },
  evidenceStatement: {
    backgroundColor: colors.background,
    borderRadius: radii.sm,
    padding: spacing.md,
    gap: spacing.xs,
  },
  evidenceTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  evidenceText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textPrimary,
    lineHeight: 20,
  },
  evidenceFootnote: {
    marginTop: spacing.xs,
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  footnoteText: {
    fontSize: 10,
    color: colors.textSecondary,
  },
  notifList: {
    gap: spacing.xs,
  },
  notifText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textPrimary,
  },
  auditEventRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  auditDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.primary,
    marginTop: 5,
  },
  auditInfo: {
    flex: 1,
  },
  auditEventTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  auditMeta: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  buttonRow: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  alertsContainer: {
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  alertCard: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    padding: spacing.sm,
    borderRadius: doctorRadii.sm,
    borderWidth: 1,
  },
  alertCardHigh: {
    backgroundColor: "#FEF2F2",
    borderColor: "#FCA5A5",
  },
  alertCardMod: {
    backgroundColor: "#FFFBEB",
    borderColor: "#FDE68A",
  },
  alertContent: {
    flex: 1,
  },
  alertCodeText: {
    fontSize: typography.fontSize.caption,
    fontWeight: "800",
    color: colors.textPrimary,
  },
  alertMsgText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  tirBreakdownRow: {
    flexDirection: "row",
    gap: 6,
    marginTop: 6,
  },
  tirPill: {
    flex: 1,
    padding: 6,
    borderRadius: doctorRadii.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  tirPillNum: {
    fontSize: 15,
    fontWeight: "800",
  },
  tirPillLabel: {
    fontSize: 9.5,
    fontWeight: "600",
    marginTop: 2,
    textAlign: "center",
  },
  comparisonTable: {
    marginTop: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: doctorRadii.sm,
    overflow: "hidden",
  },
  comparisonHeaderRow: {
    flexDirection: "row",
    backgroundColor: doctorPalette.surfaceSoft,
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  comparisonRow: {
    flexDirection: "row",
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    alignItems: "center",
  },
  compCol: {
    flex: 1,
    fontSize: typography.fontSize.caption,
    color: colors.textPrimary,
  },
  compColHeader: {
    fontWeight: "700",
    color: colors.textSecondary,
    fontSize: 11,
  },
  slotsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 4,
  },
  slotCard: {
    flexBasis: "48%",
    flexGrow: 1,
    backgroundColor: colors.background,
    borderRadius: doctorRadii.sm,
    padding: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  slotTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  slotMean: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.primary,
    marginVertical: 2,
  },
  slotCount: {
    fontSize: 9.5,
    color: colors.textSecondary,
  },
  slotNote: {
    fontSize: 10,
    color: colors.textSecondary,
    marginTop: 3,
  },
  patternSubText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  mealAssocList: {
    gap: 6,
    marginTop: 4,
  },
  mealAssocItem: {
    backgroundColor: colors.background,
    borderRadius: doctorRadii.sm,
    padding: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  mealAssocHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  mealAssocTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  mealAssocTime: {
    fontSize: 10.5,
    color: colors.textSecondary,
  },
  mealAssocMetrics: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 4,
  },
  mealAssocMetric: {
    fontSize: 11,
    color: colors.textSecondary,
  },
  screeningsList: {
    gap: 6,
    marginTop: 4,
  },
  screeningRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: colors.background,
    borderRadius: doctorRadii.sm,
    padding: 8,
    borderWidth: 1,
    borderColor: colors.border,
    gap: 6,
  },
  screeningTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  screeningMeta: {
    fontSize: 10.5,
    color: colors.textSecondary,
    marginTop: 2,
  },
  agpSufficiencyBox: {
    backgroundColor: doctorPalette.surfaceSoft,
    padding: 8,
    borderRadius: doctorRadii.sm,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    marginTop: 4,
  },
  agpSufficiencyText: {
    fontSize: 10,
    color: doctorPalette.muted,
    lineHeight: 14,
  },
  docIconBox: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: doctorPalette.surfaceSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  docIconBoxPrescription: {
    backgroundColor: "#CCFBF1",
  },
  docTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flexWrap: "wrap",
  },
  dailyFilterBar: {
    flexDirection: "row",
    gap: 6,
    flexWrap: "wrap",
    marginBottom: 4,
  },
  dailyFilterPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surface,
    borderWidth: 1,
    borderColor: doctorPalette.border,
  },
  dailyFilterPillActive: {
    backgroundColor: doctorPalette.ink,
    borderColor: doctorPalette.ink,
  },
  dailyFilterPillText: {
    fontSize: 11,
    fontWeight: "700",
    color: doctorPalette.muted,
  },
  dailyFilterPillTextActive: {
    color: "#FFFFFF",
  },
  dailyGroupsList: {
    gap: spacing.sm,
  },
  dayGroupCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.sm,
    gap: spacing.xs,
    ...doctorSoftShadow,
  },
  dayHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 6,
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.surfaceSoft,
  },
  dayTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  dayTitle: {
    fontSize: 13,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  daySummaryChips: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    flexWrap: "wrap",
  },
  dayChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: doctorRadii.sm,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  dayChipText: {
    fontSize: 10,
    fontWeight: "600",
    color: doctorPalette.ink,
  },
  dayChipMean: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: doctorRadii.sm,
    backgroundColor: "#EFF6FF",
  },
  dayChipMeanText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#1D4ED8",
  },
  dayEntriesList: {
    gap: 6,
    marginTop: 4,
  },
  dailyEntryCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.md,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: 8,
    gap: 4,
  },
  glucoseEntryCard: {
    borderLeftWidth: 3.5,
    borderLeftColor: "#0284C7",
  },
  mealEntryCard: {
    borderLeftWidth: 3.5,
    borderLeftColor: "#047857",
  },
  entryTopRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
  },
  glucoseIconWrap: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: "#E0F2FE",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    marginTop: 1,
  },
  mealIconWrap: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: "#D1FAE5",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    marginTop: 1,
  },
  entryMainCol: {
    flex: 1,
    gap: 2,
  },
  entryHeaderLine: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 4,
  },
  glucoseValueText: {
    fontSize: 15,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  unitText: {
    fontSize: 11,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  timingPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: doctorRadii.pill,
  },
  timingText: {
    fontSize: 10,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  timingPillMeal: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    backgroundColor: "#ECFDF5",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: doctorRadii.pill,
  },
  timingTextMeal: {
    fontSize: 10,
    fontWeight: "700",
    color: "#065F46",
  },
  entryMetaLine: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flexWrap: "wrap",
    marginTop: 2,
  },
  baselineDeltaText: {
    fontSize: 10,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  mealTitleText: {
    fontSize: 13,
    fontWeight: "700",
    color: doctorPalette.ink,
    flex: 1,
    marginRight: 4,
  },
  mealNutritionChip: {
    fontSize: 10.5,
    color: doctorPalette.muted,
  },
  excursionCalloutBox: {
    backgroundColor: "#FFFBEB",
    borderWidth: 1,
    borderColor: "#FDE68A",
    borderRadius: doctorRadii.sm,
    padding: 6,
    gap: 2,
    marginTop: 4,
  },
  excursionHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    flexWrap: "wrap",
  },
  excursionTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: "#92400E",
    flex: 1,
  },
  excursionSubNote: {
    fontSize: 10,
    color: "#78350F",
    lineHeight: 13,
  },
  disclaimerText: {
    fontSize: 9.5,
    color: colors.textSecondary,
    marginTop: spacing.xs,
    fontStyle: "italic",
  },
});
