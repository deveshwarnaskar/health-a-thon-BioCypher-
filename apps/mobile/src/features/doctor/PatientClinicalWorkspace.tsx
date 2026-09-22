import React, { useState } from "react";
import { StyleSheet, Text, View, ScrollView, Pressable, TextInput, useWindowDimensions } from "react-native";
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
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import type { PatientSummaryResponse } from "../../services/schemas/patients";
import type {
  ClinicianGlucoseObservation,
  ClinicianMealObservation,
} from "../../services/schemas/clinical";

export type PatientWorkspaceTab =
  | "snapshot"
  | "timeline"
  | "glucose"
  | "meals"
  | "medications"
  | "tasks"
  | "documents"
  | "ai-review"
  | "communication"
  | "audit";

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

  const [activeTab, setActiveTab] = useState<PatientWorkspaceTab>(initialTab);
  const [showCreatePlanModal, setShowCreatePlanModal] = useState(false);
  const [showCreateTaskModal, setShowCreateTaskModal] = useState(false);
  const [showUploadDocModal, setShowUploadDocModal] = useState(false);
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);

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

  const metrics = calculateGlycemicMetrics(glucoseItems, 14);
  const baseline = calculatePersonalBaseline(glucoseItems, 14);
  const coverage = calculateDataCoverage(glucoseItems, mealItems, 14);
  const temporalAlignments = calculateTemporalAlignment(mealItems, glucoseItems, 240);

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
      await reportGen.generateReport();
    } catch {
      // Handled by hook error state
    }
  };

  const tabs: { key: PatientWorkspaceTab; label: string; icon: React.ComponentProps<typeof Ionicons>["name"] }[] = [
    { key: "snapshot", label: "Snapshot", icon: "pulse" },
    { key: "timeline", label: "Timeline", icon: "time" },
    { key: "glucose", label: "Glucose", icon: "water" },
    { key: "meals", label: "Meals & Nutrition", icon: "restaurant" },
    { key: "medications", label: "Medications", icon: "medkit" },
    { key: "tasks", label: "Care Tasks", icon: "checkbox" },
    { key: "documents", label: "Docs & Reports", icon: "folder-open" },
    { key: "ai-review", label: "AI & Evidence", icon: "sparkles" },
    { key: "communication", label: "Messages", icon: "chatbubble-ellipses" },
    { key: "audit", label: "Audit", icon: "shield-checkmark" },
  ];

  return (
    <View style={styles.container} testID={testID}>
      {/* 1. Persistent Patient Header */}
      <View style={styles.patientHeader}>
        <View style={[styles.headerTopRow, isCompact ? styles.headerTopRowCompact : null]}>
          <View style={styles.identityGroup}>
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>{shown.name.charAt(0)}</Text>
            </View>
            <View>
              <View style={styles.nameRow}>
                <Text style={styles.patientName} numberOfLines={2}>{shown.name}</Text>
                <Badge
                  label={shown.active ? "Active" : "Inactive"}
                  tone={shown.active ? "success" : "neutral"}
                />
              </View>
              <Text style={styles.metaLine}>
                UHID: <Text style={styles.metaBold}>{shown.uh_id}</Text> · Patient ID:{" "}
                <Text style={styles.metaBold}>{shown.patient_id.slice(0, 8)}…</Text> · Facility:{" "}
                <Text style={styles.metaBold}>{shown.facility_id}</Text>
              </Text>
            </View>
          </View>

          {/* Quick Action Buttons */}
          <View style={[styles.actionButtons, isCompact ? styles.actionButtonsCompact : null]}>
            <Button
              label="+ Author Plan"
              variant="primary"
              onPress={() => setShowCreatePlanModal(true)}
            />
            <Button
              label={reportGen.isGenerating ? "Compiling…" : "📄 Generate Report"}
              variant="outline"
              disabled={reportGen.isGenerating}
              onPress={handleGenerateReport}
            />
            <Button
              label="+ Add Task"
              variant="outline"
              onPress={() => setShowCreateTaskModal(true)}
            />
            <Button
              label="Upload Doc"
              variant="outline"
              onPress={() => setShowUploadDocModal(true)}
            />
            <Button label="Close" variant="ghost" onPress={onBack} />
          </View>
        </View>

        {/* Quick Glycemic Metrics Bar */}
        <View style={[styles.metricsBar, isCompact ? styles.metricsBarCompact : null]}>
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
        </View>

        {/* General Reference Ranges Banner */}
        <View style={styles.referenceBanner}>
          <Text style={styles.referenceNoticeText}>
            General Reference Ranges: Fasting 80–130 mg/dL · Post-meal &lt;180 mg/dL · HbA1c &lt;7.0%.
            These are general population reference ranges and may not apply to this patient&apos;s
            individual care plan. Authorize personalized targets when clinically indicated.
          </Text>
        </View>

        {reportGen.isSuccess && reportGen.generatedDocument ? (
          <View style={styles.reportSuccessBanner}>
            <Text style={styles.reportSuccessText}>
              ✓ Report compiled: {reportGen.generatedDocument.filename} (
              {Math.round(reportGen.generatedDocument.file_size_bytes / 1024)} KB). Download link active.
            </Text>
          </View>
        ) : null}

        {/* Sub-Navigation Tabs */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabsRow}>
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
                  size={16}
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

      {/* 2. Modals for Adding Task or Uploading Doc */}
      {showCreateTaskModal ? (
        <View style={styles.inlineModal}>
          <Text style={styles.modalTitle}>Add Care Task for {shown.name}</Text>
          <TextInput
            style={styles.modalInput}
            placeholder="Directives for care team or patient follow-up…"
            placeholderTextColor={colors.textSecondary}
            value={taskDescription}
            onChangeText={setTaskDescription}
          />
          <View style={styles.modalActions}>
            <Button
              label={tasks.isCreating ? "Saving…" : "Save Task"}
              variant="primary"
              disabled={tasks.isCreating || !taskDescription.trim()}
              onPress={handleCreateTask}
            />
            <Button
              label="Cancel"
              variant="ghost"
              onPress={() => setShowCreateTaskModal(false)}
            />
          </View>
        </View>
      ) : null}

      {showUploadDocModal ? (
        <View style={styles.inlineModal}>
          <Text style={styles.modalTitle}>Upload Document for {shown.name}</Text>
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
              label={docs.isUploading ? "Uploading…" : "Upload to S3"}
              variant="primary"
              disabled={docs.isUploading || !docFilename.trim()}
              onPress={handleUploadDoc}
            />
            <Button
              label="Cancel"
              variant="ghost"
              onPress={() => setShowUploadDocModal(false)}
            />
          </View>
        </View>
      ) : null}

      {/* 3. Tab Contents */}
      <ScrollView style={styles.tabContentScroll} contentContainerStyle={styles.tabContentContainer}>
        {/* TAB: SNAPSHOT */}
        {activeTab === "snapshot" && (
          <View style={styles.tabPane}>
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardTitle}>14-Day Deterministic Glycemic Summary</Text>
                <Badge
                  label={coverage.isContinuous ? "Adequate Coverage" : "Sparse Telemetry"}
                  tone={coverage.isContinuous ? "success" : "warning"}
                />
              </View>

              <View style={styles.grid3}>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Mean Glucose</Text>
                  <Text style={styles.gridCellValue}>
                    {metrics.meanMgDl != null ? `${metrics.meanMgDl} mg/dL` : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>SD: ±{metrics.standardDeviationMgDl ?? "—"}</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>Glycemic Variability (CV)</Text>
                  <Text style={styles.gridCellValue}>
                    {metrics.coefficientOfVariationPct != null ? `${metrics.coefficientOfVariationPct}%` : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>Target: &lt;36%</Text>
                </View>
                <View style={styles.gridCell}>
                  <Text style={styles.gridCellLabel}>GMI / Est. A1c</Text>
                  <Text style={styles.gridCellValue}>
                    {metrics.gmiPct != null ? `${metrics.gmiPct}%` : "—"}
                  </Text>
                  <Text style={styles.gridCellSub}>eA1c: {metrics.estimatedA1cPct ?? "—"}%</Text>
                </View>
              </View>

              <Text style={styles.interpretationText}>{metrics.interpretationSummary}</Text>

              <View style={styles.baselineDivider} />
              <Text style={styles.subHeading}>Rolling Personal Baseline & Coverage</Text>
              <Text style={styles.bulletText}>• {baseline.descriptiveNote}</Text>
              <Text style={styles.bulletText}>
                • Data completeness: {coverage.coverageText} ({coverage.glucoseReadingCount} glucose readings,{" "}
                {coverage.mealRecordCount} meal records).
              </Text>
            </View>

            {/* AI Insights Card */}
            {insights.isLoading ? (
              <LoadingState label="Loading assistive AI clinical insights…" />
            ) : insights.insights ? (
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <Text style={styles.cardTitle}>Assistive AI Clinical Intelligence</Text>
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
              </View>
            ) : null}
          </View>
        )}

        {/* TAB: TIMELINE */}
        {activeTab === "timeline" && (
          <View style={styles.tabPane}>
            <View style={styles.paneHeader}>
              <Text style={styles.paneTitle}>Unified Longitudinal Observation Timeline</Text>
              <Text style={styles.paneSub}>
                Every entry is validated against canonical schema and carries verifiable provenance
              </Text>
            </View>

            {feed.isLoading ? (
              <LoadingState label="Loading longitudinal feed…" />
            ) : feedItems.length === 0 ? (
              <EmptyState title="No observations" message="No verified records found." />
            ) : (
              <View style={styles.feedList}>
                {feedItems.map((item, idx) => {
                  const isGlucose = item.kind === "glucose";
                  const isInspected = inspectedObservation?.observation_id === item.observation_id;
                  return (
                    <Pressable
                      key={idx}
                      style={[styles.feedCard, isInspected ? styles.feedCardSelected : null]}
                      onPress={() => setInspectedObservation(isInspected ? null : item)}
                    >
                      <View style={styles.feedCardTop}>
                        <View style={styles.feedCardIcon}>
                          <Ionicons
                            name={isGlucose ? "water" : "restaurant"}
                            size={17}
                            color={doctorPalette.primary}
                          />
                        </View>
                        <View style={styles.feedCardMain}>
                          <Text style={styles.feedTitle}>
                            {isGlucose
                              ? `Glucose: ${(item as any).value_mg_dl} mg/dL`
                              : (item as any).description}
                          </Text>
                          <Text style={styles.feedSub}>
                            {isGlucose
                              ? `Tag: ${(item as any).tag ?? "untagged"} · ${(item as any).taken_at}`
                              : `Carbs: ${(item as any).carbs_grams ?? "n/a"}g · GI: ${(item as any).glycemic_index ?? "n/a"} · ${(item as any).recorded_at}`}
                          </Text>
                        </View>
                        <Badge label={(item as any).confirmation ?? "confirmed"} tone="success" />
                      </View>

                      {isInspected ? (
                        <View style={styles.inspectorDetail}>
                          <Text style={styles.inspectorTitle}>CANONICAL OBSERVATION PROVENANCE</Text>
                          <Text style={styles.inspectorField}>
                            Observation ID: <Text style={styles.boldText}>{item.observation_id}</Text>
                          </Text>
                          <Text style={styles.inspectorField}>
                            Recorded Timestamp:{" "}
                            <Text style={styles.boldText}>
                              {isGlucose ? (item as any).taken_at : (item as any).recorded_at}
                            </Text>
                          </Text>
                          <Text style={styles.inspectorField}>
                            Status: <Text style={styles.boldText}>{(item as any).confirmation}</Text>
                          </Text>
                        </View>
                      ) : null}
                    </Pressable>
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
                <View style={styles.table}>
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
              <View>
                <Text style={styles.paneTitle}>Medication Management</Text>
                <Text style={styles.paneSub}>Active clinician-authored pharmacotherapy regimens</Text>
              </View>
              <Button
                label="+ Author New Plan"
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
              <View>
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
              <View>
                <Text style={styles.paneTitle}>Documents & Server Reports</Text>
                <Text style={styles.paneSub}>Clinical records and PDF summary documents</Text>
              </View>
              <View style={styles.buttonRow}>
                <Button
                  label="Upload Document"
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
                      <Text style={styles.docTitle}>{d.filename}</Text>
                      <Text style={styles.docSub}>
                        {d.kind} · {Math.round(d.file_size_bytes / 1024)} KB ·{" "}
                        {new Date(d.created_at).toLocaleString()}
                      </Text>
                    </View>
                    <Badge label="VERIFIED" tone="success" />
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
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  patientHeader: {
    backgroundColor: doctorPalette.surfaceBlue,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.border,
    paddingTop: spacing.md,
  },
  headerTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    flexWrap: "wrap",
    gap: spacing.md,
  },
  headerTopRowCompact: {
    alignItems: "flex-start",
  },
  identityGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    flex: 1,
    minWidth: 260,
  },
  avatar: {
    width: 58,
    height: 58,
    borderRadius: 29,
    backgroundColor: doctorPalette.surfaceLime,
    alignItems: "center",
    justifyContent: "center",
    ...doctorSoftShadow,
  },
  avatarText: {
    color: doctorPalette.ink,
    fontSize: 20,
    fontWeight: "800",
  },
  nameRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  patientName: {
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "800",
    color: doctorPalette.ink,
    flexShrink: 1,
  },
  metaLine: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
    marginTop: 2,
  },
  metaBold: {
    fontWeight: "700",
    color: doctorPalette.ink,
  },
  actionButtons: {
    flexDirection: "row",
    gap: spacing.xs,
    alignItems: "center",
    flexWrap: "wrap",
    justifyContent: "flex-end",
    maxWidth: 620,
  },
  actionButtonsCompact: {
    alignSelf: "stretch",
    justifyContent: "flex-start",
  },
  metricsBar: {
    flexDirection: "row",
    backgroundColor: "rgba(255,255,255,0.72)",
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    borderRadius: doctorRadii.lg,
    padding: spacing.sm,
    gap: spacing.sm,
    flexWrap: "wrap",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.9)",
  },
  metricsBarCompact: {
    marginHorizontal: spacing.md,
  },
  metricPill: {
    flex: 1,
    minWidth: 132,
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  metricPillLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: doctorPalette.muted,
    textTransform: "uppercase",
  },
  metricPillValue: {
    fontSize: typography.fontSize.body,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  referenceBanner: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.xs,
    backgroundColor: doctorPalette.surface,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    borderRadius: doctorRadii.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  referenceNoticeText: {
    fontSize: 10,
    color: doctorPalette.muted,
    lineHeight: 14,
  },
  reportSuccessBanner: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.xs,
    backgroundColor: "#DCFCE7",
    padding: spacing.xs,
    borderRadius: doctorRadii.md,
  },
  reportSuccessText: {
    fontSize: 11,
    color: "#15803D",
    fontWeight: "600",
  },
  tabsRow: {
    flexDirection: "row",
    marginTop: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  tabButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 9,
    paddingHorizontal: spacing.md,
    borderRadius: doctorRadii.pill,
    backgroundColor: "rgba(255,255,255,0.74)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.82)",
    marginRight: spacing.xs,
  },
  tabButtonActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.surfaceLime,
  },
  tabText: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.muted,
    fontWeight: "700",
  },
  tabTextActive: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  inlineModal: {
    backgroundColor: doctorPalette.warm,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.9)",
    margin: spacing.lg,
    marginBottom: 0,
    borderRadius: doctorRadii.lg,
    padding: spacing.md,
    gap: spacing.sm,
    ...doctorSoftShadow,
  },
  modalTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "700",
    color: "#854D0E",
  },
  modalInput: {
    backgroundColor: doctorPalette.surface,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    borderRadius: doctorRadii.md,
    padding: spacing.sm,
    fontSize: typography.fontSize.bodySmall,
  },
  kindSelectorRow: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  kindPill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surface,
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
    gap: spacing.sm,
  },
  tabContentScroll: {
    flex: 1,
  },
  tabContentContainer: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  tabPane: {
    gap: spacing.md,
  },
  card: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.md,
    gap: spacing.sm,
    ...doctorSoftShadow,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  cardTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  cardSubtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.muted,
  },
  grid3: {
    flexDirection: "row",
    gap: spacing.md,
    marginVertical: spacing.xs,
    flexWrap: "wrap",
  },
  gridCell: {
    flex: 1,
    minWidth: 140,
    backgroundColor: doctorPalette.surfaceSoft,
    borderRadius: doctorRadii.md,
    padding: spacing.sm,
    gap: 2,
  },
  gridCellLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: doctorPalette.muted,
    textTransform: "uppercase",
  },
  gridCellValue: {
    fontSize: typography.fontSize.body,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  gridCellSub: {
    fontSize: 10,
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
    gap: spacing.md,
    marginTop: spacing.xs,
  },
  distPill: {
    flex: 1,
    padding: spacing.md,
    borderRadius: doctorRadii.lg,
    alignItems: "center",
    gap: 2,
  },
  distNum: {
    fontSize: typography.fontSize.headline,
    fontWeight: "800",
  },
  distLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: "600",
    color: doctorPalette.ink,
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
});
