import React from "react";
import {
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { caregiverPalette, caregiverRadii, caregiverShadow } from "./caregiverDesign";
import { EmptyState } from "../../components/primitives/EmptyState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { useCaregiverTimeline, type UnifiedTimelineItem } from "./useCaregiverTimeline";

export type CaregiverDailyTimelineProps = {
  patientId: string;
  testID?: string;
};

export function CaregiverDailyTimeline({
  patientId,
  testID,
}: CaregiverDailyTimelineProps) {
  const timeline = useCaregiverTimeline(patientId);

  if (timeline.isLoading) {
    return <LoadingState label="Loading patient's daily records…" />;
  }

  if (timeline.isError) {
    return (
      <ErrorState
        title="Could not load daily timeline"
        message="Unable to retrieve the patient's observation feed. Tap retry."
        onRetry={() => timeline.refetch()}
      />
    );
  }

  const { items, summary } = timeline;

  return (
    <View style={styles.container} testID={testID}>
      {/* Daily Pulse Summary Card */}
      <View style={styles.pulseCard}>
        <View style={styles.pulseHeader}>
          <View style={styles.pulseIconCircle}>
            <Ionicons name="pulse" size={16} color={caregiverPalette.primary} />
          </View>
          <View style={styles.pulseTitleCol}>
            <Text style={styles.pulseTitle} allowFontScaling>
              Today's Daily Pulse
            </Text>
            <Text style={styles.pulseSubtitle} allowFontScaling>
              Summary of daily meals and sugar logs
            </Text>
          </View>
        </View>

        <View style={styles.metricsGrid}>
          {/* Metric 1: Latest Glucose */}
          <View style={styles.metricCard}>
            <View style={styles.metricTopRow}>
              <Ionicons name="water" size={13} color={caregiverPalette.sky} />
              <Text style={styles.metricLabel} allowFontScaling>
                Latest Sugar
              </Text>
            </View>
            <Text
              style={[
                styles.metricValue,
                summary.latestGlucoseStatus === "in-range" && styles.valueGreen,
                summary.latestGlucoseStatus === "low" && styles.valueRed,
                summary.latestGlucoseStatus === "high" && styles.valueAmber,
              ]}
              allowFontScaling
            >
              {summary.latestGlucose?.value_mg_dl
                ? `${summary.latestGlucose.value_mg_dl}`
                : "—"}
            </Text>
            <Text style={styles.metricUnit} allowFontScaling>
              {summary.latestGlucose?.value_mg_dl ? "mg/dL" : "No readings"}
            </Text>
          </View>

          {/* Metric 2: Today Average */}
          <View style={styles.metricCard}>
            <View style={styles.metricTopRow}>
              <Ionicons name="analytics" size={13} color={caregiverPalette.tealDark} />
              <Text style={styles.metricLabel} allowFontScaling>
                Today's Avg
              </Text>
            </View>
            <Text style={styles.metricValue} allowFontScaling>
              {summary.todayAvgGlucose ? `${summary.todayAvgGlucose}` : "—"}
            </Text>
            <Text style={styles.metricUnit} allowFontScaling>
              {summary.todayAvgGlucose ? "mg/dL" : "Awaiting data"}
            </Text>
          </View>

          {/* Metric 3: Meals Logged */}
          <View style={styles.metricCard}>
            <View style={styles.metricTopRow}>
              <Ionicons name="restaurant" size={13} color={caregiverPalette.amberDark} />
              <Text style={styles.metricLabel} allowFontScaling>
                Meals Logged
              </Text>
            </View>
            <Text style={styles.metricValue} allowFontScaling>
              {summary.todayMealsCount}
            </Text>
            <Text style={styles.metricUnit} allowFontScaling>
              meals recorded
            </Text>
          </View>

          {/* Metric 4: Readings Count */}
          <View style={styles.metricCard}>
            <View style={styles.metricTopRow}>
              <Ionicons name="checkmark-circle" size={13} color={caregiverPalette.purpleDark} />
              <Text style={styles.metricLabel} allowFontScaling>
                Readings
              </Text>
            </View>
            <Text style={styles.metricValue} allowFontScaling>
              {summary.todayReadingsCount}
            </Text>
            <Text style={styles.metricUnit} allowFontScaling>
              readings logged
            </Text>
          </View>
        </View>
      </View>

      {/* Unified Timeline Items */}
      {items.length === 0 ? (
        <EmptyState
          title="No daily records logged"
          message="No blood sugar readings or meals have been recorded for this patient yet. Use the Log Sugar or Log Meal tabs above."
        />
      ) : (
        <View style={styles.timelineList}>
          <Text style={styles.timelineHeader} allowFontScaling>
            CHRONOLOGICAL DAILY INPUTS ({items.length})
          </Text>

          {items.map((item, idx) => (
            <TimelineItemRow key={`timeline-${item.sortTimestamp}-${idx}`} item={item} />
          ))}
        </View>
      )}
    </View>
  );
}

function TimelineItemRow({ item }: { item: UnifiedTimelineItem }) {
  if (item.kind === "glucose") {
    const value = item.value_mg_dl ?? 0;
    const isNormal = value >= 70 && value <= 180;
    const isLow = value < 70;
    const isHigh = value > 180;

    return (
      <View style={styles.itemCard}>
        <View style={styles.itemLeft}>
          <View
            style={[
              styles.itemIconCircle,
              isNormal && styles.circleGreen,
              isLow && styles.circleRed,
              isHigh && styles.circleAmber,
            ]}
          >
            <Ionicons
              name="water"
              size={18}
              color={isNormal ? caregiverPalette.emeraldDark : isLow ? caregiverPalette.roseDark : caregiverPalette.amberDark}
            />
          </View>
          <View style={styles.itemDetails}>
            <View style={styles.itemTitleRow}>
              <Text style={styles.glucoseValue} allowFontScaling>
                {value} <Text style={styles.glucoseUnit}>mg/dL</Text>
              </Text>
              <View
                style={[
                  styles.statusTag,
                  isNormal && styles.tagGreen,
                  isLow && styles.tagRed,
                  isHigh && styles.tagAmber,
                ]}
              >
                <Text
                  style={[
                    styles.statusTagText,
                    isNormal && styles.textGreen,
                    isLow && styles.textRed,
                    isHigh && styles.textAmber,
                  ]}
                  allowFontScaling
                >
                  {isNormal ? "Target Range" : isLow ? "Low Glucose" : "High Glucose"}
                </Text>
              </View>
            </View>

            <View style={styles.itemMetaRow}>
              <Text style={styles.metaTag} allowFontScaling>
                {item.tag ? item.tag.toUpperCase() : "RANDOM READING"}
              </Text>
              <Text style={styles.metaDot}>•</Text>
              <Text style={styles.metaTime} allowFontScaling>
                {item.formattedTime}
              </Text>
            </View>
          </View>
        </View>
      </View>
    );
  }

  // Meal item
  return (
    <View style={styles.itemCard}>
      <View style={styles.itemLeft}>
        <View style={[styles.itemIconCircle, styles.circleAmber]}>
          <Ionicons name="restaurant" size={18} color={caregiverPalette.amberDark} />
        </View>
        <View style={styles.itemDetails}>
          <Text style={styles.mealDescription} numberOfLines={2} allowFontScaling>
            {item.description}
          </Text>

          <View style={styles.itemMetaRow}>
            {item.portion_label ? (
              <>
                <Text style={styles.portionBadge} allowFontScaling>
                  {item.portion_label}
                </Text>
                <Text style={styles.metaDot}>•</Text>
              </>
            ) : null}
            <Text style={styles.metaTime} allowFontScaling>
              {item.formattedTime}
            </Text>
            <Text style={styles.metaDot}>•</Text>
            <Text style={styles.confirmedText} allowFontScaling>
              Meal Record
            </Text>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 14,
  },
  pulseCard: {
    backgroundColor: caregiverPalette.surface,
    borderRadius: caregiverRadii.lg,
    padding: 16,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    gap: 12,
    ...caregiverShadow.card,
  },
  pulseHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  pulseIconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: caregiverPalette.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  pulseTitleCol: {
    flex: 1,
  },
  pulseTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: caregiverPalette.ink,
  },
  pulseSubtitle: {
    fontSize: 11,
    color: caregiverPalette.muted,
    marginTop: 1,
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  metricCard: {
    width: "48.5%",
    backgroundColor: caregiverPalette.surfaceMuted,
    borderRadius: caregiverRadii.md,
    padding: 12,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    gap: 2,
  },
  metricTopRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  metricLabel: {
    fontSize: 10,
    color: caregiverPalette.muted,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  metricValue: {
    fontSize: 18,
    fontWeight: "800",
    color: caregiverPalette.ink,
    marginTop: 2,
  },
  valueGreen: {
    color: caregiverPalette.emeraldDark,
  },
  valueRed: {
    color: caregiverPalette.roseDark,
  },
  valueAmber: {
    color: caregiverPalette.amberDark,
  },
  metricUnit: {
    fontSize: 10,
    color: caregiverPalette.muted,
    fontWeight: "500",
  },
  timelineList: {
    gap: 10,
  },
  timelineHeader: {
    fontSize: 11,
    fontWeight: "800",
    color: caregiverPalette.muted,
    letterSpacing: 0.6,
    paddingHorizontal: 2,
  },
  itemCard: {
    backgroundColor: caregiverPalette.surface,
    borderRadius: caregiverRadii.md,
    padding: 13,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    ...caregiverShadow.subtle,
  },
  itemLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    flex: 1,
  },
  itemIconCircle: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: "center",
    justifyContent: "center",
  },
  circleGreen: {
    backgroundColor: caregiverPalette.emeraldSoft,
  },
  circleRed: {
    backgroundColor: caregiverPalette.roseSoft,
  },
  circleAmber: {
    backgroundColor: caregiverPalette.amberSoft,
  },
  itemDetails: {
    flex: 1,
    gap: 3,
  },
  itemTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  glucoseValue: {
    fontSize: 16,
    fontWeight: "800",
    color: caregiverPalette.ink,
  },
  glucoseUnit: {
    fontSize: 11,
    fontWeight: "500",
    color: caregiverPalette.muted,
  },
  statusTag: {
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: caregiverRadii.pill,
  },
  tagGreen: {
    backgroundColor: caregiverPalette.emeraldSoft,
  },
  tagRed: {
    backgroundColor: caregiverPalette.roseSoft,
  },
  tagAmber: {
    backgroundColor: caregiverPalette.amberSoft,
  },
  statusTagText: {
    fontSize: 10,
    fontWeight: "700",
  },
  textGreen: {
    color: caregiverPalette.emeraldDark,
  },
  textRed: {
    color: caregiverPalette.roseDark,
  },
  textAmber: {
    color: caregiverPalette.amberDark,
  },
  mealDescription: {
    fontSize: 13,
    fontWeight: "700",
    color: caregiverPalette.ink,
  },
  itemMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  metaTag: {
    fontSize: 10,
    fontWeight: "700",
    color: caregiverPalette.muted,
  },
  metaDot: {
    fontSize: 10,
    color: caregiverPalette.borderHighlight,
  },
  metaTime: {
    fontSize: 11,
    color: caregiverPalette.muted,
  },
  portionBadge: {
    fontSize: 10,
    fontWeight: "700",
    color: caregiverPalette.amberDark,
  },
  confirmedText: {
    fontSize: 10,
    fontWeight: "700",
    color: caregiverPalette.primary,
  },
});
