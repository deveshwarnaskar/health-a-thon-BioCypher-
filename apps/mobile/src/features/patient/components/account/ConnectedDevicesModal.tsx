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

export type ConnectedDevicesModalProps = {
  visible: boolean;
  onClose: () => void;
};

type DeviceItem = {
  id: string;
  name: string;
  category: "meter" | "cgm" | "wearable";
  status: "connected" | "available" | "manual";
  lastSync?: string;
  icon: keyof typeof Ionicons.glyphMap;
  iconBg: string;
  iconColor: string;
};

const DEVICES: DeviceItem[] = [
  {
    id: "meter-1",
    name: "Accu-Chek Instant / Guide",
    category: "meter",
    status: "manual",
    lastSync: "Manual observation mode active",
    icon: "water-outline",
    iconBg: "#F0FDFA",
    iconColor: "#0D9488",
  },
  {
    id: "wearable-1",
    name: "Smart Watch / Step Counter",
    category: "wearable",
    status: "available",
    lastSync: "Ready for Bluetooth pairing",
    icon: "watch-outline",
    iconBg: "#EFF6FF",
    iconColor: "#2563EB",
  },
  {
    id: "cgm-1",
    name: "Continuous Glucose Monitor (CGM)",
    category: "cgm",
    status: "available",
    lastSync: "Not configured for current care plan",
    icon: "pulse-outline",
    iconBg: "#F5F3FF",
    iconColor: "#7C3AED",
  },
];

export function ConnectedDevicesModal({ visible, onClose }: ConnectedDevicesModalProps) {
  return (
    <Modal visible={visible} animationType="slide" transparent={false} onRequestClose={onClose}>
      <View style={styles.container}>
        {/* Modern Header */}
        <View style={styles.header}>
          <TouchableOpacity
            onPress={onClose}
            style={styles.backBtn}
            accessibilityRole="button"
            accessibilityLabel="Back"
            activeOpacity={0.7}
          >
            <Ionicons name="arrow-back" size={20} color="#0F172A" />
          </TouchableOpacity>
          <View style={styles.headerTextCol}>
            <View style={styles.kickerRow}>
              <View style={styles.kickerDot} />
              <Text style={styles.kicker} allowFontScaling>
                HARDWARE & SENSORS
              </Text>
            </View>
            <Text style={styles.title} allowFontScaling>
              Connected Devices
            </Text>
          </View>
        </View>

        <ScrollView style={styles.body} contentContainerStyle={styles.bodyContent} showsVerticalScrollIndicator={false}>
          {/* Info Card */}
          <View style={styles.infoCard}>
            <View style={styles.infoIconBox}>
              <Ionicons name="bluetooth" size={18} color="#0284C7" />
            </View>
            <View style={styles.infoTextCol}>
              <Text style={styles.infoTitle} allowFontScaling>
                Cryptographic Hardware Sync
              </Text>
              <Text style={styles.infoText} allowFontScaling>
                Bluetooth glucose meters and wearable telemetry sync locally on your device. Readings are cryptographically signed before transmission.
              </Text>
            </View>
          </View>

          <Text style={styles.sectionTitle} allowFontScaling>
            AVAILABLE HARDWARE SOURCES
          </Text>

          {DEVICES.map((dev) => (
            <View key={dev.id} style={styles.deviceCard}>
              <View style={[styles.deviceIconCircle, { backgroundColor: dev.iconBg }]}>
                <Ionicons name={dev.icon} size={22} color={dev.iconColor} />
              </View>

              <View style={styles.deviceInfo}>
                <Text style={styles.deviceName} allowFontScaling>
                  {dev.name}
                </Text>
                <Text style={styles.deviceSync} allowFontScaling>
                  {dev.lastSync}
                </Text>
              </View>

              <View
                style={[
                  styles.deviceBadge,
                  dev.status === "connected"
                    ? styles.badgeConnected
                    : dev.status === "manual"
                    ? styles.badgeManual
                    : styles.badgeAvailable,
                ]}
              >
                <Text
                  style={[
                    styles.deviceBadgeText,
                    dev.status === "connected"
                      ? styles.badgeTextConnected
                      : dev.status === "manual"
                      ? styles.badgeTextManual
                      : styles.badgeTextAvailable,
                  ]}
                  allowFontScaling
                >
                  {dev.status === "connected"
                    ? "CONNECTED"
                    : dev.status === "manual"
                    ? "STANDBY"
                    : "PAIR"}
                </Text>
              </View>
            </View>
          ))}

          {/* Direct Input fallback explanation */}
          <View style={styles.tipCard}>
            <View style={styles.tipHeaderRow}>
              <Ionicons name="bulb-outline" size={16} color="#0D9488" />
              <Text style={styles.tipTitle} allowFontScaling>
                DIRECT LOGGING ALWAYS SUPPORTED
              </Text>
            </View>
            <Text style={styles.tipBody} allowFontScaling>
              Even without a paired device, you can log glucose readings, meals, and vitals instantly via the Record tab or through WhatsApp voice/photo notes.
            </Text>
          </View>

          <View style={{ height: 40 }} />
        </ScrollView>
      </View>
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
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingTop: 54,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    backgroundColor: colors.surface,
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  headerTextCol: {
    marginLeft: spacing.sm + 2,
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
    color: "#0F172A",
    fontWeight: "800",
    letterSpacing: -0.3,
  },
  body: {
    flex: 1,
  },
  bodyContent: {
    padding: spacing.md,
    gap: spacing.md,
  },
  infoCard: {
    flexDirection: "row",
    backgroundColor: "#F0F9FF",
    borderRadius: 18,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#BAE6FD",
    gap: spacing.sm,
    alignItems: "flex-start",
  },
  infoIconBox: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: "#E0F2FE",
    alignItems: "center",
    justifyContent: "center",
  },
  infoTextCol: {
    flex: 1,
  },
  infoTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0369A1",
    marginBottom: 2,
  },
  infoText: {
    fontSize: 12,
    color: "#0284C7",
    lineHeight: 18,
  },
  sectionTitle: {
    fontSize: 11,
    color: "#64748B",
    fontWeight: "700",
    letterSpacing: 1.1,
    marginLeft: 4,
  },
  deviceCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 20,
    padding: spacing.md + 2,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 1,
  },
  deviceIconCircle: {
    width: 44,
    height: 44,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  deviceInfo: {
    flex: 1,
  },
  deviceName: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0F172A",
  },
  deviceSync: {
    fontSize: 11,
    color: "#64748B",
    marginTop: 2,
  },
  deviceBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
  },
  badgeConnected: {
    backgroundColor: "#ECFDF5",
    borderColor: "#A7F3D0",
  },
  badgeManual: {
    backgroundColor: "#F1F5F9",
    borderColor: "#E2E8F0",
  },
  badgeAvailable: {
    backgroundColor: "#EFF6FF",
    borderColor: "#BFDBFE",
  },
  deviceBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  badgeTextConnected: {
    color: "#059669",
  },
  badgeTextManual: {
    color: "#475569",
  },
  badgeTextAvailable: {
    color: "#2563EB",
  },
  tipCard: {
    backgroundColor: "#F8FAFC",
    borderRadius: 18,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    gap: 6,
  },
  tipHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  tipTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: "#0D9488",
    letterSpacing: 0.8,
  },
  tipBody: {
    fontSize: 12,
    color: "#64748B",
    lineHeight: 18,
  },
});
