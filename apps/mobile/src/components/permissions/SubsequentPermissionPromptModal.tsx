import React, { useState } from "react";
import {
  Modal,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, typography } from "../../theming/tokens";
import {
  PERMISSION_METADATA,
  type PermissionState,
  type PermissionType,
} from "../../services/permissions/types";

export interface SubsequentPermissionPromptModalProps {
  visible: boolean;
  state: PermissionState;
  onRequestAll: () => Promise<void>;
  onRequestSingle: (type: PermissionType) => Promise<void>;
  onOpenSettings: () => Promise<void>;
  onDismissForSession: () => void;
}

export function SubsequentPermissionPromptModal({
  visible,
  state,
  onRequestAll,
  onRequestSingle,
  onOpenSettings,
  onDismissForSession,
}: SubsequentPermissionPromptModalProps) {
  const [requesting, setRequesting] = useState(false);
  const [requestingType, setRequestingType] = useState<PermissionType | null>(null);

  const permissionList: PermissionType[] = ["notifications", "microphone", "camera"];
  const missing = permissionList.filter((type) => state[type] !== "granted");
  const hasBlocked = permissionList.some((type) => state[type] === "blocked");

  const handleRequestAll = async () => {
    setRequesting(true);
    try {
      if (hasBlocked) {
        await onOpenSettings();
      } else {
        await onRequestAll();
      }
    } finally {
      setRequesting(false);
    }
  };

  const handleRequestSingle = async (type: PermissionType) => {
    setRequestingType(type);
    try {
      if (state[type] === "blocked") {
        await onOpenSettings();
      } else {
        await onRequestSingle(type);
      }
    } finally {
      setRequestingType(null);
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent
      accessibilityViewIsModal
    >
      <View style={styles.overlay}>
        <SafeAreaView style={styles.dialogContainer}>
          <ScrollView
            contentContainerStyle={styles.dialogContent}
            showsVerticalScrollIndicator={false}
          >
            {/* Warning Icon Badge */}
            <View style={styles.header}>
              <View style={styles.warningIconCircle}>
                <Ionicons name="warning-outline" size={32} color={colors.warning} />
              </View>
              <Text style={styles.title}>Turn On Permissions</Text>
              <Text style={styles.description}>
                Some permissions were not turned on. To use all features of THALI (like
                WhatsApp and Facebook), please give the app permission to turn these on:
              </Text>
            </View>

            {/* Permissions Status Checklist */}
            <View style={styles.checklist}>
              {permissionList.map((type) => {
                const meta = PERMISSION_METADATA[type];
                const isGranted = state[type] === "granted";
                const isBlocked = state[type] === "blocked";
                const isItemBusy = requestingType === type;

                return (
                  <View
                    key={type}
                    style={[
                      styles.checklistItem,
                      !isGranted && styles.checklistItemMissing,
                    ]}
                  >
                    <View
                      style={[
                        styles.itemIconCircle,
                        { backgroundColor: meta.iconBgColor },
                      ]}
                    >
                      <Ionicons
                        name={meta.iconName as any}
                        size={20}
                        color={meta.iconColor}
                      />
                    </View>

                    <View style={styles.itemInfo}>
                      <Text style={styles.itemTitle}>{meta.title}</Text>
                      <Text style={styles.itemSubtitle}>
                        {meta.shortDescription}
                      </Text>
                    </View>

                    {isGranted ? (
                      <View style={styles.statusGranted}>
                        <Ionicons
                          name="checkmark-circle"
                          size={20}
                          color={colors.leafGreen}
                        />
                      </View>
                    ) : (
                      <TouchableOpacity
                        style={styles.enableButton}
                        onPress={() => handleRequestSingle(type)}
                        disabled={requesting || isItemBusy}
                        accessibilityRole="button"
                        accessibilityLabel={`Enable ${meta.title}`}
                      >
                        <Text style={styles.enableButtonText}>
                          {isItemBusy
                            ? "…"
                            : isBlocked
                            ? "Settings"
                            : "Enable"}
                        </Text>
                      </TouchableOpacity>
                    )}
                  </View>
                );
              })}
            </View>

            {hasBlocked && (
              <View style={styles.settingsNotice}>
                <Ionicons
                  name="settings-outline"
                  size={16}
                  color={colors.textSecondary}
                />
                <Text style={styles.settingsNoticeText}>
                  One or more permissions were previously denied. Tap “Open Settings”
                  to toggle them on in device settings.
                </Text>
              </View>
            )}
          </ScrollView>

          {/* Action Buttons */}
          <View style={styles.footer}>
            <TouchableOpacity
              style={[styles.primaryButton, requesting && styles.buttonDisabled]}
              onPress={handleRequestAll}
              disabled={requesting}
              accessibilityRole="button"
              accessibilityLabel={hasBlocked ? "Open Device Settings" : "Enable Missing Permissions"}
            >
              <Ionicons
                name={hasBlocked ? "settings-outline" : "shield-checkmark-outline"}
                size={18}
                color={colors.textOnPrimary}
              />
              <Text style={styles.primaryButtonText}>
                {requesting
                  ? "Updating…"
                  : hasBlocked
                  ? "Open Device Settings"
                  : `Enable All (${missing.length})`}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.secondaryButton}
              onPress={onDismissForSession}
              accessibilityRole="button"
              accessibilityLabel="Continue to App and ask me next time"
            >
              <Text style={styles.secondaryButtonText}>
                Continue to App (Ask me next time)
              </Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.6)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.md,
  },
  dialogContainer: {
    width: "100%",
    maxWidth: 440,
    backgroundColor: colors.surface,
    borderRadius: 20,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOpacity: 0.2,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 4 },
    elevation: 8,
  },
  dialogContent: {
    padding: spacing.lg,
  },
  header: {
    alignItems: "center",
    marginBottom: spacing.md,
  },
  warningIconCircle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "#FEF3C7",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm,
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
    textAlign: "center",
  },
  description: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    textAlign: "center",
    lineHeight: 20,
  },
  checklist: {
    gap: spacing.sm,
    marginVertical: spacing.md,
  },
  checklistItem: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.background,
    padding: spacing.sm,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  checklistItemMissing: {
    borderColor: "#FDE68A",
    backgroundColor: "#FFFBEB",
  },
  itemIconCircle: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.sm,
  },
  itemInfo: {
    flex: 1,
    marginRight: spacing.xs,
  },
  itemTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  itemSubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 14,
  },
  statusGranted: {
    paddingHorizontal: spacing.xs,
  },
  enableButton: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: 8,
  },
  enableButtonText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
  },
  settingsNotice: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surfaceSoft,
    padding: spacing.sm,
    borderRadius: 8,
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  settingsNoticeText: {
    flex: 1,
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  footer: {
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: spacing.xs,
  },
  primaryButton: {
    backgroundColor: colors.primary,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
    borderRadius: 10,
    gap: spacing.xs,
  },
  primaryButtonText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
  },
  secondaryButton: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 8,
  },
  secondaryButtonText: {
    color: colors.textSecondary,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.medium,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
});
