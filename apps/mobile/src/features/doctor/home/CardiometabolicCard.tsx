import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { doctorPalette, doctorSoftShadow } from "../doctorDesign";
import { SectionHeader, HomeInlineState } from "./DoctorHomeBits";

export function CardiometabolicCard({
  isLoading,
  hasNumericData,
}: {
  isLoading?: boolean;
  hasNumericData?: boolean;
}) {
  return (
    <View style={styles.section}>
      <SectionHeader title="Cardiometabolic Health" viewAllLabel="Not found in this program yet" />
      <View style={styles.card}>
        <View style={styles.headerRow}>
          <View style={styles.headerIcon}>
            <Ionicons name="heart" size={14} color={doctorPalette.primary} />
          </View>
          <Text style={styles.headerTitle} allowFontScaling>
            BP · Lipids · Renal markers
          </Text>
        </View>
        {isLoading ? (
          <Text style={styles.loadingText} allowFontScaling>
            Loading cardiometabolic data…
          </Text>
        ) : !hasNumericData ? (
          <HomeInlineState
            icon="heart-outline"
            title="Cardiometabolic data not available"
            message="Blood pressure, lipid, kidney, and A1C lab values aren't mapped to this cohort yet. When labs are connected, this card will surface them here."
          />
        ) : (
          <Text style={styles.loadingText} allowFontScaling>
            Connected
          </Text>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: 12,
  },
  card: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 18,
    gap: 12,
    ...doctorSoftShadow,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  headerIcon: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontSize: 12,
    fontWeight: "800",
    color: doctorPalette.inkSecondary,
  },
  loadingText: {
    fontSize: 13,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
});