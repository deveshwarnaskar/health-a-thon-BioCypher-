import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { colors, radii, spacing, typography } from "../../../theming/tokens";

export type DailyCareItem = {
  id: string;
  category: "glucose" | "meals" | "medication" | "tasks";
  title: string;
  value: string;
  subtext: string;
  icon: string;
  statusBadge?: string;
  onPress: () => void;
};

export type DailyCareGridProps = {
  items: DailyCareItem[];
};

export function DailyCareGrid({ items }: DailyCareGridProps) {
  return (
    <View style={styles.grid}>
      {items.map((item) => (
        <TouchableOpacity
          key={item.id}
          style={styles.card}
          onPress={item.onPress}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel={
            item.category === "meals"
              ? "Food (placeholder)"
              : `${item.title}: ${item.value}, ${item.subtext}`
          }
        >
          <View style={styles.topRow}>
            <Text style={styles.icon} allowFontScaling>
              {item.icon}
            </Text>
            {item.statusBadge ? (
              <View style={styles.badge}>
                <Text style={styles.badgeText} allowFontScaling>
                  {item.statusBadge}
                </Text>
              </View>
            ) : null}
          </View>

          <Text style={styles.value} allowFontScaling numberOfLines={1}>
            {item.value}
          </Text>

          <Text style={styles.title} allowFontScaling numberOfLines={1}>
            {item.title}
          </Text>

          <Text style={styles.subtext} allowFontScaling numberOfLines={1}>
            {item.subtext}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  card: {
    flex: 1,
    minWidth: "46%",
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    minHeight: 110,
    justifyContent: "space-between",
  },
  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xxs,
  },
  icon: {
    fontSize: 22,
  },
  badge: {
    backgroundColor: "#EBF5FB",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.sm,
  },
  badgeText: {
    fontSize: 10,
    color: colors.info,
    fontWeight: typography.weight.bold,
  },
  value: {
    fontSize: typography.fontSize.title,
    lineHeight: typography.lineHeight.title,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  title: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.semibold,
    color: colors.textSecondary,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 2,
  },
  subtext: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
});
