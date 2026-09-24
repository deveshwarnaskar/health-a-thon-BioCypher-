import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, touchTarget, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";

export type DoctorScreenHeaderProps = {
  doctorName?: string | null;
  facilityId?: string | null;
  title?: string;
  subtitle?: string;
  showGreeting?: boolean;
  pendingReviewCount?: number;
  onPressReviews?: () => void;
  onSignOut?: () => void;
  onBack?: () => void;
};

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good Morning";
  if (hour < 17) return "Good Afternoon";
  return "Good Evening";
}

export function DoctorScreenHeader({
  doctorName,
  facilityId = "Facility 1",
  title,
  subtitle,
  showGreeting = false,
  pendingReviewCount = 0,
  onPressReviews,
  onSignOut,
  onBack,
}: DoctorScreenHeaderProps) {
  const greeting = getGreeting();
  const displayName = doctorName || "Clinician";
  const initial = displayName.replace(/^Dr\.\s*/i, "").charAt(0).toUpperCase() || "D";

  return (
    <View style={styles.header} accessibilityRole="header">
      <View style={styles.contentRow}>
        {onBack ? (
          <TouchableOpacity
            style={styles.circleIconButton}
            onPress={onBack}
            accessibilityRole="button"
            accessibilityLabel="Go back"
            activeOpacity={0.7}
          >
            <Ionicons name="arrow-back" size={20} color={doctorPalette.ink} />
          </TouchableOpacity>
        ) : null}

        <View style={styles.textContainer}>
          {showGreeting ? (
            <>
              <Text style={styles.greetingKicker} allowFontScaling numberOfLines={1}>
                {greeting}
              </Text>
              <View style={styles.nameRow}>
                <Text style={styles.greetingName} allowFontScaling numberOfLines={1}>
                  Dr. {displayName}!
                </Text>
                <Ionicons name="checkmark-circle" size={17} color={doctorPalette.primary} />
              </View>
            </>
          ) : (
            <>
              <Text style={styles.title} allowFontScaling numberOfLines={1}>
                {title}
              </Text>
              {subtitle ? (
                <Text style={styles.subtitle} allowFontScaling numberOfLines={1}>
                  {subtitle}
                </Text>
              ) : null}
            </>
          )}
        </View>

        <View style={styles.actionRow}>
          {/* AI Reviews / Notification Bell Button */}
          {onPressReviews ? (
            <TouchableOpacity
              style={styles.circleIconButton}
              onPress={onPressReviews}
              accessibilityRole="button"
              accessibilityLabel={`AI notifications, ${pendingReviewCount} pending`}
              activeOpacity={0.7}
            >
              <Ionicons
                name={pendingReviewCount > 0 ? "notifications" : "notifications-outline"}
                size={20}
                color={pendingReviewCount > 0 ? doctorPalette.ink : doctorPalette.muted}
              />
              {pendingReviewCount > 0 ? (
                <View style={styles.badgeIndicator}>
                  <Text style={styles.badgeText} allowFontScaling>
                    {pendingReviewCount > 9 ? "9+" : pendingReviewCount}
                  </Text>
                </View>
              ) : null}
            </TouchableOpacity>
          ) : null}

          {/* Doctor Avatar Thumbnail */}
          <TouchableOpacity
            style={styles.avatarThumbnail}
            onPress={onSignOut}
            accessibilityRole="button"
            accessibilityLabel="Doctor account profile and sign-out"
            activeOpacity={0.8}
          >
            <Text style={styles.avatarInitial} allowFontScaling>
              {initial}
            </Text>
            <View style={styles.onlineDot} />
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    backgroundColor: doctorPalette.appBackground,
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 14,
  },
  contentRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  textContainer: {
    flex: 1,
    justifyContent: "center",
  },
  greetingKicker: {
    fontSize: 13,
    fontWeight: "500",
    color: doctorPalette.muted,
    letterSpacing: 0.2,
  },
  nameRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 1,
  },
  greetingName: {
    fontSize: 23,
    lineHeight: 28,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.3,
  },
  title: {
    fontSize: 22,
    lineHeight: 28,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.2,
  },
  subtitle: {
    fontSize: 13,
    color: doctorPalette.muted,
    marginTop: 2,
  },
  actionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  circleIconButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: doctorPalette.surface,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    alignItems: "center",
    justifyContent: "center",
    ...doctorSoftShadow,
  },
  badgeIndicator: {
    position: "absolute",
    top: -2,
    right: -2,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: "#EF4444",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 4,
    borderWidth: 2,
    borderColor: doctorPalette.surface,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#FFFFFF",
    lineHeight: 12,
  },
  avatarThumbnail: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: doctorPalette.surfaceLime,
    borderWidth: 2,
    borderColor: doctorPalette.surface,
    alignItems: "center",
    justifyContent: "center",
    ...doctorSoftShadow,
  },
  avatarInitial: {
    fontSize: 18,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  onlineDot: {
    position: "absolute",
    bottom: 0,
    right: 0,
    width: 11,
    height: 11,
    borderRadius: 6,
    backgroundColor: "#10B981",
    borderWidth: 2,
    borderColor: doctorPalette.surface,
  },
});
