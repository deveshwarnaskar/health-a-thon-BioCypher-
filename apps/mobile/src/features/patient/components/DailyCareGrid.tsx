import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, typography } from "../../../theming/tokens";

export type DailyCareItem = {
  id: string;
  category: "glucose" | "meals" | "medication" | "tasks";
  title: string;
  value: string;
  subtext: string;
  icon?: string;
  statusBadge?: string;
  onPress: () => void;
};

export type DailyCareGridProps = {
  items: DailyCareItem[];
};

function cardBackground(category: DailyCareItem["category"]) {
  switch (category) {
    case "glucose":
      return colors.tileYellow;
    case "meals":
      return colors.tileGreen;
    case "medication":
      return colors.tileLavender;
    case "tasks":
      return colors.tilePink;
  }
}

function CategoryIcon({ category }: { category: DailyCareItem["category"] }) {
  switch (category) {
    case "glucose":
      return <Ionicons name="water-outline" size={22} color="#92400E" />;
    case "meals":
      return <Ionicons name="restaurant-outline" size={22} color="#065F46" />;
    case "medication":
      return <Ionicons name="medkit-outline" size={22} color="#3730A3" />;
    case "tasks":
      return <Ionicons name="checkbox-outline" size={22} color="#9D174D" />;
  }
}

export function DailyCareGrid({ items }: DailyCareGridProps) {
  return (
    <View style={styles.grid}>
      {items.map((item) => (
        <TouchableOpacity
          key={item.id}
          style={[styles.card, { backgroundColor: cardBackground(item.category) }]}
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
            <CategoryIcon category={item.category} />
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
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    padding: spacing.md,
    minHeight: 124,
    justifyContent: "space-between",
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.07,
    shadowRadius: 16,
    elevation: 2,
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
    backgroundColor: "#FFFFFFAA",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  badgeText: {
    fontSize: 10,
    color: colors.primaryInk,
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
