import React, { useEffect, useRef, useState } from "react";
import {
  Animated,
  Easing,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "../doctorDesign";
import { buildDoctorAccountQrValue } from "../doctorQr";
import { QrCodeView } from "./QrCodeView";

export type DoctorQrModalProps = {
  visible: boolean;
  doctorAccountId?: string | null;
  doctorDisplayName?: string | null;
  facilityId?: string | null;
  onClose: () => void;
};

export function DoctorQrModal({
  visible,
  doctorAccountId,
  doctorDisplayName,
  facilityId,
  onClose,
}: DoctorQrModalProps) {
  const [isRendered, setIsRendered] = useState(visible);
  const isClosingRef = useRef(false);

  // Animated values for modal arrival
  const backdropOpacity = useRef(new Animated.Value(0)).current;
  const cardScale = useRef(new Animated.Value(0.82)).current;
  const cardTranslateY = useRef(new Animated.Value(24)).current;
  const cardOpacity = useRef(new Animated.Value(0)).current;
  const qrScale = useRef(new Animated.Value(0.92)).current;
  const qrOpacity = useRef(new Animated.Value(0)).current;

  // Button micro-interaction animations
  const doneBtnScale = useRef(new Animated.Value(1)).current;
  const closeBtnScale = useRef(new Animated.Value(1)).current;

  const useNative = Platform.OS !== "web";

  const triggerEntrance = () => {
    isClosingRef.current = false;
    backdropOpacity.setValue(0);
    cardScale.setValue(0.82);
    cardTranslateY.setValue(24);
    cardOpacity.setValue(0);
    qrScale.setValue(0.92);
    qrOpacity.setValue(0);

    Animated.parallel([
      // Backdrop fade in
      Animated.timing(backdropOpacity, {
        toValue: 1,
        duration: 220,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: useNative,
      }),
      // Modal card spring scale
      Animated.spring(cardScale, {
        toValue: 1,
        damping: 14,
        stiffness: 130,
        mass: 0.85,
        useNativeDriver: useNative,
      }),
      // Modal card spring translateY
      Animated.spring(cardTranslateY, {
        toValue: 0,
        damping: 15,
        stiffness: 140,
        mass: 0.9,
        useNativeDriver: useNative,
      }),
      // Modal card opacity fade
      Animated.timing(cardOpacity, {
        toValue: 1,
        duration: 180,
        easing: Easing.out(Easing.quad),
        useNativeDriver: useNative,
      }),
      // Staggered QR Code focus reveal
      Animated.sequence([
        Animated.delay(80),
        Animated.parallel([
          Animated.spring(qrScale, {
            toValue: 1,
            friction: 5,
            tension: 90,
            useNativeDriver: useNative,
          }),
          Animated.timing(qrOpacity, {
            toValue: 1,
            duration: 160,
            easing: Easing.out(Easing.quad),
            useNativeDriver: useNative,
          }),
        ]),
      ]),
    ]).start();
  };

  const triggerExit = (callback?: () => void) => {
    if (isClosingRef.current) return;
    isClosingRef.current = true;

    Animated.parallel([
      Animated.timing(cardScale, {
        toValue: 0.88,
        duration: 150,
        easing: Easing.in(Easing.cubic),
        useNativeDriver: useNative,
      }),
      Animated.timing(cardTranslateY, {
        toValue: 16,
        duration: 150,
        easing: Easing.in(Easing.quad),
        useNativeDriver: useNative,
      }),
      Animated.timing(cardOpacity, {
        toValue: 0,
        duration: 130,
        easing: Easing.linear,
        useNativeDriver: useNative,
      }),
      Animated.timing(backdropOpacity, {
        toValue: 0,
        duration: 150,
        easing: Easing.linear,
        useNativeDriver: useNative,
      }),
    ]).start(() => {
      setIsRendered(false);
      isClosingRef.current = false;
      onClose();
      if (callback) callback();
    });
  };

  useEffect(() => {
    if (visible) {
      setIsRendered(true);
      triggerEntrance();
    } else if (isRendered && !isClosingRef.current) {
      triggerExit();
    }
  }, [visible]);

  if (!isRendered) return null;

  const value = doctorAccountId
    ? buildDoctorAccountQrValue({
        accountId: doctorAccountId,
        displayName: doctorDisplayName,
        facilityId,
      })
    : null;

  const handleDismiss = () => {
    triggerExit();
  };

  return (
    <Modal
      visible={isRendered}
      transparent
      animationType="none"
      statusBarTranslucent
      onRequestClose={handleDismiss}
    >
      <Pressable
        style={StyleSheet.absoluteFill}
        onPress={handleDismiss}
        accessibilityRole="button"
        accessibilityLabel="Close doctor QR code"
      >
        <Animated.View
          style={[
            styles.backdrop,
            {
              opacity: backdropOpacity,
            },
          ]}
        />
      </Pressable>

      <View style={styles.centerContainer} pointerEvents="box-none">
        <Animated.View
          style={[
            styles.card,
            {
              opacity: cardOpacity,
              transform: [{ scale: cardScale }, { translateY: cardTranslateY }],
            },
          ]}
          accessibilityViewIsModal
        >
          {/* Card Header */}
          <View style={styles.cardHeader}>
            <View style={styles.cardTitleRow}>
              <View style={styles.iconBadge}>
                <Ionicons name="qr-code" size={20} color={doctorPalette.primary} />
              </View>
              <View style={styles.cardTitleTextCol}>
                <Text style={styles.cardTitle} allowFontScaling>
                  Account QR Code
                </Text>
                <Text style={styles.cardSubtitle} allowFontScaling>
                  Unique to this clinician account
                </Text>
              </View>
            </View>
            <Pressable
              onPressIn={() => {
                Animated.spring(closeBtnScale, {
                  toValue: 0.88,
                  speed: 25,
                  bounciness: 0,
                  useNativeDriver: useNative,
                }).start();
              }}
              onPressOut={() => {
                Animated.spring(closeBtnScale, {
                  toValue: 1,
                  friction: 4,
                  tension: 80,
                  useNativeDriver: useNative,
                }).start();
              }}
              onPress={handleDismiss}
              accessibilityRole="button"
              accessibilityLabel="Close account QR code modal"
              hitSlop={8}
            >
              <Animated.View
                style={[
                  styles.closeButton,
                  {
                    transform: [{ scale: closeBtnScale }],
                  },
                ]}
              >
                <Ionicons name="close" size={20} color={doctorPalette.ink} />
              </Animated.View>
            </Pressable>
          </View>

          {/* Doctor Identity Banner */}
          {doctorDisplayName ? (
            <View style={styles.doctorInfoRow}>
              <View style={styles.doctorAvatarPill}>
                <Ionicons name="shield-checkmark" size={13} color="#047857" />
                <Text style={styles.doctorDisplayName} numberOfLines={1}>
                  {doctorDisplayName.startsWith("Dr.") ? doctorDisplayName : `Dr. ${doctorDisplayName}`}
                </Text>
              </View>
              {facilityId ? (
                <Text style={styles.facilityTag} numberOfLines={1}>
                  {facilityId.length > 14 ? `${facilityId.slice(0, 10)}…` : facilityId}
                </Text>
              ) : null}
            </View>
          ) : null}

          {/* QR Code Frame with focus animation */}
          {value ? (
            <Animated.View
              style={[
                styles.qrFrame,
                {
                  opacity: qrOpacity,
                  transform: [{ scale: qrScale }],
                },
              ]}
            >
              <QrCodeView value={value} size={208} quietZone={16} testID="doctor-account-qr" />
            </Animated.View>
          ) : (
            <Text style={styles.unavailableText} allowFontScaling>
              Account identifier unavailable for this session.
            </Text>
          )}

          {/* Instructional helper */}
          <View style={styles.instructionRow}>
            <Ionicons name="scan-outline" size={14} color={doctorPalette.muted} />
            <Text style={styles.instructionText}>
              Scan via patient THALI app to link care accounts
            </Text>
          </View>

          {/* Done Button with tactile feedback */}
          <Pressable
            onPressIn={() => {
              Animated.spring(doneBtnScale, {
                toValue: 0.96,
                speed: 25,
                bounciness: 0,
                useNativeDriver: useNative,
              }).start();
            }}
            onPressOut={() => {
              Animated.spring(doneBtnScale, {
                toValue: 1,
                friction: 4,
                tension: 80,
                useNativeDriver: useNative,
              }).start();
            }}
            onPress={handleDismiss}
            accessibilityRole="button"
            accessibilityLabel="Close QR code modal"
          >
            <Animated.View
              style={[
                styles.dismissButton,
                {
                  transform: [{ scale: doneBtnScale }],
                },
              ]}
            >
              <Text style={styles.dismissButtonText} allowFontScaling>
                Done
              </Text>
            </Animated.View>
          </Pressable>
        </Animated.View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(15, 23, 42, 0.52)",
  },
  centerContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  card: {
    width: "100%",
    maxWidth: 340,
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.xl,
    padding: 22,
    gap: 16,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    ...doctorSoftShadow,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
  },
  cardTitleRow: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  iconBadge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  cardTitleTextCol: {
    flex: 1,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  cardSubtitle: {
    fontSize: 11.5,
    color: doctorPalette.muted,
    marginTop: 2,
  },
  closeButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: doctorPalette.surfaceSoft,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
  },
  doctorInfoRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 2,
    flexWrap: "wrap",
  },
  doctorAvatarPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: "#ECFDF5",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: doctorRadii.pill,
    borderWidth: 1,
    borderColor: "#A7F3D0",
  },
  doctorDisplayName: {
    fontSize: 11.5,
    fontWeight: "700",
    color: "#065F46",
    maxWidth: 180,
  },
  facilityTag: {
    fontSize: 10.5,
    color: doctorPalette.muted,
    backgroundColor: doctorPalette.surfaceSoft,
    paddingHorizontal: 6,
    paddingVertical: 3,
    borderRadius: doctorRadii.sm,
  },
  qrFrame: {
    alignSelf: "center",
    backgroundColor: "#FFFFFF",
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: 6,
    ...doctorSoftShadow,
  },
  unavailableText: {
    alignSelf: "center",
    fontSize: 13,
    color: doctorPalette.muted,
    paddingVertical: 48,
  },
  instructionRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginTop: -2,
  },
  instructionText: {
    fontSize: 11,
    color: doctorPalette.muted,
    textAlign: "center",
    fontWeight: "500",
  },
  dismissButton: {
    alignSelf: "stretch",
    height: 44,
    borderRadius: doctorRadii.md,
    backgroundColor: doctorPalette.ink,
    alignItems: "center",
    justifyContent: "center",
    ...doctorSoftShadow,
  },
  dismissButtonText: {
    fontSize: 14,
    fontWeight: "700",
    color: "#FFFFFF",
    letterSpacing: 0.3,
  },
});