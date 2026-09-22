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

export type PrivacySecurityModalProps = {
  visible: boolean;
  onClose: () => void;
  uhid?: string;
  patientId?: string | null;
  onSignOut: () => void;
};

export function PrivacySecurityModal({
  visible,
  onClose,
  uhid,
  patientId,
  onSignOut,
}: PrivacySecurityModalProps) {
  const maskedId = patientId
    ? `${patientId.slice(0, 8)}••••••••${patientId.slice(-4)}`
    : "ID-PROTECTED";

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
                DATA GOVERNANCE & SECURITY
              </Text>
            </View>
            <Text style={styles.title} allowFontScaling>
              Privacy & Security
            </Text>
          </View>
        </View>

        <ScrollView style={styles.body} contentContainerStyle={styles.bodyContent} showsVerticalScrollIndicator={false}>
          {/* Identity Protection */}
          <View style={styles.card}>
            <View style={styles.sectionHeaderRow}>
              <View style={[styles.sectionIconBox, { backgroundColor: "#F0FDFA" }]}>
                <Ionicons name="shield-checkmark-outline" size={16} color="#0D9488" />
              </View>
              <Text style={styles.cardHeader} allowFontScaling>
                PATIENT IDENTITY PROTECTION
              </Text>
            </View>

            <View style={styles.row}>
              <Text style={styles.label} allowFontScaling>Hospital Identifier (UHID)</Text>
              <View style={styles.uhidBadge}>
                <Ionicons name="id-card-outline" size={12} color="#0D9488" style={{ marginRight: 4 }} />
                <Text style={styles.uhidText} allowFontScaling>{uhid || "UHID-ASSIGNED"}</Text>
              </View>
            </View>
            <View style={styles.divider} />

            <View style={styles.row}>
              <Text style={styles.label} allowFontScaling>System Patient UUID</Text>
              <View style={styles.monoBadge}>
                <Text style={styles.valMono} allowFontScaling>{maskedId}</Text>
              </View>
            </View>
            <View style={styles.divider} />

            <View style={styles.row}>
              <Text style={styles.label} allowFontScaling>Runtime Role</Text>
              <View style={styles.rolePill}>
                <Ionicons name="checkmark-circle" size={12} color="#059669" style={{ marginRight: 4 }} />
                <Text style={styles.roleText} allowFontScaling>PATIENT (VERIFIED)</Text>
              </View>
            </View>
          </View>

          {/* Cryptographic Standards */}
          <View style={styles.card}>
            <View style={styles.sectionHeaderRow}>
              <View style={[styles.sectionIconBox, { backgroundColor: "#EFF6FF" }]}>
                <Ionicons name="lock-closed-outline" size={16} color="#2563EB" />
              </View>
              <Text style={styles.cardHeader} allowFontScaling>
                ENCRYPTION & STORAGE BOUNDARIES
              </Text>
            </View>

            <View style={styles.securityItem}>
              <View style={[styles.iconContainer, { backgroundColor: "#ECFDF5" }]}>
                <Ionicons name="lock-closed" size={18} color="#059669" />
              </View>
              <View style={styles.securityInfo}>
                <Text style={styles.securityTitle} allowFontScaling>
                  Local Database Encryption
                </Text>
                <Text style={styles.securitySub} allowFontScaling>
                  SQLite database encrypted with AES-256 SQLCipher using hardware-backed cryptographic keys.
                </Text>
              </View>
            </View>
            <View style={styles.divider} />

            <View style={styles.securityItem}>
              <View style={[styles.iconContainer, { backgroundColor: "#F0F9FF" }]}>
                <Ionicons name="shield-checkmark" size={18} color="#0284C7" />
              </View>
              <View style={styles.securityInfo}>
                <Text style={styles.securityTitle} allowFontScaling>
                  Keycloak OIDC Session
                </Text>
                <Text style={styles.securitySub} allowFontScaling>
                  Cryptographic bearer tokens protected in secure Keychain / Keystore storage with automatic refresh.
                </Text>
              </View>
            </View>
            <View style={styles.divider} />

            <View style={styles.securityItem}>
              <View style={[styles.iconContainer, { backgroundColor: "#F5F3FF" }]}>
                <Ionicons name="git-network-outline" size={18} color="#7C3AED" />
              </View>
              <View style={styles.securityInfo}>
                <Text style={styles.securityTitle} allowFontScaling>
                  Multi-Tenant Row-Level Security
                </Text>
                <Text style={styles.securitySub} allowFontScaling>
                  Strict facility isolation ensures your health observations and records never cross tenant boundaries.
                </Text>
              </View>
            </View>
          </View>

          {/* Sign out action */}
          <TouchableOpacity
            style={styles.signOutBtn}
            onPress={() => {
              onClose();
              onSignOut();
            }}
            accessibilityRole="button"
            accessibilityLabel="Sign out of account"
            activeOpacity={0.7}
          >
            <Ionicons name="log-out-outline" size={18} color="#DC2626" style={{ marginRight: 8 }} />
            <Text style={styles.signOutText} allowFontScaling>
              Sign Out of Account
            </Text>
          </TouchableOpacity>

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
  card: {
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
  sectionHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: spacing.sm,
  },
  sectionIconBox: {
    width: 28,
    height: 28,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  cardHeader: {
    fontSize: 11,
    color: "#64748B",
    fontWeight: "700",
    letterSpacing: 1,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.xs + 2,
  },
  divider: {
    height: 1,
    backgroundColor: "#F1F5F9",
    marginVertical: 4,
  },
  label: {
    fontSize: 13,
    color: "#64748B",
    fontWeight: "500",
  },
  uhidBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  uhidText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#0D9488",
  },
  monoBadge: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  valMono: {
    fontSize: 11,
    color: "#0F172A",
    fontFamily: "monospace",
    fontWeight: "600",
  },
  rolePill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#ECFDF5",
    borderWidth: 1,
    borderColor: "#A7F3D0",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  roleText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#059669",
    letterSpacing: 0.4,
  },
  securityItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingVertical: spacing.xs + 2,
    gap: spacing.sm + 2,
  },
  iconContainer: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  securityInfo: {
    flex: 1,
  },
  securityTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0F172A",
    marginBottom: 2,
  },
  securitySub: {
    fontSize: 11,
    color: "#64748B",
    lineHeight: 16,
  },
  signOutBtn: {
    flexDirection: "row",
    backgroundColor: "#FEF2F2",
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#FECACA",
    minHeight: 48,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.xs,
  },
  signOutText: {
    color: "#DC2626",
    fontSize: 14,
    fontWeight: "700",
  },
});
