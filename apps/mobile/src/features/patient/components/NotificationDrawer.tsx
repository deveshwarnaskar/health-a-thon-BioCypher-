import React from "react";
import {
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import type { NotificationResponse } from "../../../services/schemas/notifications";

export type NotificationDrawerProps = {
  visible: boolean;
  onClose: () => void;
  notifications: NotificationResponse[];
  onSelectNotification?: (notification: NotificationResponse) => void;
};

type NotificationMeta = {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
  bg: string;
};

function getNotificationMeta(type: string): NotificationMeta {
  switch (type) {
    case "reminder":
      return { label: "Reminder", icon: "time-outline", color: "#0D9488", bg: "#F0FDFA" };
    case "alert":
      return { label: "Health Alert", icon: "warning-outline", color: "#DC2626", bg: "#FEF2F2" };
    case "task_assigned":
      return { label: "Task Update", icon: "checkbox-outline", color: "#2563EB", bg: "#EFF6FF" };
    case "care_update":
      return { label: "Care Summary", icon: "document-text-outline", color: "#7C3AED", bg: "#F5F3FF" };
    case "clinical_communication":
      return { label: "Clinic Message", icon: "chatbubble-ellipses-outline", color: "#0284C7", bg: "#F0F9FF" };
    default:
      return { label: "Update", icon: "notifications-outline", color: "#64748B", bg: "#F1F5F9" };
  }
}

export function NotificationDrawer({
  visible,
  onClose,
  notifications,
  onSelectNotification,
}: NotificationDrawerProps) {
  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.container}>
        {/* Modern Header */}
        <View style={styles.header}>
          <View>
            <View style={styles.kickerRow}>
              <View style={styles.kickerDot} />
              <Text style={styles.kicker} allowFontScaling>
                CLINICAL ALERTS & REMINDERS
              </Text>
            </View>
            <Text style={styles.title} allowFontScaling>
              Notifications
            </Text>
          </View>
          <TouchableOpacity
            style={styles.closeButton}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Close notifications"
            activeOpacity={0.7}
          >
            <Ionicons name="close" size={20} color="#0F172A" />
          </TouchableOpacity>
        </View>

        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          {notifications.length === 0 ? (
            <View style={styles.emptyContainer}>
              <View style={styles.emptyIconCircle}>
                <Ionicons name="notifications-off-outline" size={34} color="#0D9488" />
              </View>
              <Text style={styles.emptyTitle} allowFontScaling>
                {"You're all caught up"}
              </Text>
              <Text style={styles.emptySubtitle} allowFontScaling>
                New medication reminders, task schedules, and clinic updates will appear here.
              </Text>
            </View>
          ) : (
            notifications.map((n) => {
              const meta = getNotificationMeta(n.notification_type);
              const message =
                n.template_params?.message ||
                n.template_params?.reminder ||
                n.template_name.replace(/_/g, " ");

              const timeStr = n.created_at
                ? new Date(n.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                : "";

              return (
                <TouchableOpacity
                  key={n.id}
                  style={styles.itemCard}
                  onPress={() => onSelectNotification?.(n)}
                  activeOpacity={0.7}
                  accessibilityRole="button"
                  accessibilityLabel={`${meta.label}: ${message}`}
                >
                  <View style={styles.itemTopRow}>
                    <View style={styles.typeRow}>
                      <View style={[styles.typeIconBox, { backgroundColor: meta.bg }]}>
                        <Ionicons name={meta.icon} size={15} color={meta.color} />
                      </View>
                      <View style={[styles.typeBadge, { backgroundColor: meta.bg }]}>
                        <Text style={[styles.typeBadgeText, { color: meta.color }]} allowFontScaling>
                          {meta.label}
                        </Text>
                      </View>
                    </View>
                    <View style={styles.timeRow}>
                      <Ionicons name="time-outline" size={12} color="#94A3B8" style={{ marginRight: 3 }} />
                      <Text style={styles.timestamp} allowFontScaling>
                        {timeStr}
                      </Text>
                    </View>
                  </View>
                  <Text style={styles.itemMessage} allowFontScaling>
                    {message}
                  </Text>
                </TouchableOpacity>
              );
            })
          )}
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    backgroundColor: colors.surface,
  },
  kickerRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 2,
  },
  kickerDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#0D9488",
    marginRight: 6,
  },
  kicker: {
    fontSize: 10,
    color: "#64748B",
    fontWeight: "700",
    letterSpacing: 1.1,
  },
  title: {
    fontSize: 20,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.3,
  },
  closeButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    justifyContent: "center",
  },
  content: {
    padding: spacing.md,
    gap: spacing.sm + 2,
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.xxl,
  },
  emptyIconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
  },
  emptyTitle: {
    fontSize: typography.fontSize.headline,
    fontWeight: "800",
    color: colors.textPrimary,
  },
  emptySubtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.xs,
    textAlign: "center",
    maxWidth: 280,
    lineHeight: 18,
  },
  itemCard: {
    backgroundColor: colors.surface,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 1,
  },
  itemTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs + 2,
  },
  typeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  typeIconBox: {
    width: 26,
    height: 26,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  typeBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  typeBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
  timeRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  timestamp: {
    fontSize: 11,
    color: "#64748B",
    fontWeight: "500",
  },
  itemMessage: {
    fontSize: 13,
    color: "#0F172A",
    lineHeight: 19,
    fontWeight: "500",
  },
});
