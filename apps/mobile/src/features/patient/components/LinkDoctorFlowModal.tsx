import React, { useState } from "react";
import {
  Modal,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { CameraView, useCameraPermissions } from "expo-camera";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { useTranslation } from "../../../i18n/i18n";
import { parseDoctorAccountQrValue, type DoctorQrAccount } from "../../doctor/doctorQr";

export type LinkDoctorFlowModalProps = {
  visible: boolean;
  onClose: () => void;
  onLinkRequested?: (account: DoctorQrAccount) => void;
};

export function LinkDoctorFlowModal({
  visible,
  onClose,
  onLinkRequested,
}: LinkDoctorFlowModalProps) {
  const { t } = useTranslation();
  const [qrValue, setQrValue] = useState("");
  const [error, setError] = useState<string | null>(null   );
  const [resolvedAccount, setResolvedAccount] = useState<DoctorQrAccount | null>(null);
  const [entryMode, setEntryMode] = useState<"scan" | "paste">("scan");
  const [permission, requestPermission] = useCameraPermissions();

  const handleBarcodeScanned = (barcode: { data: string }) => {
    if (resolvedAccount) {
      return;
    }

    const { data } = barcode;
    setQrValue(data);
    setError(null);

    const account = parseDoctorAccountQrValue(data);
    if (account) {
      setResolvedAccount(account);
    } else {
      setResolvedAccount(null);
      setError(t("linkDoctor.invalidQrValue") ?? "That does not look like a doctor QR value.");
    }
  };

  const handlePaste = (value: string) => {
    setQrValue(value);
    setError(null);

    const account = parseDoctorAccountQrValue(value);
    if (account) {
      setResolvedAccount(account);
    } else {
      setResolvedAccount(null);
      setError(t("linkDoctor.invalidQrValue") ?? "That does not look like a doctor QR value.");
    }
  };

  const handleLinkPress = () => {
    if (resolvedAccount) {
      onLinkRequested?.(resolvedAccount);
    }
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <View style={styles.headerRow}>
            <Text style={styles.title} allowFontScaling>
              {t("linkDoctor.title")}
            </Text>
            <TouchableOpacity onPress={onClose} accessibilityRole="button" activeOpacity={0.7}>
              <Ionicons name="close" size={22} color="#64748B" />
            </TouchableOpacity>
          </View>

          <Text style={styles.description} allowFontScaling>
            {t("linkDoctor.description")}
          </Text>

          <View style={styles.inputRow}>
            <Ionicons name="qr-code-outline" size={18} color="#64748B" />
            <TextInput
              style={styles.input}
              value={qrValue}
              onChangeText={handlePaste}
              placeholder="thali://doctor?account=…"
              placeholderTextColor="#94A3B8"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              allowFontScaling
            />
          </View>

          {error ? (
            <Text style={styles.errorText} allowFontScaling>
              {error}
            </Text>
          ) : null}

          {resolvedAccount ? (
            <View style={styles.resolvedRow}>
              <Ionicons name="person-circle-outline" size={18} color="#0D9488" />
              <Text style={styles.resolvedText} allowFontScaling>
                {resolvedAccount.accountId}
              </Text>
            </View>
          ) : null}

          <TouchableOpacity
            style={[styles.linkButton, !resolvedAccount && styles.linkButtonDisabled]}
            onPress={handleLinkPress}
            disabled={!resolvedAccount}
            accessibilityRole="button"
            activeOpacity={0.7}
          >
            <Ionicons name="medkit-outline" size={18} color="#FFFFFF" />
            <Text style={styles.linkButtonText} allowFontScaling>
              {t("linkDoctor.linkButton")}
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.55)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.lg,
  },
  card: {
    width: "100%",
    maxWidth: 400,
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.lg,
    gap: spacing.md,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: "700",
    color: "#0F172A",
  },
  description: {
    fontSize: typography.fontSize.body,
    color: "#64748B",
    lineHeight: 20,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: "#F8FAFC",
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    paddingHorizontal: spacing.md,
  },
  input: {
    flex: 1,
    paddingVertical: spacing.sm,
    fontSize: 13,
    color: "#0F172A",
  },
  errorText: {
    fontSize: 12,
    color: "#DC2626",
  },
  resolvedRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: "#F0FDFA",
    borderRadius: radii.md,
    padding: spacing.sm,
  },
  resolvedText: {
    fontSize: 13,
    color: "#0F766E",
    fontWeight: "600",
  },
  linkButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    backgroundColor: colors.primary,
    borderRadius: radii.pill,
    paddingVertical: spacing.sm,
    minHeight: touchTarget.min,
  },
  linkButtonDisabled: {
    opacity: 0.5,
  },
  linkButtonText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "700",
  },
});
