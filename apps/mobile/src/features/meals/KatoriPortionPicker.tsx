import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import {
  KATORI_PORTION_LABELS,
  KATORI_VOLUMES,
  type KatoriVolumeMl,
} from "../../services/schemas/meals";

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
    fontSize: typography.fontSize.headline,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  caption: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
  },
  subTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "600",
    color: colors.textPrimary,
    marginTop: spacing.xs,
  },
  volumeRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  volumeCard: {
    flex: 1,
    minHeight: 56,
    padding: spacing.sm,
    borderRadius: radii.md,
    borderWidth: 2,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  volumeCardSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.surface,
    borderWidth: 2,
  },
  volumeCardText: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "500",
    color: colors.textPrimary,
    textAlign: "center",
  },
  volumeCardTextSelected: {
    color: colors.primary,
    fontWeight: "700",
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
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  quantityChipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  quantityChipText: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "500",
    color: colors.textPrimary,
  },
  quantityChipTextSelected: {
    color: colors.textOnPrimary,
    fontWeight: "700",
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
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  stepperBtnText: {
    fontSize: typography.fontSize.headline,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  quantityValueText: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
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
