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

export interface InitialPermissionModalProps {
  visible: boolean;
  state: PermissionState;
  onRequestAll: () => Promise<void>;
  onRequestSingle: (type: PermissionType) => Promise<void>;
  onComplete: () => void;
}

export function InitialPermissionModal({
  visible,
  state,
  onRequestAll,
  onRequestSingle,
  onComplete,
}: InitialPermissionModalProps) {
  const [requesting, setRequesting] = useState(false);
  const [requestingType, setRequestingType] = useState<PermissionType | null>(null);

  const allGranted =
    state.notifications === "granted" &&
    state.microphone === "granted" &&
    state.camera === "granted";

  const handleAllowAll = async () => {
    setRequesting(true);
    try {
      await onRequestAll();
    } finally {
      setRequesting(false);
    }
  };

  const handleAllowSingle = async (type: PermissionType) => {
    setRequestingType(type);
    try {
      await onRequestSingle(type);
    } finally {
      setRequestingType(null);
    }
  };

  const permissionList: PermissionType[] = ["notifications", "microphone", "camera"];

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={false}
      presentationStyle="fullScreen"
      accessibilityViewIsModal
    >
      <SafeAreaView style={styles.safeArea}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {/* Header Branding */}
          <View style={styles.header}>
            <View style={styles.badgeIconContainer}>
              <Ionicons name="shield-checkmark" size={32} color={colors.primary} />
            </View>
            <Text style={styles.welcomeText}>WELCOME TO THALI</Text>
            <Text style={styles.mainTitle}>Turn On Permissions for Best Experience</Text>
            <Text style={styles.subtitle}>
              Like WhatsApp and Facebook, THALI works best when you grant permission for
              notifications, microphone, and camera on first install.
            </Text>
          </View>

          {/* Permission Cards */}
          <View style={styles.cardList}>
            {permissionList.map((type) => {
              const meta = PERMISSION_METADATA[type];
              const isGranted = state[type] === "granted";
              const isItemBusy = requestingType === type;

              return (
                <View key={type} style={styles.card}>
                  <View
                    style={[
                      styles.iconCircle,
                      { backgroundColor: meta.iconBgColor },
                    ]}
                  >
                    <Ionicons
                      name={meta.iconName as any}
                      size={24}
                      color={meta.iconColor}
                    />
                  </View>

                  <View style={styles.cardBody}>
                    <View style={styles.cardTitleRow}>
                      <Text style={styles.cardTitle}>{meta.title}</Text>
                      {isGranted ? (
                        <View style={styles.grantedBadge}>
                          <Ionicons
                            name="checkmark-circle"
                            size={14}
                            color={colors.leafGreen}
                          />
                          <Text style={styles.grantedBadgeText}>Enabled</Text>
                        </View>
                      ) : (
                        <View style={styles.requiredBadge}>
                          <Text style={styles.requiredBadgeText}>Required</Text>
                        </View>
                      )}
                    </View>

                    <Text style={styles.cardDescription}>{meta.detailedRationale}</Text>

                    {!isGranted && (
                      <TouchableOpacity
                        style={styles.singleAllowButton}
                        onPress={() => handleAllowSingle(type)}
                        disabled={requesting || isItemBusy}
                        accessibilityRole="button"
                        accessibilityLabel={`Allow ${meta.title} access`}
                      >
                        <Text style={styles.singleAllowButtonText}>
                          {isItemBusy ? "Allowing…" : `Allow ${meta.title}`}
                        </Text>
                        <Ionicons
                          name="chevron-forward"
                          size={14}
                          color={colors.primary}
                        />
                      </TouchableOpacity>
                    )}
                  </View>
                </View>
              );
            })}
          </View>

          {/* Privacy Note */}
          <View style={styles.privacyNote}>
            <Ionicons name="lock-closed-outline" size={16} color={colors.textSecondary} />
            <Text style={styles.privacyText}>
              Your data is encrypted end-to-end. We only access device sensors when you
              actively interact with health tools.
            </Text>
          </View>
        </ScrollView>

        {/* Footer Actions */}
        <View style={styles.footer}>
          {!allGranted ? (
            <TouchableOpacity
              style={[styles.primaryButton, requesting && styles.buttonDisabled]}
              onPress={handleAllowAll}
              disabled={requesting}
              accessibilityRole="button"
              accessibilityLabel="Turn on all permissions"
            >
              <Ionicons
                name="shield-checkmark-outline"
                size={20}
                color={colors.textOnPrimary}
              />
              <Text style={styles.primaryButtonText}>
                {requesting ? "Requesting Permissions…" : "Turn On All Permissions"}
              </Text>
            </TouchableOpacity>
          ) : null}

          <TouchableOpacity
            style={[
              allGranted ? styles.primaryButton : styles.secondaryButton,
              requesting && styles.buttonDisabled,
            ]}
            onPress={onComplete}
            disabled={requesting}
            accessibilityRole="button"
            accessibilityLabel={allGranted ? "Get Started" : "Continue to Application"}
          >
            <Text
              style={
                allGranted
                  ? styles.primaryButtonText
                  : styles.secondaryButtonText
              }
            >
              {allGranted ? "Get Started" : "Continue to App"}
            </Text>
            {allGranted && (
              <Ionicons
                name="arrow-forward"
                size={18}
                color={colors.textOnPrimary}
              />
            )}
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  header: {
    alignItems: "center",
    marginBottom: spacing.lg,
  },
  badgeIconContainer: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#E0F2FE",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm,
  },
  welcomeText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.semibold,
    color: colors.primary,
    letterSpacing: 1.2,
    marginBottom: spacing.xxs,
  },
  mainTitle: {
    fontSize: typography.fontSize.headline,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    textAlign: "center",
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    textAlign: "center",
    lineHeight: 20,
    paddingHorizontal: spacing.sm,
  },
  cardList: {
    gap: spacing.md,
  },
  card: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: "#000",
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
    alignItems: "flex-start",
  },
  iconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  cardBody: {
    flex: 1,
  },
  cardTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.xxs,
  },
  cardTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  grantedBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#DCFCE7",
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    borderRadius: 12,
    gap: 4,
  },
  grantedBadgeText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.semibold,
    color: colors.leafGreen,
  },
  requiredBadge: {
    backgroundColor: "#FEF3C7",
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    borderRadius: 12,
  },
  requiredBadgeText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.semibold,
    color: colors.warning,
  },
  cardDescription: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    lineHeight: 18,
    marginBottom: spacing.xs,
  },
  singleAllowButton: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: 4,
    paddingVertical: spacing.xxs,
  },
  singleAllowButtonText: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.semibold,
    color: colors.primary,
  },
  privacyNote: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surfaceSoft,
    padding: spacing.md,
    borderRadius: 12,
    marginTop: spacing.lg,
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: "#E2F1F8",
  },
  privacyText: {
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
    gap: spacing.sm,
  },
  primaryButton: {
    backgroundColor: colors.primary,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 14,
    borderRadius: 12,
    gap: spacing.xs,
  },
  primaryButtonText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
  },
  secondaryButton: {
    backgroundColor: "transparent",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    borderRadius: 12,
  },
  secondaryButtonText: {
    color: colors.textSecondary,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.medium,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
});
