import React, { useState } from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { caregiverPalette, caregiverRadii, caregiverShadow } from "./caregiverDesign";
import { Button } from "../../components/primitives/Button";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { useLogMeal } from "../meals/useLogMeal";
import type { KatoriVolumeMl } from "../../services/schemas/meals";

export type CaregiverMealEntryFormProps = {
  patientId: string;
  onSuccess?: () => void;
  testID?: string;
};

const MEAL_TIMES = [
  { label: "Breakfast", icon: "sunny-outline" },
  { label: "Lunch", icon: "restaurant-outline" },
  { label: "Snack", icon: "cafe-outline" },
  { label: "Dinner", icon: "moon-outline" },
];

const PORTIONS: { label: string; volume: KatoriVolumeMl; desc: string; sizeMultiplier: number }[] = [
  { label: "Small", volume: 150, desc: "150 ml katori", sizeMultiplier: 0.8 },
  { label: "Medium", volume: 220, desc: "220 ml standard", sizeMultiplier: 1.0 },
  { label: "Large", volume: 350, desc: "350 ml full bowl", sizeMultiplier: 1.25 },
];

const QUICK_FOODS = [
  "2 Chapatis",
  "1 Katori Dal",
  "Bhindi Sabzi",
  "Steamed Rice",
  "Cucumber Salad",
  "Curd / Dahi",
  "Methi Thepla",
  "Khichdi",
];

export function CaregiverMealEntryForm({
  patientId,
  onSuccess,
  testID,
}: CaregiverMealEntryFormProps) {
  const [mealTime, setMealTime] = useState("Lunch");
  const [description, setDescription] = useState("");
  const [selectedPortion, setSelectedPortion] = useState<KatoriVolumeMl>(220);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const logMealMutation = useLogMeal({
    patientId,
    onSuccess: () => {
      setSuccessMessage(`Meal logged successfully for ${mealTime}.`);
      setDescription("");
      onSuccess?.();
    },
    onError: (err: any) => {
      setSuccessMessage(null);
      setErrorMessage(err?.message ?? "Unable to log meal. Please try again.");
    },
  });

  const handleAppendFood = (food: string) => {
    if (!description.trim()) {
      setDescription(food);
    } else {
      setDescription(`${description.trim()}, ${food}`);
    }
    if (errorMessage) setErrorMessage(null);
  };

  const handleSubmit = () => {
    if (!description.trim()) {
      setErrorMessage("Please enter what the patient ate.");
      return;
    }
    setSuccessMessage(null);
    setErrorMessage(null);

    const fullDescription = `${mealTime}: ${description.trim()}`;
    logMealMutation.mutate({
      description: fullDescription,
      portion: {
        food_key: "standard_meal",
        katori_volume_ml: selectedPortion,
        quantity: 1,
      },
    });
  };

  return (
    <View style={styles.card} testID={testID}>
      {/* Header */}
      <View style={styles.cardHeader}>
        <View style={styles.headerIcon}>
          <Ionicons name="restaurant" size={18} color={caregiverPalette.amberDark} />
        </View>
        <View style={styles.headerTitleCol}>
          <Text style={styles.cardTitle} allowFontScaling>
            Log Meal for Patient
          </Text>
          <Text style={styles.cardSubtitle} allowFontScaling>
            Record meal intake, timing, and portion size
          </Text>
        </View>
      </View>

      {successMessage ? (
        <AlertBanner tone="success" title="Meal Recorded" message={successMessage} />
      ) : null}

      {errorMessage ? (
        <AlertBanner tone="critical" title="Could Not Record Meal" message={errorMessage} />
      ) : null}

      {/* Meal Timing Pills */}
      <View style={styles.fieldGroup}>
        <Text style={styles.fieldLabel} allowFontScaling>
          Meal Type / Timing
        </Text>
        <View style={styles.mealTimeGrid}>
          {MEAL_TIMES.map((mt) => {
            const isSelected = mealTime === mt.label;
            return (
              <TouchableOpacity
                key={mt.label}
                style={[styles.mealTimeChip, isSelected && styles.mealTimeChipSelected]}
                onPress={() => setMealTime(mt.label)}
                activeOpacity={0.75}
                accessibilityRole="button"
                accessibilityLabel={mt.label}
              >
                <Ionicons
                  name={mt.icon as any}
                  size={15}
                  color={isSelected ? caregiverPalette.primary : caregiverPalette.muted}
                />
                <Text
                  style={[
                    styles.mealTimeText,
                    isSelected && styles.mealTimeTextSelected,
                  ]}
                  allowFontScaling
                >
                  {mt.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      {/* Meal Description Input */}
      <View style={styles.fieldGroup}>
        <View style={styles.labelRow}>
          <Text style={styles.fieldLabel} allowFontScaling>
            Meal Description / Foods Prepared
          </Text>
          <Text style={styles.fieldHint}>Tap items below or type</Text>
        </View>

        <TextInput
          style={styles.textInput}
          value={description}
          onChangeText={(val) => {
            setDescription(val);
            if (errorMessage) setErrorMessage(null);
          }}
          placeholder="e.g. 2 chapatis, dal tadka, bhindi sabzi, cucumber salad"
          placeholderTextColor={caregiverPalette.subtle}
          multiline
          numberOfLines={2}
          editable={!logMealMutation.isPending}
        />

        {/* Quick Food Suggestions */}
        <View style={styles.quickFoodContainer}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.quickFoodScroll}
          >
            {QUICK_FOODS.map((food) => (
              <TouchableOpacity
                key={food}
                style={styles.quickFoodChip}
                onPress={() => handleAppendFood(food)}
                activeOpacity={0.7}
              >
                <Ionicons name="add" size={12} color={caregiverPalette.primary} />
                <Text style={styles.quickFoodText} allowFontScaling>
                  {food}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      </View>

      {/* Scaled Visual Portion Size Selection */}
      <View style={styles.fieldGroup}>
        <Text style={styles.fieldLabel} allowFontScaling>
          Serving / Portion (Katori size)
        </Text>
        <View style={styles.portionRow}>
          {PORTIONS.map((p) => {
            const isSelected = selectedPortion === p.volume;
            return (
              <TouchableOpacity
                key={p.volume}
                style={[styles.portionCard, isSelected && styles.portionCardSelected]}
                onPress={() => setSelectedPortion(p.volume)}
                activeOpacity={0.8}
                accessibilityRole="button"
                accessibilityLabel={`${p.label} portion, ${p.desc}`}
              >
                {/* Visual Scaled Katori Graphic */}
                <View style={styles.katoriVisualContainer}>
                  <View
                    style={[
                      styles.katoriBowl,
                      {
                        width: 32 * p.sizeMultiplier,
                        height: 20 * p.sizeMultiplier,
                        backgroundColor: isSelected
                          ? caregiverPalette.amberSoft
                          : caregiverPalette.surfaceSoft,
                        borderColor: isSelected
                          ? caregiverPalette.amber
                          : caregiverPalette.borderHighlight,
                      },
                    ]}
                  >
                    <View
                      style={[
                        styles.katoriFill,
                        {
                          height: 12 * p.sizeMultiplier,
                          backgroundColor: isSelected
                            ? caregiverPalette.amber
                            : caregiverPalette.borderHighlight,
                        },
                      ]}
                    />
                  </View>
                </View>

                <Text
                  style={[
                    styles.portionTitle,
                    isSelected && styles.portionTitleSelected,
                  ]}
                  allowFontScaling
                >
                  {p.label}
                </Text>
                <Text style={styles.portionDesc} allowFontScaling>
                  {p.desc}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      <Button
        label={logMealMutation.isPending ? "Recording Meal…" : "Record Meal on Patient's Behalf"}
        variant="primary"
        onPress={handleSubmit}
        disabled={logMealMutation.isPending || !description.trim()}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: caregiverPalette.surface,
    borderRadius: caregiverRadii.lg,
    padding: 16,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    gap: 14,
    ...caregiverShadow.card,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  headerIcon: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: caregiverPalette.amberSoft,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: caregiverPalette.amberBorder,
  },
  headerTitleCol: {
    flex: 1,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: caregiverPalette.ink,
  },
  cardSubtitle: {
    fontSize: 11,
    color: caregiverPalette.muted,
    marginTop: 1,
  },
  fieldGroup: {
    gap: 6,
  },
  labelRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  fieldLabel: {
    fontSize: 12,
    fontWeight: "700",
    color: caregiverPalette.inkSecondary,
  },
  fieldHint: {
    fontSize: 11,
    color: caregiverPalette.muted,
  },
  mealTimeGrid: {
    flexDirection: "row",
    gap: 6,
  },
  mealTimeChip: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 5,
    paddingVertical: 9,
    borderRadius: caregiverRadii.md,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    backgroundColor: caregiverPalette.surfaceMuted,
  },
  mealTimeChipSelected: {
    borderColor: caregiverPalette.primary,
    backgroundColor: caregiverPalette.primaryLight,
  },
  mealTimeText: {
    fontSize: 11,
    fontWeight: "600",
    color: caregiverPalette.muted,
  },
  mealTimeTextSelected: {
    color: caregiverPalette.primary,
    fontWeight: "800",
  },
  textInput: {
    borderWidth: 1,
    borderColor: caregiverPalette.borderHighlight,
    borderRadius: caregiverRadii.md,
    backgroundColor: caregiverPalette.surfaceMuted,
    padding: 12,
    fontSize: 13,
    color: caregiverPalette.ink,
    minHeight: 72,
    textAlignVertical: "top",
  },
  quickFoodContainer: {
    marginTop: 2,
  },
  quickFoodScroll: {
    gap: 6,
  },
  quickFoodChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: caregiverPalette.surfaceSoft,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: caregiverRadii.pill,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
  },
  quickFoodText: {
    fontSize: 11,
    fontWeight: "600",
    color: caregiverPalette.inkSecondary,
  },
  portionRow: {
    flexDirection: "row",
    gap: 8,
  },
  portionCard: {
    flex: 1,
    padding: 10,
    borderRadius: caregiverRadii.md,
    borderWidth: 1,
    borderColor: caregiverPalette.border,
    backgroundColor: caregiverPalette.surfaceMuted,
    alignItems: "center",
    gap: 4,
  },
  portionCardSelected: {
    borderColor: caregiverPalette.amber,
    backgroundColor: caregiverPalette.amberSoft,
    borderWidth: 1.5,
  },
  katoriVisualContainer: {
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  katoriBowl: {
    borderBottomLeftRadius: 16,
    borderBottomRightRadius: 16,
    borderWidth: 1.5,
    overflow: "hidden",
    justifyContent: "flex-end",
  },
  katoriFill: {
    width: "100%",
    borderBottomLeftRadius: 14,
    borderBottomRightRadius: 14,
    opacity: 0.8,
  },
  portionTitle: {
    fontSize: 12,
    fontWeight: "800",
    color: caregiverPalette.ink,
  },
  portionTitleSelected: {
    color: caregiverPalette.amberDark,
  },
  portionDesc: {
    fontSize: 10,
    color: caregiverPalette.muted,
  },
});
