import React, { useState } from "react";
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget } from "../../../theming/tokens";
import { TodaySummaryCard, type TodayItem } from "../components/TodaySummaryCard";
import { TimelineItemRow } from "../components/TimelineItemRow";
import { WhatsAppHomeCard } from "../components/WhatsAppHomeCard";
import { useGlucoseFeed } from "../../glucose/useGlucoseFeed";
import { usePatientMeals } from "../../meals/usePatientMeals";
import { usePatientMedications, useUnifiedTimeline, usePatientNotifications } from "../api";
import { useCareTasks } from "../../tasks/useCareTasks";
import { useWhatsAppIdentity } from "../useWhatsAppIdentity";
import type { RecordOptionKey } from "./RecordTab";

export type HomeTabProps = {
  patientId: string | null;
  patientName?: string;
  onNavigateToRecord: (type?: RecordOptionKey) => void;
  onNavigateToTimeline: () => void;
  onNavigateToTasks: () => void;
  onNavigateToMedications: () => void;
  onNavigateToReports?: () => void;
  onOpenNotifications: () => void;
  onOpenAssist: () => void;
  onSignOut?: () => void;
  onConnectWhatsApp?: () => void;
};

export function HomeTab({
  patientId,
  patientName,
  onNavigateToRecord,
  onNavigateToTimeline,
  onNavigateToTasks,
  onNavigateToMedications,
  onNavigateToReports,
  onOpenNotifications,
  onOpenAssist,
  onSignOut,
  onConnectWhatsApp,
}: HomeTabProps) {
  const [activeCategory, setActiveCategory] = useState<
    "all" | "glucose" | "meals" | "medication" | "activity" | "tasks"
  >("all");

  const glucoseFeed = useGlucoseFeed(patientId);
  const mealsFeed = usePatientMeals(patientId);
  const medicationsQuery = usePatientMedications(patientId);
  const tasksQuery = useCareTasks({ patient_id: patientId ?? undefined });
  const timelineQuery = useUnifiedTimeline(patientId);
  const notificationsQuery = usePatientNotifications(patientId);
  const whatsAppQuery = useWhatsAppIdentity();

  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([
        glucoseFeed.refetch(),
        mealsFeed.refetch(),
        medicationsQuery.refetch(),
        tasksQuery.refetch(),
        timelineQuery.refetch(),
        notificationsQuery.refetch(),
        whatsAppQuery.refetch(),
      ]);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Derive today's state
  const latestGlucose = glucoseFeed.readings?.[0];
  const mealCountToday = mealsFeed.meals?.length || 0;
  const plans = medicationsQuery.data || [];
  const firstPlan = plans[0];
  const activeTasks = tasksQuery.data?.items || [];
  const pendingTasks = activeTasks.filter((t) => t.status !== "completed");

  const unreadNotifications = (notificationsQuery.data || []).filter(
    (n) => n.status !== "delivered" && n.status !== "cancelled"
  ).length;

  // Data completeness calculation
  const todayStr = new Date().toDateString();
  const hasGlucoseToday = !!latestGlucose && new Date(latestGlucose.taken_at).toDateString() === todayStr;
  const hasMealToday = mealCountToday > 0;
  const hasMedicationPlan = plans.length > 0;
  const hasActivityToday = (timelineQuery.data || []).some(
    (e) => e.type === "activity" && new Date(e.timestamp).toDateString() === todayStr
  );

  let completionPoints = 0;
  if (hasGlucoseToday || latestGlucose) completionPoints += 25;
  if (hasMealToday) completionPoints += 25;
  if (hasMedicationPlan) completionPoints += 25;
  if (hasActivityToday) completionPoints += 25;
  const completenessPct = completionPoints;

  // User presentation details
  const userInitial = (patientName?.trim()?.charAt(0) || "P").toUpperCase();
  const displayClinic = `Apollo Sugar Clinic · UHID-${patientId ? patientId.slice(0, 5).toUpperCase() : "99214"}`;

  // Build Today attention items
  const todayItems: TodayItem[] = [];

  if (firstPlan) {
    todayItems.push({
      id: "med-1",
      label: `Medication (${firstPlan.medication})`,
      status: "due",
      time: "Scheduled",
    });
  }

  if (latestGlucose) {
    const timeStr = new Date(latestGlucose.taken_at).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    todayItems.push({
      id: "glucose-1",
      label: `Glucose reading (${latestGlucose.value_mg_dl ?? "--"} mg/dL)`,
      status: "completed",
      time: timeStr,
    });
  } else {
    todayItems.push({
      id: "glucose-1",
      label: "Record morning glucose",
      status: "due",
      time: "Fasting",
    });
  }

  if (mealCountToday > 0) {
    todayItems.push({
      id: "meal-1",
      label: "Meal logged",
      status: "completed",
      time: "Today",
    });
  } else {
    todayItems.push({
      id: "meal-1",
      label: "Log meal",
      status: "due",
      time: "Due",
    });
  }

  // Recent activity (top 3 timeline events)
  const recentEvents = (timelineQuery.data || []).slice(0, 3);

  return (
    <View style={styles.container}>
      {/* Modern High-Density App Header */}
      <View style={styles.topHeader}>
        <View style={styles.headerLeftCol}>
          <View style={styles.headerAppKickerRow}>
            <Text style={styles.headerAppKicker} allowFontScaling>
              THALI CARE
            </Text>
            <View style={styles.roleTag}>
              <Text style={styles.roleTagText} allowFontScaling>
                Patient
              </Text>
            </View>
          </View>
          <Text style={styles.headerMainTitle} allowFontScaling numberOfLines={1}>
            {patientName || "Care Active"}
          </Text>
          <TouchableOpacity
            style={styles.facilitySelectorRow}
            activeOpacity={0.7}
            accessibilityRole="button"
            accessibilityLabel="Clinical facility selector"
          >
            <Text style={styles.facilitySelectorText} allowFontScaling numberOfLines={1}>
              {displayClinic}
            </Text>
            <Ionicons name="chevron-down" size={13} color="#0F172A" style={{ marginLeft: 3 }} />
          </TouchableOpacity>
        </View>

        <View style={styles.headerRightCol}>
          {onSignOut ? (
            <TouchableOpacity
              style={styles.headerSignOutButton}
              onPress={onSignOut}
              accessibilityRole="button"
              accessibilityLabel="Sign out"
              activeOpacity={0.7}
            >
              <Ionicons name="log-out-outline" size={15} color="#DC2626" style={{ marginRight: 4 }} />
              <Text style={styles.headerSignOutText} allowFontScaling>
                Sign out
              </Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.headerStatusPill}>
              <Ionicons name="shield-checkmark" size={13} color="#0D9488" style={{ marginRight: 3 }} />
              <Text style={styles.headerStatusText} allowFontScaling>
                Active Plan
              </Text>
            </View>
          )}

          <TouchableOpacity
            style={styles.headerIconButton}
            onPress={onOpenNotifications}
            accessibilityRole="button"
            accessibilityLabel={`Notifications, ${unreadNotifications} unread`}
            activeOpacity={0.7}
          >
            <Ionicons name="notifications-outline" size={20} color="#0F172A" />
            {unreadNotifications > 0 ? (
              <View style={styles.headerBadge}>
                <Text style={styles.headerBadgeText} allowFontScaling>
                  {unreadNotifications > 9 ? "9+" : unreadNotifications}
                </Text>
              </View>
            ) : null}
          </TouchableOpacity>

          <View style={styles.headerAvatarCircle}>
            <Text style={styles.headerAvatarInitial} allowFontScaling>
              {userInitial}
            </Text>
          </View>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            tintColor={colors.primary}
            colors={[colors.primary]}
          />
        }
      >
        {/* Floating Search / Quick Assist Bar (Airbnb Style) */}
        <TouchableOpacity
          style={styles.searchBarContainer}
          onPress={onOpenAssist}
          accessibilityRole="button"
          accessibilityLabel="THALI Assist AI care guide"
          activeOpacity={0.85}
        >
          <Ionicons name="search" size={18} color="#64748B" style={styles.searchIcon} />
          <Text style={styles.searchPlaceholderText} allowFontScaling numberOfLines={1}>
            Search &quot;fasting glucose&quot;, &quot;dal roti&quot;, &quot;meds&quot;...
          </Text>
          <View style={styles.searchRightBadge}>
            <Ionicons name="sparkles" size={15} color="#0D9488" />
          </View>
        </TouchableOpacity>

        {/* Category Navigation Bar (Airbnb / Blinkit style) */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.categoryBar}
        >
          {[
            { key: "all", label: "All", icon: "sparkles" },
            { key: "glucose", label: "Glucose", icon: "water-outline" },
            { key: "meals", label: "Meals", icon: "restaurant-outline" },
            { key: "medication", label: "Medication", icon: "medkit-outline" },
            { key: "activity", label: "Activity", icon: "walk-outline" },
            { key: "tasks", label: "Care Tasks", icon: "checkbox-outline" },
          ].map((cat) => {
            const isSelected = activeCategory === cat.key;
            return (
              <TouchableOpacity
                key={cat.key}
                style={styles.categoryItem}
                onPress={() => {
                  setActiveCategory(cat.key as any);
                  if (cat.key === "glucose") onNavigateToRecord("glucose");
                  else if (cat.key === "meals") onNavigateToRecord("meal");
                  else if (cat.key === "medication") onNavigateToMedications();
                  else if (cat.key === "activity") onNavigateToRecord("activity");
                  else if (cat.key === "tasks") onNavigateToTasks();
                }}
                activeOpacity={0.7}
                accessibilityRole="button"
                accessibilityLabel={`Filter by ${cat.label}`}
              >
                <Ionicons
                  name={cat.icon as any}
                  size={20}
                  color={isSelected ? "#0F172A" : "#64748B"}
                />
                <Text
                  style={[
                    styles.categoryLabel,
                    isSelected && styles.categoryLabelActive,
                  ]}
                  allowFontScaling
                >
                  {cat.label}
                </Text>
                {isSelected ? <View style={styles.categoryIndicator} /> : null}
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {/* Section 1: Care Command (Bento Grid Layout) */}
        <View style={styles.commandSection}>
          <View style={styles.commandHeaderRow}>
            <View style={styles.commandTitleCol}>
              <Text style={styles.commandKicker} allowFontScaling>
                TODAY&apos;S OPERATIONS
              </Text>
              <View style={styles.commandTitleWithDot}>
                <Text style={styles.commandTitle} allowFontScaling>
                  Daily Care
                </Text>
                <View style={styles.commandPulseDot} />
              </View>
            </View>

            <TouchableOpacity
              style={styles.viewTimelineBtn}
              onPress={onNavigateToTimeline}
              activeOpacity={0.7}
              accessibilityRole="button"
              accessibilityLabel="View full timeline"
            >
              <Text style={styles.viewTimelineText} allowFontScaling>
                View Timeline
              </Text>
              <Ionicons name="arrow-forward" size={13} color="#0F172A" style={{ marginLeft: 3 }} />
            </TouchableOpacity>
          </View>

          {/* Bento Grid Layout */}
          <View style={styles.bentoGrid}>
            {/* Left Hero Card (~44% width) */}
            <TouchableOpacity
              style={styles.bentoHeroCard}
              onPress={() => onNavigateToRecord("glucose")}
              activeOpacity={0.8}
              accessibilityRole="button"
              accessibilityLabel="Glucose status hero card"
            >
              <View>
                <Text style={styles.bentoHeroKicker} allowFontScaling>
                  On Plan Now
                </Text>
                <View style={styles.bentoHeroBadge}>
                  <Text style={styles.bentoHeroBadgeText} allowFontScaling numberOfLines={1}>
                    {latestGlucose ? `${latestGlucose.value_mg_dl} mg/dL` : "Tap to Log"}
                  </Text>
                </View>
              </View>

              <View>
                <Text style={styles.bentoHeroSubtext} allowFontScaling numberOfLines={2}>
                  {latestGlucose
                    ? latestGlucose.tag
                      ? `${latestGlucose.tag.replace("_", " ").toUpperCase()}`
                      : "NORMAL RANGE"
                    : "Target: 80–130 mg/dL"}
                </Text>
              </View>

              <Ionicons
                name="water"
                size={42}
                color="rgba(255, 255, 255, 0.16)"
                style={styles.bentoHeroWatermark}
              />
            </TouchableOpacity>

            {/* Right 2x2 Grid (~54% width) */}
            <View style={styles.bentoRightCol}>
              <View style={styles.bentoRow}>
                {/* Meals Card (Amber) */}
                <TouchableOpacity
                  style={[styles.bentoSmallCard, styles.bentoCardAmber]}
                  onPress={() => onNavigateToRecord("meal")}
                  activeOpacity={0.7}
                  accessibilityRole="button"
                  accessibilityLabel="Today's meals card"
                >
                  <Text style={styles.bentoSmallKickerAmber} allowFontScaling>
                    Today&apos;s Meals
                  </Text>
                  <Text style={styles.bentoSmallValAmber} allowFontScaling numberOfLines={1}>
                    {mealCountToday} Logged
                  </Text>
                  <View style={styles.bentoSmallBadgeAmber}>
                    <Text style={styles.bentoSmallBadgeTextAmber} allowFontScaling>
                      {mealCountToday > 0 ? "Active" : "Log Meal"}
                    </Text>
                  </View>
                </TouchableOpacity>

                {/* Medication Card (Rose) */}
                <TouchableOpacity
                  style={[styles.bentoSmallCard, styles.bentoCardRose]}
                  onPress={onNavigateToMedications}
                  activeOpacity={0.7}
                  accessibilityRole="button"
                  accessibilityLabel="Medication regimen card"
                >
                  <Text style={styles.bentoSmallKickerRose} allowFontScaling>
                    Medication
                  </Text>
                  <Text style={styles.bentoSmallValRose} allowFontScaling numberOfLines={1}>
                    {plans.length} Prescribed
                  </Text>
                  <View style={styles.bentoSmallBadgeRose}>
                    <Text style={styles.bentoSmallBadgeTextRose} allowFontScaling>
                      {firstPlan ? "Active Plan" : "None"}
                    </Text>
                  </View>
                </TouchableOpacity>
              </View>

              <View style={styles.bentoRow}>
                {/* Care Tasks Card (Emerald) */}
                <TouchableOpacity
                  style={[styles.bentoSmallCard, styles.bentoCardEmerald]}
                  onPress={onNavigateToTasks}
                  activeOpacity={0.7}
                  accessibilityRole="button"
                  accessibilityLabel="Care tasks card"
                >
                  <Text style={styles.bentoSmallKickerEmerald} allowFontScaling>
                    Care Tasks
                  </Text>
                  <Text style={styles.bentoSmallValEmerald} allowFontScaling numberOfLines={1}>
                    {pendingTasks.length} Pending
                  </Text>
                  <View style={styles.bentoSmallBadgeEmerald}>
                    <Text style={styles.bentoSmallBadgeTextEmerald} allowFontScaling>
                      {pendingTasks.length === 0 ? "All Done" : "Due Today"}
                    </Text>
                  </View>
                </TouchableOpacity>

                {/* 7-Day Review Card (Purple) */}
                <TouchableOpacity
                  style={[styles.bentoSmallCard, styles.bentoCardPurple]}
                  onPress={onNavigateToReports}
                  activeOpacity={0.7}
                  accessibilityRole="button"
                  accessibilityLabel="7-day review card"
                >
                  <Text style={styles.bentoSmallKickerPurple} allowFontScaling>
                    7-Day Review
                  </Text>
                  <Text style={styles.bentoSmallValPurple} allowFontScaling numberOfLines={1}>
                    ADA Summary
                  </Text>
                  <View style={styles.bentoSmallBadgePurple}>
                    <Text style={styles.bentoSmallBadgeTextPurple} allowFontScaling>
                      Report
                    </Text>
                  </View>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </View>

        {/* Quick Record Action Row */}
        <View style={styles.quickRecordRow}>
          <TouchableOpacity
            style={[styles.quickActionBtn, styles.quickActionGlucose]}
            onPress={() => onNavigateToRecord("glucose")}
            accessibilityRole="button"
            accessibilityLabel="Quick record glucose"
            activeOpacity={0.7}
          >
            <Ionicons name="water" size={15} color="#DC2626" />
            <Text style={[styles.quickActionText, styles.quickActionTextGlucose]} allowFontScaling>
              Glucose
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.quickActionBtn, styles.quickActionMeal]}
            onPress={() => onNavigateToRecord("meal")}
            accessibilityRole="button"
            accessibilityLabel="Quick record meal"
            activeOpacity={0.7}
          >
            <Ionicons name="restaurant" size={15} color="#D97706" />
            <Text style={[styles.quickActionText, styles.quickActionTextMeal]} allowFontScaling>
              Meal
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.quickActionBtn, styles.quickActionMeds]}
            onPress={() => onNavigateToRecord("medication")}
            accessibilityRole="button"
            accessibilityLabel="Quick record medication dose"
            activeOpacity={0.7}
          >
            <Ionicons name="medkit" size={15} color="#2563EB" />
            <Text style={[styles.quickActionText, styles.quickActionTextMeds]} allowFontScaling>
              Meds
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.quickActionBtn, styles.quickActionActivity]}
            onPress={() => onNavigateToRecord("activity")}
            accessibilityRole="button"
            accessibilityLabel="Quick record activity"
            activeOpacity={0.7}
          >
            <Ionicons name="walk" size={15} color="#059669" />
            <Text style={[styles.quickActionText, styles.quickActionTextActivity]} allowFontScaling>
              Activity
            </Text>
          </TouchableOpacity>
        </View>

        {/* Today Summary Checklist */}
        <TodaySummaryCard items={todayItems} />

        {/* Data Completeness Card */}
        <View style={styles.completenessCard}>
          <View style={styles.completenessHeader}>
            <View>
              <Text style={styles.completenessKicker} allowFontScaling>
                DATA COMPLETENESS
              </Text>
              <Text style={styles.completenessTitle} allowFontScaling>
                Today&apos;s Record: {completenessPct}% complete
              </Text>
            </View>
            <View
              style={[
                styles.completenessBadge,
                completenessPct >= 75 ? styles.completenessBadgeGood : styles.completenessBadgeWarn,
              ]}
            >
              <Text
                style={[
                  styles.completenessBadgeText,
                  completenessPct >= 75 ? styles.completenessBadgeTextGood : styles.completenessBadgeTextWarn,
                ]}
                allowFontScaling
              >
                {completenessPct >= 75 ? "On Track" : "Action Needed"}
              </Text>
            </View>
          </View>
          <View style={styles.progressBarBackground}>
            <View style={[styles.progressBarFill, { width: `${completenessPct}%` }]} />
          </View>
          <View style={styles.completenessChipsRow}>
            <View style={[styles.completenessChip, hasGlucoseToday && styles.completenessChipDone]}>
              <Ionicons
                name={hasGlucoseToday ? "checkmark-circle" : "ellipse-outline"}
                size={13}
                color={hasGlucoseToday ? "#059669" : "#64748B"}
                style={{ marginRight: 4 }}
              />
              <Text style={[styles.completenessChipText, hasGlucoseToday && styles.completenessChipTextDone]} allowFontScaling>
                Glucose
              </Text>
            </View>
            <View style={[styles.completenessChip, hasMealToday && styles.completenessChipDone]}>
              <Ionicons
                name={hasMealToday ? "checkmark-circle" : "ellipse-outline"}
                size={13}
                color={hasMealToday ? "#059669" : "#64748B"}
                style={{ marginRight: 4 }}
              />
              <Text style={[styles.completenessChipText, hasMealToday && styles.completenessChipTextDone]} allowFontScaling>
                Meals
              </Text>
            </View>
            <View style={[styles.completenessChip, hasMedicationPlan && styles.completenessChipDone]}>
              <Ionicons
                name={hasMedicationPlan ? "checkmark-circle" : "ellipse-outline"}
                size={13}
                color={hasMedicationPlan ? "#059669" : "#64748B"}
                style={{ marginRight: 4 }}
              />
              <Text style={[styles.completenessChipText, hasMedicationPlan && styles.completenessChipTextDone]} allowFontScaling>
                Meds
              </Text>
            </View>
            <View style={[styles.completenessChip, hasActivityToday && styles.completenessChipDone]}>
              <Ionicons
                name={hasActivityToday ? "checkmark-circle" : "ellipse-outline"}
                size={13}
                color={hasActivityToday ? "#059669" : "#64748B"}
                style={{ marginRight: 4 }}
              />
              <Text style={[styles.completenessChipText, hasActivityToday && styles.completenessChipTextDone]} allowFontScaling>
                Activity
              </Text>
            </View>
          </View>
        </View>

        {/* WhatsApp Connection Card (shown when not connected) */}
        {whatsAppQuery.data?.status === "not_connected" ? (
          <WhatsAppHomeCard onConnect={onConnectWhatsApp ?? (() => {})} />
        ) : null}

        {/* Upcoming Regimen Banner */}
        {firstPlan ? (
          <View style={styles.upcomingBox}>
            <View style={styles.upcomingHeaderRow}>
              <View style={styles.upcomingBadge}>
                <Ionicons name="alarm-outline" size={12} color="#D97706" style={{ marginRight: 4 }} />
                <Text style={styles.upcomingKicker} allowFontScaling>
                  NEXT SCHEDULED
                </Text>
              </View>
              <Text style={styles.upcomingTime} allowFontScaling>
                Evening Regimen
              </Text>
            </View>
            <Text style={styles.upcomingTitle} allowFontScaling>
              {firstPlan.medication}
            </Text>
            <Text style={styles.upcomingSubtitle} allowFontScaling>
              {firstPlan.instruction || "Take with water as prescribed by clinician"}
            </Text>
            <TouchableOpacity
              style={styles.upcomingAction}
              onPress={onNavigateToMedications}
              accessibilityRole="button"
              accessibilityLabel={`View details for ${firstPlan.medication}`}
              activeOpacity={0.7}
            >
              <Text style={styles.upcomingActionText} allowFontScaling>
                View Medication Plan
              </Text>
              <Ionicons name="arrow-forward" size={14} color="#D97706" style={{ marginLeft: 4 }} />
            </TouchableOpacity>
          </View>
        ) : null}

        {/* Weekly Clinical Report Banner */}
        <View style={styles.reportBannerCard}>
          <View style={styles.reportBannerHeader}>
            <View style={styles.reportIconCircle}>
              <Ionicons name="bar-chart-outline" size={22} color="#0D9488" />
            </View>
            <View style={styles.reportBannerTextCol}>
              <Text style={styles.reportBannerKicker} allowFontScaling>
                WEEKLY INSIGHTS
              </Text>
              <Text style={styles.reportBannerTitle} allowFontScaling>
                Deterministic Glycemic Summary
              </Text>
              <Text style={styles.reportBannerSub} allowFontScaling>
                ADA/EASD glycemic metrics, time-in-range, and meal-glucose timeline correlations.
              </Text>
            </View>
          </View>
          <TouchableOpacity
            style={styles.reportBannerBtn}
            onPress={onNavigateToReports}
            accessibilityRole="button"
            accessibilityLabel="View Weekly Clinical Report"
            activeOpacity={0.8}
          >
            <Ionicons name="document-text-outline" size={15} color="#FFFFFF" style={{ marginRight: 6 }} />
            <Text style={styles.reportBannerBtnText} allowFontScaling>
              View Weekly Report
            </Text>
            <Ionicons name="arrow-forward" size={14} color="#FFFFFF" style={{ marginLeft: 4 }} />
          </TouchableOpacity>
        </View>

        {/* Recent Activity */}
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Text style={styles.sectionTitle} allowFontScaling>
              Recent Activity
            </Text>
            <TouchableOpacity
              style={styles.seeAllButton}
              onPress={onNavigateToTimeline}
              accessibilityRole="button"
              accessibilityLabel="View all care timeline activity"
              activeOpacity={0.7}
            >
              <Text style={styles.seeAllLink} allowFontScaling>
                See all
              </Text>
              <Ionicons name="arrow-forward" size={13} color="#0D9488" style={{ marginLeft: 3 }} />
            </TouchableOpacity>
          </View>

          {recentEvents.length === 0 ? (
            <View style={styles.emptyRecentBox}>
              <View style={styles.emptyRecentIconCircle}>
                <Ionicons name="calendar-outline" size={24} color="#94A3B8" />
              </View>
              <Text style={styles.emptyRecentTitle} allowFontScaling>
                No activity recorded yet today
              </Text>
              <Text style={styles.emptyRecentText} allowFontScaling>
                Readings, meals, and meds logged today will appear here chronologically.
              </Text>
              <TouchableOpacity
                style={styles.quickRecordButton}
                onPress={() => onNavigateToRecord()}
                accessibilityRole="button"
                accessibilityLabel="Record your first health entry"
                activeOpacity={0.8}
              >
                <Ionicons name="add" size={18} color="#FFFFFF" style={{ marginRight: 4 }} />
                <Text style={styles.quickRecordButtonText} allowFontScaling>
                  Record an Entry
                </Text>
              </TouchableOpacity>
            </View>
          ) : (
            recentEvents.map((event) => (
              <TimelineItemRow
                key={event.id}
                event={event}
                onPress={onNavigateToTimeline}
              />
            ))
          )}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  // Top Header (Airbnb/Blinkit/GymDeck inspired)
  topHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    paddingTop: 10,
    paddingBottom: 12,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F9",
  },
  headerLeftCol: {
    flex: 1,
    paddingRight: spacing.sm,
  },
  headerAppKickerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 2,
  },
  roleTag: {
    backgroundColor: "#EFF6FF",
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#DBEAFE",
  },
  roleTagText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#2563EB",
  },
  headerSignOutButton: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radii.pill,
    backgroundColor: "#FEE2E2",
  },
  headerSignOutText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#DC2626",
  },
  headerAppKicker: {
    fontSize: 11,
    fontWeight: "800",
    color: "#64748B",
    letterSpacing: 0.8,
  },
  headerMainTitle: {
    fontSize: 26,
    fontWeight: "900",
    color: "#0F172A",
    letterSpacing: -0.6,
    marginTop: 1,
  },
  facilitySelectorRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 2,
  },
  facilitySelectorText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#1E293B",
  },
  headerRightCol: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  headerStatusPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: radii.pill,
  },
  headerStatusText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#0D9488",
  },
  headerIconButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
    position: "relative",
  },
  headerBadge: {
    position: "absolute",
    top: -2,
    right: -2,
    backgroundColor: "#EF4444",
    minWidth: 16,
    height: 16,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 3,
  },
  headerBadgeText: {
    fontSize: 9,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  headerAvatarCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  headerAvatarInitial: {
    fontSize: 16,
    fontWeight: "900",
    color: "#0F172A",
  },

  // Main Scrollable Content
  content: {
    padding: spacing.md,
    gap: spacing.md + 2,
    paddingBottom: 110,
  },

  // Floating Search Bar (Airbnb style)
  searchBarContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    paddingHorizontal: 14,
    minHeight: 48,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  searchIcon: {
    marginRight: 10,
  },
  searchPlaceholderText: {
    flex: 1,
    fontSize: 13,
    fontWeight: "500",
    color: "#64748B",
  },
  searchRightBadge: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    alignItems: "center",
    justifyContent: "center",
  },

  // Horizontal Category Bar (Airbnb / Blinkit style)
  categoryBar: {
    flexDirection: "row",
    gap: 4,
    paddingVertical: 2,
  },
  categoryItem: {
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 6,
  },
  categoryLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: "#64748B",
    marginTop: 3,
  },
  categoryLabelActive: {
    color: "#0F172A",
    fontWeight: "800",
  },
  categoryIndicator: {
    width: 22,
    height: 3,
    borderRadius: 2,
    backgroundColor: "#0F172A",
    marginTop: 4,
  },

  // Care Command Section (Bento Grid Layout)
  commandSection: {
    gap: spacing.sm,
  },
  commandHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  commandTitleCol: {
    gap: 1,
  },
  commandKicker: {
    fontSize: 10,
    fontWeight: "700",
    color: "#0D9488",
    letterSpacing: 1.1,
  },
  commandTitleWithDot: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  commandTitle: {
    fontSize: 22,
    lineHeight: 28,
    fontWeight: "900",
    color: "#0F172A",
    letterSpacing: -0.4,
  },
  commandPulseDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#10B981",
  },
  viewTimelineBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radii.pill,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.03,
    shadowRadius: 4,
    elevation: 1,
  },
  viewTimelineText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#0F172A",
  },

  // Bento Grid Items
  bentoGrid: {
    flexDirection: "row",
    gap: 10,
  },
  bentoHeroCard: {
    flex: 1,
    minHeight: 204,
    backgroundColor: "#0D5C75",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.15)",
    padding: 14,
    justifyContent: "space-between",
    position: "relative",
    overflow: "hidden",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 3,
  },
  bentoHeroKicker: {
    fontSize: 11,
    fontWeight: "700",
    color: "rgba(255, 255, 255, 0.85)",
  },
  bentoHeroBadge: {
    backgroundColor: "#FEF08A",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radii.pill,
    alignSelf: "flex-start",
    marginTop: 8,
  },
  bentoHeroBadgeText: {
    fontSize: 13,
    fontWeight: "900",
    color: "#0F172A",
  },
  bentoHeroSubtext: {
    fontSize: 11,
    fontWeight: "600",
    color: "#E2E8F0",
    lineHeight: 16,
  },
  bentoHeroWatermark: {
    position: "absolute",
    right: 6,
    bottom: 6,
  },

  bentoRightCol: {
    flex: 1.25,
    gap: 10,
  },
  bentoRow: {
    flexDirection: "row",
    gap: 10,
  },
  bentoSmallCard: {
    flex: 1,
    borderRadius: 16,
    borderWidth: 1,
    padding: 10,
    justifyContent: "space-between",
    minHeight: 96,
  },

  // Amber Card
  bentoCardAmber: {
    backgroundColor: "#FFFBEB",
    borderColor: "#FEF3C7",
  },
  bentoSmallKickerAmber: {
    fontSize: 10,
    fontWeight: "700",
    color: "#78350F",
  },
  bentoSmallValAmber: {
    fontSize: 17,
    fontWeight: "900",
    color: "#B45309",
  },
  bentoSmallBadgeAmber: {
    backgroundColor: "#FEF3C7",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.pill,
    alignSelf: "flex-start",
  },
  bentoSmallBadgeTextAmber: {
    fontSize: 9,
    fontWeight: "700",
    color: "#78350F",
  },

  // Rose Card
  bentoCardRose: {
    backgroundColor: "#FFF1F2",
    borderColor: "#FFE4E6",
  },
  bentoSmallKickerRose: {
    fontSize: 10,
    fontWeight: "700",
    color: "#9F1239",
  },
  bentoSmallValRose: {
    fontSize: 17,
    fontWeight: "900",
    color: "#E11D48",
  },
  bentoSmallBadgeRose: {
    backgroundColor: "#FFE4E6",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.pill,
    alignSelf: "flex-start",
  },
  bentoSmallBadgeTextRose: {
    fontSize: 9,
    fontWeight: "700",
    color: "#9F1239",
  },

  // Emerald Card
  bentoCardEmerald: {
    backgroundColor: "#ECFDF5",
    borderColor: "#D1FAE5",
  },
  bentoSmallKickerEmerald: {
    fontSize: 10,
    fontWeight: "700",
    color: "#065F46",
  },
  bentoSmallValEmerald: {
    fontSize: 17,
    fontWeight: "900",
    color: "#059669",
  },
  bentoSmallBadgeEmerald: {
    backgroundColor: "#D1FAE5",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.pill,
    alignSelf: "flex-start",
  },
  bentoSmallBadgeTextEmerald: {
    fontSize: 9,
    fontWeight: "700",
    color: "#065F46",
  },

  // Purple Card
  bentoCardPurple: {
    backgroundColor: "#F5F3FF",
    borderColor: "#EDE9FE",
  },
  bentoSmallKickerPurple: {
    fontSize: 10,
    fontWeight: "700",
    color: "#5B21B6",
  },
  bentoSmallValPurple: {
    fontSize: 17,
    fontWeight: "900",
    color: "#7C3AED",
  },
  bentoSmallBadgePurple: {
    backgroundColor: "#EDE9FE",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.pill,
    alignSelf: "flex-start",
  },
  bentoSmallBadgeTextPurple: {
    fontSize: 9,
    fontWeight: "700",
    color: "#5B21B6",
  },

  // Quick Record Row
  quickRecordRow: {
    flexDirection: "row",
    gap: spacing.xs,
    justifyContent: "space-between",
  },
  quickActionBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    paddingVertical: 10,
    paddingHorizontal: 4,
    borderRadius: 16,
    borderWidth: 1,
    minHeight: touchTarget.min,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.03,
    shadowRadius: 6,
    elevation: 1,
  },
  quickActionGlucose: {
    backgroundColor: "#FEF2F2",
    borderColor: "#FEE2E2",
  },
  quickActionMeal: {
    backgroundColor: "#FFFBEB",
    borderColor: "#FEF3C7",
  },
  quickActionMeds: {
    backgroundColor: "#EFF6FF",
    borderColor: "#DBEAFE",
  },
  quickActionActivity: {
    backgroundColor: "#ECFDF5",
    borderColor: "#D1FAE5",
  },
  quickActionText: {
    fontSize: 12,
    fontWeight: "700",
  },
  quickActionTextGlucose: {
    color: "#DC2626",
  },
  quickActionTextMeal: {
    color: "#D97706",
  },
  quickActionTextMeds: {
    color: "#2563EB",
  },
  quickActionTextActivity: {
    color: "#059669",
  },

  // Data Completeness Card
  completenessCard: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
    gap: spacing.sm,
  },
  completenessHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  completenessKicker: {
    fontSize: 10,
    fontWeight: "700",
    color: "#0D9488",
    letterSpacing: 0.8,
  },
  completenessTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
    marginTop: 2,
  },
  completenessBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  completenessBadgeGood: {
    backgroundColor: "#ECFDF5",
  },
  completenessBadgeWarn: {
    backgroundColor: "#FEF3C7",
  },
  completenessBadgeText: {
    fontSize: 10,
    fontWeight: "700",
  },
  completenessBadgeTextGood: {
    color: "#059669",
  },
  completenessBadgeTextWarn: {
    color: "#D97706",
  },
  progressBarBackground: {
    height: 8,
    backgroundColor: "#EEF2F6",
    borderRadius: radii.pill,
    overflow: "hidden",
  },
  progressBarFill: {
    height: "100%",
    backgroundColor: "#10B981",
    borderRadius: radii.pill,
  },
  completenessChipsRow: {
    flexDirection: "row",
    gap: spacing.xs,
    flexWrap: "wrap",
  },
  completenessChip: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F8FAFC",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#EEF2F6",
  },
  completenessChipDone: {
    backgroundColor: "#ECFDF5",
    borderColor: "#D1FAE5",
  },
  completenessChipText: {
    fontSize: 11,
    fontWeight: "500",
    color: "#64748B",
  },
  completenessChipTextDone: {
    color: "#065F46",
    fontWeight: "700",
  },

  // Upcoming Reminder Box
  upcomingBox: {
    backgroundColor: "#FFFBEB",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#FEF3C7",
    padding: spacing.md,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
    gap: 4,
  },
  upcomingHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  upcomingBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FEF3C7",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  upcomingKicker: {
    fontSize: 10,
    fontWeight: "700",
    color: "#D97706",
    letterSpacing: 0.8,
  },
  upcomingTime: {
    fontSize: 12,
    fontWeight: "600",
    color: "#78350F",
  },
  upcomingTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
  },
  upcomingSubtitle: {
    fontSize: 13,
    color: "#64748B",
    marginTop: 2,
    lineHeight: 18,
  },
  upcomingAction: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    marginTop: spacing.xs,
    paddingVertical: 4,
  },
  upcomingActionText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#D97706",
  },

  // Weekly Report Banner
  reportBannerCard: {
    backgroundColor: "#F0FDFA",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#CCFBF1",
    padding: spacing.md,
    gap: spacing.sm,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  reportBannerHeader: {
    flexDirection: "row",
    gap: spacing.sm,
    alignItems: "flex-start",
  },
  reportIconCircle: {
    width: 42,
    height: 42,
    borderRadius: radii.pill,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "#CCFBF1",
  },
  reportBannerTextCol: {
    flex: 1,
  },
  reportBannerKicker: {
    fontSize: 10,
    fontWeight: "700",
    color: "#0D9488",
    letterSpacing: 0.8,
  },
  reportBannerTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
    marginTop: 2,
  },
  reportBannerSub: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 2,
    lineHeight: 17,
  },
  reportBannerBtn: {
    flexDirection: "row",
    backgroundColor: "#0D9488",
    borderRadius: radii.pill,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.md,
  },
  reportBannerBtnText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "700",
  },

  // Recent Activity Section
  section: {
    gap: spacing.sm,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#0F172A",
    letterSpacing: -0.2,
  },
  seeAllButton: {
    flexDirection: "row",
    alignItems: "center",
  },
  seeAllLink: {
    fontSize: 13,
    fontWeight: "600",
    color: "#0D9488",
  },
  emptyRecentBox: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.lg,
    alignItems: "center",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  emptyRecentIconCircle: {
    width: 48,
    height: 48,
    borderRadius: radii.pill,
    backgroundColor: "#F8FAFC",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.xs,
  },
  emptyRecentTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
    textAlign: "center",
  },
  emptyRecentText: {
    fontSize: 13,
    color: "#64748B",
    marginTop: 4,
    marginBottom: spacing.md,
    textAlign: "center",
    lineHeight: 18,
  },
  quickRecordButton: {
    flexDirection: "row",
    backgroundColor: "#0D9488",
    borderRadius: radii.pill,
    minHeight: touchTarget.min,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    justifyContent: "center",
  },
  quickRecordButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
});
