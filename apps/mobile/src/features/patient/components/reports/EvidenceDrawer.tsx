import React from "react";
import {
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../../theming/tokens";
import type { EvidenceItem } from "../../types";

export type EvidenceDrawerProps = {
  visible: boolean;
  onClose: () => void;
  title: string;
  items: EvidenceItem[];
  basisText?: string;
};

export function EvidenceDrawer({
  visible,
  onClose,
  title,
  items,
  basisText,
}: EvidenceDrawerProps) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.container}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerTextCol}>
              <Text style={styles.kicker} allowFontScaling>SUPPORTING RECORDS</Text>
              <Text style={styles.title} allowFontScaling numberOfLines={2}>
                {title}
              </Text>
            </View>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn} accessibilityLabel="Close evidence drawer">
              <Ionicons name="close" size={22} color="#64748B" />
            </TouchableOpacity>
          </View>

          {basisText ? (
            <View style={styles.basisBox}>
              <Ionicons name="git-branch-outline" size={16} color="#0284C7" />
              <Text style={styles.basisText} allowFontScaling>{basisText}</Text>
            </View>
          ) : null}

          <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
            <Text style={styles.sectionHeader} allowFontScaling>
              SUPPORTING OBSERVATION RECORDS ({items.length})
            </Text>

            {items.length === 0 ? (
              <View style={styles.emptyCard}>
                <Ionicons name="document-text-outline" size={28} color="#94A3B8" />
                <Text style={styles.emptyText} allowFontScaling>
                  No individual linked observations in this window.
                </Text>
              </View>
            ) : (
              items.map((item) => (
                <View key={item.id} style={styles.itemCard}>
                  <View style={styles.itemTopRow}>
                    <View style={styles.badge}>
                      <Text style={styles.badgeText} allowFontScaling>
                        {item.type.toUpperCase()}
                      </Text>
                    </View>
                    <Text style={styles.itemDate} allowFontScaling>
                      {item.date} · {item.time}
                    </Text>
                  </View>
                  <Text style={styles.itemLabel} allowFontScaling>{item.label}</Text>
                  <Text style={styles.itemValue} allowFontScaling>{item.value}</Text>
                  {item.context ? (
                    <Text style={styles.itemContext} allowFontScaling>{item.context}</Text>
                  ) : null}
                </View>
              ))
            )}

            <Text style={styles.footerNote} allowFontScaling>
              Evidence is derived from confirmed patient observations and validated against ICMR-NIN glycemic parameters.
            </Text>
          </ScrollView>

          <TouchableOpacity style={styles.closeAction} onPress={onClose}>
            <Text style={styles.closeActionText} allowFontScaling>Done</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.6)",
    justifyContent: "flex-end",
  },
  container: {
    backgroundColor: colors.background,
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
    maxHeight: "85%",
    paddingBottom: spacing.xl,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F9",
  },
  headerTextCol: {
    flex: 1,
    paddingRight: spacing.sm,
  },
  kicker: {
    ...typography.caption,
    color: "#64748B",
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  title: {
    ...typography.titleMedium,
    color: colors.textPrimary,
    fontWeight: "800",
    marginTop: 2,
  },
  closeBtn: {
    width: touchTarget.min,
    height: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
  },
  basisBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: "#F0F9FF",
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "#BAE6FD",
  },
  basisText: {
    ...typography.caption,
    color: "#0369A1",
    fontWeight: "600",
    flex: 1,
  },
  body: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
  },
  sectionHeader: {
    ...typography.caption,
    color: "#475569",
    fontWeight: "700",
    letterSpacing: 0.5,
    marginBottom: spacing.sm,
  },
  itemCard: {
    backgroundColor: "#F8FAFC",
    borderRadius: radii.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    marginBottom: spacing.sm,
  },
  itemTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  badge: {
    backgroundColor: "#EEF2FF",
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    borderRadius: 4,
  },
  badgeText: {
    ...typography.caption,
    color: "#4F46E5",
    fontWeight: "700",
    fontSize: 10,
  },
  itemDate: {
    ...typography.caption,
    color: "#64748B",
  },
  itemLabel: {
    ...typography.bodyMedium,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  itemValue: {
    ...typography.caption,
    color: "#475569",
    marginTop: 2,
  },
  itemContext: {
    ...typography.caption,
    color: "#94A3B8",
    fontStyle: "italic",
    marginTop: 2,
  },
  emptyCard: {
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl,
    backgroundColor: "#F8FAFC",
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  emptyText: {
    ...typography.caption,
    color: "#64748B",
    marginTop: spacing.xs,
    textAlign: "center",
  },
  footerNote: {
    ...typography.caption,
    color: "#94A3B8",
    textAlign: "center",
    marginVertical: spacing.md,
    fontStyle: "italic",
  },
  closeAction: {
    marginHorizontal: spacing.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: radii.md,
    paddingVertical: spacing.sm,
    alignItems: "center",
  },
  closeActionText: {
    ...typography.bodyMedium,
    color: colors.textPrimary,
    fontWeight: "700",
  },
});
