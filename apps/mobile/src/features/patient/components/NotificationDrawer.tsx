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
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import type { NotificationResponse } from "../../../services/schemas/notifications";

export type NotificationDrawerProps = {
  visible: boolean;
  onClose: () => void;
  notifications: NotificationResponse[];
  onSelectNotification?: (notification: NotificationResponse) => void;
};

function getNotificationTypeLabel(type: string): string {
  switch (type) {
    case "reminder":
      return "Reminder";
    case "alert":
      return "Health Alert";
    case "task_assigned":
      return "Task Update";
    case "care_update":
      return "Care Summary";
    case "clinical_communication":
      return "Clinic Message";
    default:
      return "Update";
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
        <View style={styles.header}>
          <Text style={styles.title} allowFontScaling>
            Notifications
          </Text>
          <TouchableOpacity
            style={styles.closeButton}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Close notifications"
          >
            <Text style={styles.closeText} allowFontScaling>
              ✕
            </Text>
          </TouchableOpacity>
        </View>

        <ScrollView contentContainerStyle={styles.content}>
          {notifications.length === 0 ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon} allowFontScaling>
                🔔
              </Text>
              <Text style={styles.emptyTitle} allowFontScaling>
                {"You're all caught up"}
              </Text>
              <Text style={styles.emptySubtitle} allowFontScaling>
                New reminders and clinic updates will appear here.
              </Text>
            </View>
          ) : (
            notifications.map((n) => {
              const typeLabel = getNotificationTypeLabel(n.notification_type);
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
                  accessibilityLabel={`${typeLabel}: ${message}`}
                >
                  <View style={styles.itemTopRow}>
                    <View style={styles.typeBadge}>
                      <Text style={styles.typeBadgeText} allowFontScaling>
                        {typeLabel}
                      </Text>
                    </View>
                    <Text style={styles.timestamp} allowFontScaling>
                      {timeStr}
                    </Text>
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
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.surface,
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  closeButton: {
    minWidth: touchTarget.min,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
  },
  closeText: {
    fontSize: 18,
    color: colors.textSecondary,
    fontWeight: "bold",
  },
  content: {
    padding: spacing.md,
    gap: spacing.sm,
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.xxl,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: spacing.md,
  },
  emptyTitle: {
    fontSize: typography.fontSize.headline,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  emptySubtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.xs,
    textAlign: "center",
  },
  itemCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  itemTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  typeBadge: {
    backgroundColor: "#F0F7F9",
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    borderRadius: radii.sm,
  },
  typeBadgeText: {
    fontSize: 11,
    fontWeight: typography.weight.bold,
    color: colors.primary,
  },
  timestamp: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  itemMessage: {
    fontSize: typography.fontSize.body,
    color: colors.textPrimary,
    lineHeight: typography.lineHeight.body,
  },
});
