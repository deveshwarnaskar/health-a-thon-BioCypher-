import React, { useState } from "react";
import {
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
import { touchTarget } from "../../../theming/tokens";
import {
  doctorPalette,
  doctorRadii,
  doctorShadow,
  doctorSoftShadow,
  doctorPillShadow,
} from "../doctorDesign";
import type { PatientSummaryResponse } from "../../../services/schemas/patients";

export type DoctorHomeTabProps = {
  doctorName?: string | null;
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

export function DoctorHomeTab({
  doctorName,
  facilityId: propFacilityId,
  patients,
  reviewCount,
  taskCount,
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
  const [activeWorkflowTab, setActiveWorkflowTab] = useState<
    "patients" | "review" | "telemetry" | "more"
  >("patients");

  const handlePullToRefresh = async () => {
    setIsRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setIsRefreshing(false);
    }
  };

  const activePatients = patients.filter((p) => p.active);
  const featuredPatient = patients[0];
  const highlightPatient1 = patients[1] || featuredPatient;
  const highlightPatient2 = patients[2] || featuredPatient;

  return (
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
      {/* 1. Floating Modern Search Bar with filter button */}
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
        <TouchableOpacity
          style={styles.filterButton}
          onPress={onNavigateToPatients}
          accessibilityRole="button"
          accessibilityLabel="Open patient directory filters"
          activeOpacity={0.7}
        >
          <Ionicons name="options-outline" size={20} color={doctorPalette.ink} />
        </TouchableOpacity>
      </View>

      {/* 2. Workflow / Category Square Cards Row */}
      <View style={styles.categorySection}>
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle} allowFontScaling>
            Clinical Workflows
          </Text>
          <TouchableOpacity
            onPress={onNavigateToWorkspaceHub}
            accessibilityRole="button"
            accessibilityLabel="View all clinical workstations"
          >
            <Text style={styles.viewAllText} allowFontScaling>
              View all
            </Text>
          </TouchableOpacity>
        </View>

        <View style={styles.categoryRow}>
          {/* Card 1: Cohort / Patients (Active style with lime-green accent) */}
          <TouchableOpacity
            style={[
              styles.categorySquare,
              activeWorkflowTab === "patients" ? styles.categorySquareActive : styles.categorySquareDefault,
            ]}
            onPress={() => {
              setActiveWorkflowTab("patients");
              onNavigateToPatients();
            }}
            accessibilityRole="button"
            accessibilityLabel={`Patient Cohort, ${patients.length} records`}
            activeOpacity={0.75}
          >
            <View style={styles.categoryIconWrap}>
              <Ionicons
                name="people"
                size={24}
                color={activeWorkflowTab === "patients" ? doctorPalette.ink : doctorPalette.muted}
              />
            </View>
            <Text
              style={[
                styles.categoryLabel,
                activeWorkflowTab === "patients" ? styles.categoryLabelActive : null,
              ]}
              allowFontScaling
              numberOfLines={1}
            >
              Cohort
            </Text>
          </TouchableOpacity>

          {/* Card 2: AI Review */}
          <TouchableOpacity
            style={[
              styles.categorySquare,
              activeWorkflowTab === "review" ? styles.categorySquareActive : styles.categorySquareDefault,
            ]}
            onPress={() => {
              setActiveWorkflowTab("review");
              onNavigateToReview();
            }}
            accessibilityRole="button"
            accessibilityLabel={`AI Review Queue, ${reviewCount} pending`}
            activeOpacity={0.75}
          >
            <View style={styles.categoryIconWrap}>
              <Ionicons
                name="sparkles"
                size={22}
                color={activeWorkflowTab === "review" ? doctorPalette.ink : "#F59E0B"}
              />
              {reviewCount > 0 ? <View style={styles.categoryDot} /> : null}
            </View>
            <Text
              style={[
                styles.categoryLabel,
                activeWorkflowTab === "review" ? styles.categoryLabelActive : null,
              ]}
              allowFontScaling
              numberOfLines={1}
            >
              AI Review
            </Text>
          </TouchableOpacity>

          {/* Card 3: Telemetry */}
          <TouchableOpacity
            style={[
              styles.categorySquare,
              activeWorkflowTab === "telemetry" ? styles.categorySquareActive : styles.categorySquareDefault,
            ]}
            onPress={() => {
              setActiveWorkflowTab("telemetry");
              onNavigateToSubWorkspace("monitoring");
            }}
            accessibilityRole="button"
            accessibilityLabel="Longitudinal Telemetry Monitoring"
            activeOpacity={0.75}
          >
            <View style={styles.categoryIconWrap}>
              <Ionicons
                name="analytics"
                size={22}
                color={activeWorkflowTab === "telemetry" ? doctorPalette.ink : "#8B5CF6"}
              />
            </View>
            <Text
              style={[
                styles.categoryLabel,
                activeWorkflowTab === "telemetry" ? styles.categoryLabelActive : null,
              ]}
              allowFontScaling
              numberOfLines={1}
            >
              Telemetry
            </Text>
          </TouchableOpacity>

          {/* Card 4: More / Hub */}
          <TouchableOpacity
            style={[
              styles.categorySquare,
              activeWorkflowTab === "more" ? styles.categorySquareActive : styles.categorySquareDefault,
            ]}
            onPress={() => {
              setActiveWorkflowTab("more");
              onNavigateToWorkspaceHub();
            }}
            accessibilityRole="button"
            accessibilityLabel="Open all utilities"
            activeOpacity={0.75}
          >
            <View style={styles.categoryIconWrap}>
              <Ionicons
                name="grid"
                size={22}
                color={activeWorkflowTab === "more" ? doctorPalette.ink : doctorPalette.muted}
              />
            </View>
            <Text
              style={[
                styles.categoryLabel,
                activeWorkflowTab === "more" ? styles.categoryLabelActive : null,
              ]}
              allowFontScaling
              numberOfLines={1}
            >
              More
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* 3. Featured Patient / Urgent Priority Hero Card */}
      <View style={styles.featuredSection}>
        <Text style={styles.sectionTitle} allowFontScaling>
          Priority Clinical Focus
        </Text>

        {featuredPatient ? (
          <View style={styles.featuredCard}>
            <View style={styles.featuredCardContent}>
              {/* Top Row: Name with verified checkmark & graphic */}
              <View style={styles.featuredTopRow}>
                <View style={styles.featuredInfoCol}>
                  <View style={styles.patientNameWithBadge}>
                    <Text style={styles.featuredPatientName} numberOfLines={1} allowFontScaling>
                      {featuredPatient.name}
                    </Text>
                    <Ionicons name="checkmark-circle" size={18} color={doctorPalette.primary} />
                  </View>
                  <Text style={styles.featuredPatientMeta} allowFontScaling>
                    Type 2 Diabetes · UHID: {featuredPatient.uh_id}
                  </Text>

                  {/* Rating / Metric badge pill */}
                  <View style={styles.metricPillBadge}>
                    <Ionicons name="water" size={13} color="#DC2626" />
                    <Text style={styles.metricPillBadgeText} allowFontScaling>
                      Fasting 184 mg/dL · TIR 54%
                    </Text>
                  </View>
                </View>

                {/* Stethoscope / Avatar Graphic Circle */}
                <View style={styles.featuredAvatarCircle}>
                  <Ionicons name="medical" size={28} color={doctorPalette.ink} />
                </View>
              </View>

              {/* Stat Chips Row */}
              <View style={styles.statChipsRow}>
                <View style={styles.miniStatChip}>
                  <Ionicons name="calendar-outline" size={13} color={doctorPalette.ink} />
                  <Text style={styles.miniStatText} allowFontScaling>
                    14-Day Baseline
                  </Text>
                </View>
                <View style={styles.miniStatChip}>
                  <Ionicons name="time-outline" size={13} color={doctorPalette.ink} />
                  <Text style={styles.miniStatText} allowFontScaling>
                    High Excursion
                  </Text>
                </View>
              </View>

              {/* Vibrant Blue Pill Action Button */}
              <TouchableOpacity
                style={styles.featuredActionButton}
                onPress={() => onSelectPatient(featuredPatient)}
                accessibilityRole="button"
                accessibilityLabel={`Inspect clinical care plan for ${featuredPatient.name}`}
                activeOpacity={0.85}
              >
                <Text style={styles.featuredActionText} allowFontScaling>
                  Review Care Plan
                </Text>
                <View style={styles.featuredActionArrow}>
                  <Ionicons name="arrow-forward" size={14} color={doctorPalette.primary} />
                </View>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <View style={styles.emptyFeaturedCard}>
            <Ionicons name="people-outline" size={32} color={doctorPalette.muted} />
            <Text style={styles.emptyFeaturedText} allowFontScaling>
              No patients registered in facility cohort.
            </Text>
          </View>
        )}
      </View>

      {/* 4. Cohort Highlights Section (Dual Modern Cards like "Nearby Specialists") */}
      <View style={styles.highlightsSection}>
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle} allowFontScaling>
            Active Cohort Rounds
          </Text>
          <TouchableOpacity
            onPress={onNavigateToPatients}
            accessibilityRole="button"
            accessibilityLabel="View full patient cohort"
          >
            <Text style={styles.viewAllText} allowFontScaling>
              View all
            </Text>
          </TouchableOpacity>
        </View>

        <View style={styles.dualCardsRow}>
          {/* Card 1: Electric Solid Blue Card */}
          {highlightPatient1 ? (
            <TouchableOpacity
              style={styles.blueHighlightCard}
              onPress={() => onSelectPatient(highlightPatient1)}
              accessibilityRole="button"
              accessibilityLabel={`Open record for ${highlightPatient1.name}`}
              activeOpacity={0.85}
            >
              <View style={styles.highlightAvatarCircleWhite}>
                <Text style={styles.highlightAvatarTextBlue} allowFontScaling>
                  {highlightPatient1.name.charAt(0).toUpperCase()}
                </Text>
              </View>

              <Text style={styles.highlightNameWhite} numberOfLines={1} allowFontScaling>
                {highlightPatient1.name}
              </Text>
              <Text style={styles.highlightMetaWhite} numberOfLines={1} allowFontScaling>
                {highlightPatient1.uh_id} · Active
              </Text>

              <View style={styles.highlightFooter}>
                <View style={styles.miniTagWhite}>
                  <Text style={styles.miniTagWhiteText} allowFontScaling>
                    TIR 72%
                  </Text>
                </View>
                <View style={styles.circleArrowBtnWhite}>
                  <Ionicons name="arrow-forward" size={14} color={doctorPalette.primary} />
                </View>
              </View>
            </TouchableOpacity>
          ) : null}

          {/* Card 2: Crisp White Card with lime accent arrow */}
          {highlightPatient2 ? (
            <TouchableOpacity
              style={styles.whiteHighlightCard}
              onPress={() => onSelectPatient(highlightPatient2)}
              accessibilityRole="button"
              accessibilityLabel={`Open record for ${highlightPatient2.name}`}
              activeOpacity={0.85}
            >
              <View style={styles.highlightAvatarCircleSoft}>
                <Text style={styles.highlightAvatarTextDark} allowFontScaling>
                  {highlightPatient2.name.charAt(0).toUpperCase()}
                </Text>
              </View>

              <Text style={styles.highlightNameDark} numberOfLines={1} allowFontScaling>
                {highlightPatient2.name}
              </Text>
              <Text style={styles.highlightMetaDark} numberOfLines={1} allowFontScaling>
                {highlightPatient2.uh_id} · Routine
              </Text>

              <View style={styles.highlightFooter}>
                <View style={styles.miniTagLime}>
                  <Text style={styles.miniTagLimeText} allowFontScaling>
                    Stable
                  </Text>
                </View>
                <View style={styles.circleArrowBtnLime}>
                  <Ionicons name="arrow-forward" size={14} color={doctorPalette.ink} />
                </View>
              </View>
            </TouchableOpacity>
          ) : null}
        </View>
      </View>

      {/* 5. Clinical Safety & Decision Support Governance Card */}
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
          All glycemic indices, time-in-range measurements, and longitudinal baselines are computed
          with strict mathematical determinism. Machine-generated dietary observations require human
          doctor sign-off before entering authoritative medical records.
        </Text>
      </View>
    </ScrollView>
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
    paddingBottom: 110,
    gap: 20,
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
  filterButton: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: doctorPalette.surface,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    ...doctorSoftShadow,
  },
  categorySection: {
    gap: 12,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.2,
  },
  viewAllText: {
    fontSize: 13,
    fontWeight: "700",
    color: doctorPalette.muted,
  },
  categoryRow: {
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
  categoryDot: {
    position: "absolute",
    top: -2,
    right: -4,
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
  featuredSection: {
    gap: 12,
  },
  featuredCard: {
    backgroundColor: doctorPalette.limeSoft,
    borderRadius: 26,
    borderWidth: 1,
    borderColor: doctorPalette.limeBorder,
    padding: 20,
    ...doctorSoftShadow,
  },
  featuredCardContent: {
    gap: 14,
  },
  featuredTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  featuredInfoCol: {
    flex: 1,
  },
  patientNameWithBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  featuredPatientName: {
    fontSize: 22,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.2,
    maxWidth: 200,
  },
  featuredPatientMeta: {
    fontSize: 13,
    color: doctorPalette.inkSecondary,
    marginTop: 2,
  },
  metricPillBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(255, 255, 255, 0.7)",
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 10,
    paddingVertical: 4,
    alignSelf: "flex-start",
    marginTop: 8,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.9)",
  },
  metricPillBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: doctorPalette.ink,
  },
  featuredAvatarCircle: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: doctorPalette.surfaceLime,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: "rgba(255, 255, 255, 0.8)",
    ...doctorSoftShadow,
  },
  statChipsRow: {
    flexDirection: "row",
    gap: 8,
  },
  miniStatChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: "rgba(255, 255, 255, 0.65)",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: doctorRadii.pill,
  },
  miniStatText: {
    fontSize: 11,
    fontWeight: "700",
    color: doctorPalette.ink,
  },
  featuredActionButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: doctorPalette.primary,
    borderRadius: doctorRadii.pill,
    paddingVertical: 12,
    paddingHorizontal: 18,
    minHeight: touchTarget.min,
    ...doctorPillShadow,
  },
  featuredActionText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: 0.1,
  },
  featuredActionArrow: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
  },
  emptyFeaturedCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    padding: 24,
    alignItems: "center",
    gap: 8,
    ...doctorSoftShadow,
  },
  emptyFeaturedText: {
    fontSize: 14,
    color: doctorPalette.muted,
  },
  highlightsSection: {
    gap: 12,
  },
  dualCardsRow: {
    flexDirection: "row",
    gap: 12,
  },
  blueHighlightCard: {
    flex: 1,
    backgroundColor: doctorPalette.primary,
    borderRadius: 24,
    padding: 16,
    gap: 8,
    ...doctorPillShadow,
  },
  whiteHighlightCard: {
    flex: 1,
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    padding: 16,
    gap: 8,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    ...doctorSoftShadow,
  },
  highlightAvatarCircleWhite: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "rgba(255, 255, 255, 0.22)",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.4)",
  },
  highlightAvatarTextBlue: {
    fontSize: 18,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  highlightAvatarCircleSoft: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "#DBEAFE",
  },
  highlightAvatarTextDark: {
    fontSize: 18,
    fontWeight: "800",
    color: doctorPalette.primary,
  },
  highlightNameWhite: {
    fontSize: 16,
    fontWeight: "800",
    color: "#FFFFFF",
    marginTop: 2,
  },
  highlightMetaWhite: {
    fontSize: 12,
    color: "rgba(255, 255, 255, 0.8)",
  },
  highlightNameDark: {
    fontSize: 16,
    fontWeight: "800",
    color: doctorPalette.ink,
    marginTop: 2,
  },
  highlightMetaDark: {
    fontSize: 12,
    color: doctorPalette.muted,
  },
  highlightFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 6,
  },
  miniTagWhite: {
    backgroundColor: "rgba(255, 255, 255, 0.2)",
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  miniTagWhiteText: {
    color: "#FFFFFF",
    fontSize: 10,
    fontWeight: "800",
  },
  miniTagLime: {
    backgroundColor: doctorPalette.surfaceLime,
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  miniTagLimeText: {
    color: doctorPalette.ink,
    fontSize: 10,
    fontWeight: "800",
  },
  circleArrowBtnWhite: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
  },
  circleArrowBtnLime: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: doctorPalette.surfaceLime,
    alignItems: "center",
    justifyContent: "center",
  },
  safetyCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    padding: 18,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    gap: 10,
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
});
