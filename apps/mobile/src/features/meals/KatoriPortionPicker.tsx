import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../../theming/tokens";
import {
  KATORI_PORTION_LABELS,
  KATORI_VOLUMES,
  type KatoriVolumeMl,
} from "../../services/schemas/meals";

/**
 * Consistent clinical palettes for the logbook (anchored to design tokens).
 */
const palette = {
  teal600: "#0D9488",
  tealBg: "#F0FDFA",
  tealBorder: "#A7F3D2",
  ink: "#0F172A",
  body: "#334155",
  muted: "#64748B",
  border: "rgba(15, 23, 42, 0.07)",
  hairline: "#EEF2F7",
} as const;

export type KatoriPortionPickerProps = {
  selectedVolume: KatoriVolumeMl | null;
  onSelectVolume: (volume: KatoriVolumeMl) => void;
  quantity: number;
  onChangeQuantity: (quantity: number) => void;
  disabled?: boolean;
  testID?: string;
};

const QUANTITY_PRESETS = [0.5, 1.0, 1.5, 2.0];

export function KatoriPortionPicker({
  selectedVolume,
  onSelectVolume,
  quantity,
  onChangeQuantity,
  disabled = false,
  testID,
}: KatoriPortionPickerProps) {
  return (
    <View style={styles.container} testID={testID}>
      <Text style={styles.sectionTitle} allowFontScaling>
        Katori Portion Size
      </Text>
      <Text style={styles.caption} allowFontScaling>
        Select household katori volumetric size:
      </Text>

      <View style={styles.volumeRow}>
        {KATORI_VOLUMES.map((vol) => {
          const isSelected = selectedVolume === vol;
          const label = KATORI_PORTION_LABELS[vol];
          return (
            <Pressable
              key={vol}
              onPress={() => onSelectVolume(vol)}
              disabled={disabled}
              accessible
              accessibilityRole="radio"
              accessibilityLabel={label}
              accessibilityState={{ selected: isSelected, disabled }}
              style={({ pressed }) => [
                styles.volumeCard,
                isSelected ? styles.volumeCardSelected : null,
                pressed ? styles.pressed : null,
                disabled ? styles.disabled : null,
              ]}
            >
              <Text
                style={[
                  styles.volumeCardText,
                  isSelected ? styles.volumeCardTextSelected : null,
                ]}
                allowFontScaling
              >
                {label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <Text style={styles.subTitle} allowFontScaling>
        Quantity (Katoris)
      </Text>
      <View style={styles.quantityRow}>
        {QUANTITY_PRESETS.map((q) => {
          const isSelected = Math.abs(quantity - q) < 0.01;
          return (
            <Pressable
              key={q}
              onPress={() => onChangeQuantity(q)}
              disabled={disabled}
              accessible
              accessibilityRole="radio"
              accessibilityLabel={`${q} katori`}
              accessibilityState={{ selected: isSelected, disabled }}
              style={({ pressed }) => [
                styles.quantityChip,
                isSelected ? styles.quantityChipSelected : null,
                pressed ? styles.pressed : null,
                disabled ? styles.disabled : null,
              ]}
            >
              <Text
                style={[
                  styles.quantityChipText,
                  isSelected ? styles.quantityChipTextSelected : null,
                ]}
                allowFontScaling
              >
                {q}x
              </Text>
            </Pressable>
          );
        })}

        <View style={styles.stepperContainer}>
          <Pressable
            onPress={() => onChangeQuantity(Math.max(0.5, Math.round((quantity - 0.5) * 10) / 10))}
            disabled={disabled || quantity <= 0.5}
            accessible
            accessibilityRole="button"
            accessibilityLabel="Decrease quantity"
            style={({ pressed }) => [
              styles.stepperBtn,
              pressed ? styles.pressed : null,
              (disabled || quantity <= 0.5) ? styles.disabled : null,
            ]}
          >
            <Text style={styles.stepperBtnText}>−</Text>
          </Pressable>

          <Text style={styles.quantityValueText} allowFontScaling>
            {quantity.toFixed(1)}
          </Text>

          <Pressable
            onPress={() => onChangeQuantity(Math.min(10, Math.round((quantity + 0.5) * 10) / 10))}
            disabled={disabled || quantity >= 10}
            accessible
            accessibilityRole="button"
            accessibilityLabel="Increase quantity"
            style={({ pressed }) => [
              styles.stepperBtn,
              pressed ? styles.pressed : null,
              (disabled || quantity >= 10) ? styles.disabled : null,
            ]}
          >
            <Text style={styles.stepperBtnText}>+</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.sm,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: palette.ink,
    letterSpacing: -0.3,
  },
  caption: {
    fontSize: 11,
    color: palette.muted,
  },
  subTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: palette.body,
  },
  volumeRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  volumeCard: {
    flex: 1,
    minHeight: 54,
    padding: spacing.sm,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 1,
  },
  volumeCardSelected: {
    borderColor: colors.primary,
    borderWidth: 1.5,
    backgroundColor: palette.tealBg,
    shadowOpacity: 0.08,
    elevation: 2,
  },
  volumeCardText: {
    fontSize: 13,
    fontWeight: "600",
    color: palette.body,
    textAlign: "center",
  },
  volumeCardTextSelected: {
    color: colors.primary,
    fontWeight: "800",
  },
  quantityRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    flexWrap: "wrap",
  },
  quantityChip: {
    minHeight: 36,
    minWidth: 48,
    paddingHorizontal: spacing.sm,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  quantityChipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  quantityChipText: {
    fontSize: 13,
    fontWeight: "600",
    color: palette.body,
  },
  quantityChipTextSelected: {
    color: colors.textOnPrimary,
    fontWeight: "800",
  },
  stepperContainer: {
    flexDirection: "row",
    alignItems: "center",
    marginLeft: "auto",
    gap: spacing.xs,
  },
  stepperBtn: {
    width: 36,
    height: 36,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  stepperBtnText: {
    fontSize: 18,
    fontWeight: "600",
    color: palette.ink,
  },
  quantityValueText: {
    fontSize: 16,
    fontWeight: "700",
    color: palette.ink,
    minWidth: 32,
    textAlign: "center",
  },
  pressed: {
    opacity: 0.7,
  },
  disabled: {
    opacity: 0.4,
  },
});