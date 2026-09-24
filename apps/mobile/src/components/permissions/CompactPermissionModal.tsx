import React, { useState } from "react";
import {
  Modal,
  Platform,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  PERMISSION_METADATA,
  type PermissionState,
  type PermissionStatus,
  type PermissionType,
} from "../../services/permissions/types";

export interface CompactPermissionModalProps {
  visible: boolean;
  isInitial: boolean;
  permissionsToAsk: PermissionType[];
  state: PermissionState;
  onRequestPermission: (type: PermissionType) => Promise<PermissionStatus>;
  onOpenSettings: () => Promise<void>;
  onFinish: () => void;
}

export function CompactPermissionModal({
  visible,
  isInitial,
  permissionsToAsk,
  state,
  onRequestPermission,
  onOpenSettings,
  onFinish,
}: CompactPermissionModalProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);

  if (!visible || permissionsToAsk.length === 0) {
    return null;
  }

  const safeIndex = Math.min(currentIndex, permissionsToAsk.length - 1);
  const currentType = permissionsToAsk[safeIndex];
  if (!currentType) {
    return null;
  }
  const meta = PERMISSION_METADATA[currentType];
  const isBlocked = state[currentType] === "blocked";
  const totalSteps = permissionsToAsk.length;
  const isLastStep = safeIndex === totalSteps - 1;

  const advanceOrFinish = () => {
    if (isLastStep) {
      onFinish();
    } else {
      setCurrentIndex((prev) => prev + 1);
    }
  };

  const handlePrimaryPress = async () => {
    setIsProcessing(true);
    try {
      if (isBlocked) {
        await onOpenSettings();
        advanceOrFinish();
      } else {
        await onRequestPermission(currentType);
        advanceOrFinish();
      }
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSkip = () => {
    advanceOrFinish();
  };

  const webBackdropStyle =
    Platform.OS === "web"
      ? ({
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
        } as any)
      : undefined;

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent
      accessibilityViewIsModal
      statusBarTranslucent
      onRequestClose={handleSkip}
    >
      <View style={[styles.overlay, webBackdropStyle]}>
        <View style={styles.card}>
          {/* Header Step Indicator */}
          <View style={styles.headerRow}>
            <View style={styles.stepBadge}>
              <Text style={styles.stepBadgeText}>
                {isInitial ? `STEP ${safeIndex + 1} OF ${totalSteps}` : `REQUIRED (${safeIndex + 1}/${totalSteps})`}
              </Text>
            </View>

            {/* Progress Dots */}
            <View style={styles.dotsRow}>
              {permissionsToAsk.map((_, i) => (
                <View
                  key={i}
                  style={[
                    styles.dot,
                    i === safeIndex && styles.dotActive,
                    i < safeIndex && styles.dotCompleted,
                  ]}
                />
              ))}
            </View>
          </View>

          {/* Centered Glowing Icon */}
          <View
            style={[
              styles.iconWrapper,
              {
                backgroundColor: meta.darkBgColor,
                borderColor: meta.darkIconColor + "40",
              },
            ]}
          >
            <Ionicons
              name={meta.iconName as any}
              size={30}
              color={meta.darkIconColor}
            />
          </View>

          {/* Title and Short Description */}
          <Text style={styles.title}>Turn On {meta.title}</Text>
          <Text style={styles.description}>
            {meta.detailedRationale}
          </Text>

          {/* Action Buttons */}
          <View style={styles.actionsContainer}>
            <TouchableOpacity
              style={[styles.primaryButton, isProcessing && styles.buttonDisabled]}
              onPress={handlePrimaryPress}
              disabled={isProcessing}
              accessibilityRole="button"
              accessibilityLabel={isBlocked ? "Open Device Settings" : `Turn on ${meta.title}`}
            >
              <Ionicons
                name={isBlocked ? "settings-outline" : "checkmark-circle-outline"}
                size={18}
                color="#FFFFFF"
              />
              <Text style={styles.primaryButtonText}>
                {isProcessing
                  ? "Allowing…"
                  : isBlocked
                  ? "Open Device Settings"
                  : `Turn On ${meta.title}`}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.secondaryButton}
              onPress={handleSkip}
              disabled={isProcessing}
              accessibilityRole="button"
              accessibilityLabel={isInitial ? "Skip for now" : "Ask me next time"}
            >
              <Text style={styles.secondaryButtonText}>
                {isInitial ? "Skip for now" : "Ask me next time"}
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(3, 7, 18, 0.82)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 24,
  },
  card: {
    width: "100%",
    maxWidth: 336,
    backgroundColor: "#111827",
    borderRadius: 22,
    paddingHorizontal: 20,
    paddingTop: 18,
    paddingBottom: 16,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.12)",
    shadowColor: "#000",
    shadowOpacity: 0.6,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 8 },
    elevation: 12,
    alignItems: "center",
  },
  headerRow: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 16,
  },
  stepBadge: {
    backgroundColor: "#0D253A",
    borderWidth: 1,
    borderColor: "#0E4366",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  stepBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#38BDF8",
    letterSpacing: 0.6,
  },
  dotsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#374151",
  },
  dotActive: {
    width: 16,
    borderRadius: 3,
    backgroundColor: "#38BDF8",
  },
  dotCompleted: {
    backgroundColor: "#22C55E",
  },
  iconWrapper: {
    width: 62,
    height: 62,
    borderRadius: 31,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1.5,
    marginBottom: 14,
    shadowColor: "#000",
    shadowOpacity: 0.3,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
  },
  title: {
    fontSize: 18,
    fontWeight: "700",
    color: "#FFFFFF",
    marginBottom: 8,
    textAlign: "center",
  },
  description: {
    fontSize: 13,
    color: "#94A3B8",
    textAlign: "center",
    lineHeight: 19,
    paddingHorizontal: 6,
    marginBottom: 20,
  },
  actionsContainer: {
    width: "100%",
    gap: 6,
  },
  primaryButton: {
    width: "100%",
    height: 44,
    backgroundColor: "#0D5C75",
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
  secondaryButton: {
    width: "100%",
    height: 34,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryButtonText: {
    color: "#64748B",
    fontSize: 12,
    fontWeight: "500",
  },
  buttonDisabled: {
    opacity: 0.6,
  },
});
