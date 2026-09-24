import React, { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../auth/AuthProvider";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { Divider } from "../../components/primitives/Divider";
import { Button } from "../../components/primitives/Button";
import { EmptyState } from "../../components/primitives/EmptyState";
import { colors, radii, spacing } from "../../theming/tokens";
import { FoodItemSelector } from "./FoodItemSelector";
import { KatoriPortionPicker } from "./KatoriPortionPicker";
import { MealDraftSummary } from "./MealDraftSummary";
import { MealTimeline } from "./MealTimeline";
import { useLogMeal } from "./useLogMeal";
import { useConfirmMeal } from "./useConfirmMeal";
import { usePatientMeals } from "./usePatientMeals";
import type { FoodItem } from "./types";
import type { KatoriVolumeMl, LogMealResponse } from "../../services/schemas/meals";
import type { ApiErrorDetails } from "../../services/api/errors";
import type { AnalyzeMealPhotoAiResponse } from "../../services/schemas/ai";

export type PatientMealScreenProps = {
  patientId?: string;
  onBack?: () => void;
  testID?: string;
};

/**
 * Consistent clinical palettes for the logbook (anchored to design tokens).
 */
const palette = {
  teal700: "#0F766E",
  teal600: "#0D9488",
  amber: "#FBBF24",
  green: "#6EE7B7",
  body: "#334155",
  border: "rgba(15, 23, 42, 0.07)",
} as const;

export function PatientMealScreen({
  patientId: propPatientId,
  onBack,
  testID,
}: PatientMealScreenProps) {
  const { state } = useAuth();
  const [selectedFoodKey, setSelectedFoodKey] = useState<string | null>(null);
  const [description, setDescription] = useState<string>("");
  const [selectedVolume, setSelectedVolume] = useState<KatoriVolumeMl | null>(220);
  const [quantity, setQuantity] = useState<number>(1.0);
  const [validationError, setValidationError] = useState<string | null>(null);

  const [activeDraft, setActiveDraft] = useState<LogMealResponse | null>(null);
  const [draftDescription, setDraftDescription] = useState<string>("");

  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const authUser = state.name === "authenticated" ? state.user : null;
  const isPatientRole = authUser?.role === "Patient";
  const resolvedPatientId = propPatientId ?? authUser?.patient_id ?? null;

  // Meal history feed
  const feed = usePatientMeals(resolvedPatientId, {
    enabled: isPatientRole && Boolean(resolvedPatientId),
  });

  // Draft mutation hook
  const logMeal = useLogMeal({
    patientId: resolvedPatientId,
    onSuccess: (draftResponse) => {
      setErrorMessage(null);
      setValidationError(null);
      if ((draftResponse as any).sync_status === "SAVED_LOCALLY") {
        setSuccessMessage("Meal draft saved on this device (Waiting to sync).");
        setActiveDraft(null);
        setDescription("");
        setSelectedFoodKey(null);
      } else {
        setActiveDraft(draftResponse);
        setDraftDescription(description);
      }
    },
    onError: (error: unknown) => {
      setSuccessMessage(null);
      handleApiError(error, "Failed to create meal draft");
    },
  });

  // Confirm mutation hook
  const confirmMeal = useConfirmMeal({
    onSuccess: () => {
      setErrorMessage(null);
      // Server response is authoritative: only display confirmation on success
      setSuccessMessage("Meal confirmed successfully.");
      setActiveDraft(null);
      setDraftDescription("");
      setDescription("");
      setSelectedFoodKey(null);
      setSelectedVolume(220);
      setQuantity(1.0);
      void feed.refetch();
    },
    onError: (error: unknown) => {
      setSuccessMessage(null);
      handleApiError(error, "Failed to confirm meal");
    },
  });

  function handleApiError(error: unknown, fallbackMessage: string) {
    const apiError = error as ApiErrorDetails | undefined;
    if (apiError?.httpStatus === 403) {
      setErrorMessage("Access denied. Your patient record is inactive or access has been revoked.");
    } else if (apiError?.httpStatus === 404) {
      setErrorMessage("Meal observation not found or no longer available.");
    } else if (apiError?.httpStatus === 409) {
      if (apiError.message.toLowerCase().includes("phone")) {
        setErrorMessage("A verified phone number is required on your patient profile to confirm meals.");
      } else {
        setErrorMessage("This meal has already been confirmed or updated.");
      }
    } else if (apiError?.httpStatus === 422) {
      setErrorMessage("Invalid meal data submitted. Please check the description and portion.");
    } else if (apiError?.httpStatus === 429) {
      const retry = apiError.retryAfterSeconds;
      setErrorMessage(
        retry
          ? `Too many requests. Please wait ${retry} seconds before trying again.`
          : "Too many requests. Please wait a moment before trying again."
      );
    } else if (apiError?.kind === "NETWORK_ERROR") {
      setErrorMessage("Unable to connect. Your meal has not been recorded.");
    } else {
      setErrorMessage(apiError?.message ?? fallbackMessage);
    }
  }

  const handleSelectFood = (food: FoodItem) => {
    setSelectedFoodKey(food.key);
    if (!description.trim()) {
      setDescription(food.label);
    } else if (!description.toLowerCase().includes(food.label.toLowerCase())) {
      setDescription(`${description}, ${food.label}`);
    }
    setValidationError(null);
  };

  const handleDraftSubmit = () => {
    setSuccessMessage(null);
    setErrorMessage(null);

    const trimmed = description.trim();
    if (!trimmed) {
      setValidationError("Please enter a description for your meal.");
      return;
    }

    setValidationError(null);

    const portion =
      selectedVolume && selectedFoodKey
        ? {
            food_key: selectedFoodKey,
            katori_volume_ml: selectedVolume,
            quantity,
          }
        : selectedVolume
          ? {
              food_key: trimmed.toLowerCase().split(/\s+/)[0] || "meal",
              katori_volume_ml: selectedVolume,
              quantity,
            }
          : null;

    logMeal.mutate({
      description: trimmed,
      portion,
    });
  };

  const handleConfirmDraft = () => {
    if (!activeDraft) return;
    setSuccessMessage(null);
    setErrorMessage(null);

    confirmMeal.mutate({
      mealObservationId: activeDraft.meal_observation_id,
      patientId: resolvedPatientId,
    });
  };

  // Role Guard
  if (!isPatientRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Meal Log"
          onBack={onBack}
          leadingLabel={onBack ? "Back" : undefined}
        />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="The meal logging screen is only available in Patient mode."
          />
          {onBack ? (
            <Button label="Return to Main Menu" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  // Identity Guard
  if (!resolvedPatientId) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Meal Log"
          onBack={onBack}
          leadingLabel={onBack ? "Back" : undefined}
        />
        <View style={styles.content}>
          <View testID="unlinked-patient-state">
            <EmptyState
              title="Account Linking Required"
              message="Your account is not yet linked to a patient profile. Please contact your clinic coordinator to activate your patient record."
            />
          </View>
          {onBack ? (
            <Button label="Return to Main Menu" variant="outline" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  // Summary metrics derived from the feed
  const meals = feed.meals ?? [];
  const totalCount = meals.length;
  const confirmedCount = meals.filter((m) => m.confirmed === true).length;
  const pendingCount = totalCount - confirmedCount;

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Meal Logbook"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
        actions={
          <View style={styles.headerProtocolPill}>
            <View style={styles.headerProtocolDot} />
            <Text style={styles.headerProtocolText} allowFontScaling>
              Plate Log
            </Text>
          </View>
        }
      />

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {successMessage ? (
          <AlertBanner
            tone="success"
            title="Confirmed"
            message={successMessage}
          />
        ) : null}

        {errorMessage ? (
          <AlertBanner
            tone="critical"
            title="Request Failed"
            message={errorMessage}
          />
        ) : null}

        {/* Nutrition Summary Hero (When meals exist) */}
        {totalCount > 0 ? (
          <View style={styles.summaryCard}>
            <View style={styles.summaryDeco} pointerEvents="none" />
            <View style={styles.metricsRow}>
              <View style={styles.metricItem}>
                <View style={styles.metricLabelRow}>
                  <Ionicons name="restaurant" size={11} color="rgba(255,255,255,0.65)" />
                  <Text style={styles.metricLabel} allowFontScaling>
                    Total Meals
                  </Text>
                </View>
                <View style={styles.metricValueRow}>
                  <Text style={styles.metricValue} allowFontScaling>
                    {totalCount}
                  </Text>
                </View>
              </View>

              <View style={styles.metricDivider} />

              <View style={styles.metricItem}>
                <View style={styles.metricLabelRow}>
                  <Ionicons name="checkmark-circle" size={11} color={palette.green} />
                  <Text style={styles.metricLabel} allowFontScaling>
                    Confirmed
                  </Text>
                </View>
                <View style={styles.metricValueRow}>
                  <Text style={[styles.metricValue, { color: palette.green }]} allowFontScaling>
                    {confirmedCount}
                  </Text>
                </View>
              </View>

              <View style={styles.metricDivider} />

              <View style={styles.metricItem}>
                <View style={styles.metricLabelRow}>
                  <Ionicons name="time" size={11} color={palette.amber} />
                  <Text style={styles.metricLabel} allowFontScaling>
                    Pending
                  </Text>
                </View>
                <View style={styles.metricValueRow}>
                  <Text style={[styles.metricValue, { color: palette.amber }]} allowFontScaling>
                    {pendingCount}
                  </Text>
                </View>
              </View>
            </View>

            <View style={styles.summaryStatusRow}>
              <Ionicons
                name={pendingCount > 0 ? "time" : "shield-checkmark"}
                size={13}
                color={pendingCount > 0 ? palette.amber : palette.green}
              />
              <Text style={styles.summaryStatusText} allowFontScaling>
                {pendingCount > 0
                  ? `${pendingCount} ${pendingCount === 1 ? "meal" : "meals"} awaiting confirmation`
                  : "All meals confirmed"}
              </Text>
            </View>
          </View>
        ) : null}

        {activeDraft ? (
          <MealDraftSummary
            draft={activeDraft}
            description={draftDescription}
            onConfirm={handleConfirmDraft}
            onDiscard={() => {
              setActiveDraft(null);
              setDraftDescription("");
            }}
            isConfirming={confirmMeal.isPending}
            testID="meal-draft-summary"
          />
        ) : (
          <View style={styles.formCard} testID="patient-meal-form">
            <FoodItemSelector
              selectedFoodKey={selectedFoodKey}
              onSelectFood={handleSelectFood}
              description={description}
              onChangeDescription={(text) => {
                setDescription(text);
                if (validationError) setValidationError(null);
              }}
              error={validationError}
              patientName={authUser?.name ?? ""}
              onDirectLog={async (analysis) => {
                const mealDesc = (analysis.description || description || "Photo Analyzed Meal").trim();
                setDescription(mealDesc);
                await logMeal.mutateAsync({
                  description: mealDesc,
                  portion: {
                    food_key: selectedFoodKey ?? "thali",
                    katori_volume_ml: selectedVolume ?? 220,
                    quantity: quantity > 0 ? quantity : 1.0,
                  },
                });
              }}
              testID="food-item-selector"
            />

            <Divider />

            <KatoriPortionPicker
              selectedVolume={selectedVolume}
              onSelectVolume={setSelectedVolume}
              quantity={quantity}
              onChangeQuantity={setQuantity}
              disabled={logMeal.isPending}
              testID="katori-portion-picker"
            />

            <Button
              label={logMeal.isPending ? "Creating Draft…" : "Log Meal Draft"}
              variant="primary"
              onPress={handleDraftSubmit}
              disabled={logMeal.isPending}
              accessibilityHint="Creates an unconfirmed meal draft on the server"
            />
          </View>
        )}

        <Divider label="Meal History" />

        <MealTimeline
          meals={feed.meals}
          isLoading={feed.isLoading}
          isError={feed.isError}
          onRetry={() => feed.refetch()}
          testID="patient-meal-timeline"
        />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    gap: spacing.md,
  },
  scrollContent: {
    padding: spacing.md,
    gap: spacing.sm,
    paddingBottom: spacing.xxl + 20,
  },
  headerProtocolPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: palette.border,
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderRadius: radii.pill,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1,
  },
  headerProtocolDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: palette.teal600,
  },
  headerProtocolText: {
    fontSize: 10,
    fontWeight: "700",
    color: palette.teal700,
    letterSpacing: 0.2,
  },
  summaryCard: {
    backgroundColor: colors.primary,
    borderRadius: 20,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    gap: 12,
    overflow: "hidden",
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.22,
    shadowRadius: 20,
    elevation: 5,
  },
  summaryDeco: {
    position: "absolute",
    top: -70,
    right: -50,
    width: 170,
    height: 170,
    borderRadius: 85,
    backgroundColor: "rgba(255, 255, 255, 0.07)",
  },
  metricsRow: {
    flexDirection: "row",
    alignItems: "stretch",
  },
  metricItem: {
    flex: 1,
    alignItems: "center",
    gap: 4,
  },
  metricLabelRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  metricLabel: {
    fontSize: 9,
    fontWeight: "800",
    color: "rgba(255, 255, 255, 0.66)",
    textTransform: "uppercase",
    letterSpacing: 0.8,
  },
  metricValueRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 3,
  },
  metricValue: {
    fontSize: 21,
    fontWeight: "800",
    color: "#FFFFFF",
    letterSpacing: -0.4,
  },
  metricDivider: {
    width: 1,
    alignSelf: "stretch",
    backgroundColor: "rgba(255, 255, 255, 0.16)",
  },
  summaryStatusRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(255, 255, 255, 0.08)",
    borderRadius: radii.lg,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  summaryStatusText: {
    flex: 1,
    fontSize: 11,
    fontWeight: "600",
    color: "#FFFFFF",
  },
  formCard: {
    padding: spacing.md + 2,
    backgroundColor: colors.surface,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: palette.border,
    gap: spacing.md,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.06,
    shadowRadius: 22,
    elevation: 3,
  },
});