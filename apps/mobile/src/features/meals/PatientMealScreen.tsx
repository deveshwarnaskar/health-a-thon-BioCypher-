import React, { useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { useAuth } from "../../auth/AuthProvider";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { Divider } from "../../components/primitives/Divider";
import { Button } from "../../components/primitives/Button";
import { EmptyState } from "../../components/primitives/EmptyState";
import { colors, spacing } from "../../theming/tokens";
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

export type PatientMealScreenProps = {
  patientId?: string;
  onBack?: () => void;
  testID?: string;
};

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

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Meal Logbook"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
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
          <View style={styles.formContainer} testID="patient-meal-form">
            <FoodItemSelector
              selectedFoodKey={selectedFoodKey}
              onSelectFood={handleSelectFood}
              description={description}
              onChangeDescription={(text) => {
                setDescription(text);
                if (validationError) setValidationError(null);
              }}
              error={validationError}
              testID="food-item-selector"
            />

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
    gap: spacing.md,
    paddingBottom: spacing.xxl,
  },
  formContainer: {
    gap: spacing.md,
  },
});
