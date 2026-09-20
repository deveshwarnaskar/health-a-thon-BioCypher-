import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
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
            <Text style={styles.backIcon} allowFontScaling>
              ←
            </Text>
          </TouchableOpacity>
        ) : null}

        <View style={styles.textContainer}>
          {showGreeting ? (
            <>
              <Text style={styles.greeting} allowFontScaling numberOfLines={1}>
                {greeting}, {patientName || "Friend"}
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
                <Text style={styles.subtitle} allowFontScaling>
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
                {role}
              </Text>
            </View>
          ) : null}

          {onSignOut ? (
            <TouchableOpacity
              style={styles.actionButton}
              onPress={onSignOut}
              accessibilityRole="button"
              accessibilityLabel="Sign out"
              accessibilityHint="Signs out of THALI"
              activeOpacity={0.7}
            >
              <Text style={styles.signOutIconText} allowFontScaling>
                Sign out
              </Text>
            </TouchableOpacity>
          ) : null}

          {onPressAssist ? (
            <TouchableOpacity
              style={styles.actionButton}
              onPress={onPressAssist}
              accessibilityRole="button"
              accessibilityLabel="THALI Assist AI care guide"
              accessibilityHint="Opens THALI Assist for help with your care information"
              activeOpacity={0.7}
            >
              <Text style={styles.assistIcon} allowFontScaling>
                ✦
              </Text>
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
              <Text style={styles.bellIcon} allowFontScaling>
                🔔
              </Text>
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
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  contentRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  backButton: {
    minWidth: touchTarget.min,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.xs,
  },
  backIcon: {
    fontSize: 24,
    color: colors.primary,
    fontWeight: "bold",
  },
  textContainer: {
    flex: 1,
    justifyContent: "center",
  },
  greeting: {
    fontSize: typography.fontSize.title,
    lineHeight: typography.lineHeight.title,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  dateText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: 2,
    fontWeight: typography.weight.medium,
  },
  title: {
    fontSize: typography.fontSize.title,
    lineHeight: typography.lineHeight.title,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  actionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  actionButton: {
    minWidth: touchTarget.min,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
  },
  bellIcon: {
    fontSize: 20,
    color: colors.textPrimary,
  },
  assistIcon: {
    fontSize: 20,
    color: colors.primary,
    fontWeight: "bold",
  },
  unreadBadge: {
    position: "absolute",
    top: 6,
    right: 6,
    backgroundColor: colors.critical,
    borderRadius: radii.pill,
    minWidth: 16,
    height: 16,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 3,
  },
  unreadBadgeText: {
    color: colors.textOnPrimary,
    fontSize: 10,
    fontWeight: typography.weight.bold,
    lineHeight: 12,
  },
  roleTag: {
    backgroundColor: "#F0F7F9",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radii.sm,
    marginRight: 2,
  },
  roleTagText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.primary,
  },
  signOutIconText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.semibold,
    color: colors.textSecondary,
  },
});
