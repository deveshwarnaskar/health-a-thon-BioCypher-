import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";

export type PatientScreenHeaderProps = {
  patientName?: string;
  title?: string;
  subtitle?: string;
  showGreeting?: boolean;
  role?: string;
  unreadNotificationsCount?: number;
  onPressNotifications?: () => void;
  onPressAssist?: () => void;
  onSignOut?: () => void;
  onBack?: () => void;
};

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function getFormattedDate(): string {
  const options: Intl.DateTimeFormatOptions = {
    weekday: "long",
    day: "numeric",
    month: "long",
  };
  return new Intl.DateTimeFormat("en-IN", options).format(new Date());
}

export function PatientScreenHeader({
  patientName,
  title,
  subtitle,
  showGreeting = false,
  role,
  unreadNotificationsCount = 0,
  onPressNotifications,
  onPressAssist,
  onSignOut,
  onBack,
}: PatientScreenHeaderProps) {
  const greeting = getGreeting();
  const dateStr = getFormattedDate();

  return (
    <View style={styles.header} accessibilityRole="header">
      <View style={styles.contentRow}>
        {onBack ? (
          <TouchableOpacity
            style={styles.backButton}
            onPress={onBack}
            accessibilityRole="button"
            accessibilityLabel="Go back"
            activeOpacity={0.7}
          >
            <Ionicons name="arrow-back" size={20} color={colors.textPrimary} />
          </TouchableOpacity>
        ) : null}

        <View style={styles.textContainer}>
          {showGreeting ? (
            <>
              <View style={styles.brandBadgeRow}>
                <View style={styles.brandDot} />
                <Text style={styles.appLabel} allowFontScaling numberOfLines={1}>
                  THALI CARE
                </Text>
              </View>
              <Text style={styles.greeting} allowFontScaling numberOfLines={1}>
                {greeting},{" "}
                {patientName && !/^[0-9a-f]{8}-[0-9a-f]{4}/i.test(patientName)
                  ? patientName
                  : "Friend"}
              </Text>
              <Text style={styles.dateText} allowFontScaling>
                {dateStr}
              </Text>
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
          {role ? (
            <View style={styles.roleTag}>
              <Text style={styles.roleTagText} allowFontScaling>
                {role.toUpperCase()}
              </Text>
            </View>
          ) : null}

          {onSignOut ? (
            <TouchableOpacity
              style={[styles.actionButton, styles.signOutButton]}
              onPress={onSignOut}
              accessibilityRole="button"
              accessibilityLabel="Sign out"
              accessibilityHint="Signs out of THALI"
              activeOpacity={0.7}
            >
              <Ionicons name="log-out-outline" size={15} color="#DC2626" style={{ marginRight: 4 }} />
              <Text style={styles.signOutIconText} allowFontScaling>
                Sign out
              </Text>
            </TouchableOpacity>
          ) : null}

          {onPressAssist ? (
            <TouchableOpacity
              style={[styles.actionButton, styles.assistButton]}
              onPress={onPressAssist}
              accessibilityRole="button"
              accessibilityLabel="THALI Assist AI care guide"
              accessibilityHint="Opens THALI Assist for help with your care information"
              activeOpacity={0.7}
            >
              <Ionicons name="sparkles" size={18} color="#0D9488" />
            </TouchableOpacity>
          ) : null}

          {onPressNotifications ? (
            <TouchableOpacity
              style={styles.actionButton}
              onPress={onPressNotifications}
              accessibilityRole="button"
              accessibilityLabel={`Notifications, ${unreadNotificationsCount} unread`}
              activeOpacity={0.7}
            >
              <Ionicons name="notifications-outline" size={20} color={colors.textPrimary} />
              {unreadNotificationsCount > 0 ? (
                <View style={styles.unreadBadge} accessibilityElementsHidden>
                  <Text style={styles.unreadBadgeText} allowFontScaling>
                    {unreadNotificationsCount > 9 ? "9+" : unreadNotificationsCount}
                  </Text>
                </View>
              ) : null}
            </TouchableOpacity>
          ) : null}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    backgroundColor: colors.background,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md + 4,
    paddingBottom: spacing.sm + 2,
  },
  contentRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  backButton: {
    width: 44,
    height: 44,
    minWidth: touchTarget.min,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 2,
  },
  textContainer: {
    flex: 1,
    justifyContent: "center",
  },
  brandBadgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 2,
  },
  brandDot: {
    width: 6,
    height: 6,
    borderRadius: radii.pill,
    backgroundColor: "#0D9488",
  },
  appLabel: {
    fontSize: 11,
    fontWeight: typography.weight.bold,
    color: "#0D9488",
    letterSpacing: 1,
  },
  greeting: {
    fontSize: 22,
    lineHeight: 28,
    fontWeight: typography.weight.bold,
    color: "#0F172A",
    letterSpacing: -0.3,
  },
  dateText: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 2,
    fontWeight: typography.weight.medium,
  },
  title: {
    fontSize: 22,
    lineHeight: 28,
    fontWeight: typography.weight.bold,
    color: "#0F172A",
    letterSpacing: -0.3,
  },
  subtitle: {
    fontSize: 13,
    color: "#64748B",
    marginTop: 2,
    fontWeight: typography.weight.regular,
  },
  actionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    justifyContent: "flex-end",
  },
  actionButton: {
    width: 44,
    height: 44,
    minWidth: touchTarget.min,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 2,
  },
  assistButton: {
    backgroundColor: "#F0FDFA",
    borderColor: "#CCFBF1",
  },
  signOutButton: {
    width: "auto",
    paddingHorizontal: 12,
    minWidth: 84,
    flexDirection: "row",
    borderColor: "#FECACA",
    backgroundColor: "#FEF2F2",
  },
  unreadBadge: {
    position: "absolute",
    top: 4,
    right: 4,
    backgroundColor: "#EF4444",
    borderRadius: radii.pill,
    minWidth: 18,
    height: 18,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 4,
    borderWidth: 1.5,
    borderColor: "#FFFFFF",
  },
  unreadBadgeText: {
    color: "#FFFFFF",
    fontSize: 10,
    fontWeight: typography.weight.bold,
    lineHeight: 12,
  },
  roleTag: {
    backgroundColor: "#F0FDFA",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#CCFBF1",
  },
  roleTagText: {
    fontSize: 10,
    fontWeight: typography.weight.bold,
    color: "#0D9488",
    letterSpacing: 0.5,
  },
  signOutIconText: {
    fontSize: 12,
    fontWeight: typography.weight.semibold,
    color: "#DC2626",
  },
});
