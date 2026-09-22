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

function CategoryIcon({ category }: { category: DailyCareItem["category"] }) {
  switch (category) {
    case "glucose":
      return (
        <View style={[styles.iconContainer, styles.iconContainerRed]}>
          <Ionicons name="water" size={18} color="#DC2626" />
        </View>
      );
    case "meals":
      return (
        <View style={[styles.iconContainer, styles.iconContainerAmber]}>
          <Ionicons name="restaurant" size={18} color="#D97706" />
        </View>
      );
    case "medication":
      return (
        <View style={[styles.iconContainer, styles.iconContainerBlue]}>
          <Ionicons name="medkit" size={18} color="#2563EB" />
        </View>
      );
    case "tasks":
      return (
        <View style={[styles.iconContainer, styles.iconContainerPurple]}>
          <Ionicons name="checkbox" size={18} color="#7C3AED" />
        </View>
      );
  }
}

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
            <CategoryIcon category={item.category} />
            {item.statusBadge ? (
              <View style={styles.badge}>
                <Text style={styles.badgeText} allowFontScaling numberOfLines={1}>
                  {item.statusBadge}
                </Text>
              </View>
            ) : null}
          </View>

          <View style={styles.contentCol}>
            <Text style={styles.value} allowFontScaling numberOfLines={1}>
              {item.value}
            </Text>

            <Text style={styles.title} allowFontScaling numberOfLines={1}>
              {item.title}
            </Text>

            <Text style={styles.subtext} allowFontScaling numberOfLines={1}>
              {item.subtext}
            </Text>
          </View>
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
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    backgroundColor: colors.surface,
    padding: spacing.md,
    minHeight: 136,
    justifyContent: "space-between",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  iconContainer: {
    width: 38,
    height: 38,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  iconContainerRed: {
    backgroundColor: "#FEF2F2",
  },
  iconContainerAmber: {
    backgroundColor: "#FFFBEB",
  },
  iconContainerBlue: {
    backgroundColor: "#EFF6FF",
  },
  iconContainerPurple: {
    backgroundColor: "#F5F3FF",
  },
  badge: {
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  badgeText: {
    fontSize: 10,
    color: "#475569",
    fontWeight: "700",
  },
  contentCol: {
    marginTop: "auto",
  },
  value: {
    fontSize: 18,
    lineHeight: 24,
    fontWeight: "700",
    color: "#0F172A",
    letterSpacing: -0.2,
  },
  title: {
    fontSize: 11,
    fontWeight: "700",
    color: "#64748B",
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginTop: 3,
  },
  subtext: {
    fontSize: 12,
    color: "#94A3B8",
    marginTop: 2,
  },
});
