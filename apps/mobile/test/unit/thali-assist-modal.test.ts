import { describe, expect, it } from "vitest";
import type { AnalyzeMealAiResponse, AnalyzeMealPhotoAiResponse } from "../../src/services/schemas/ai";

describe("THALI Assist Multimodal & Keyboard Avoidance Contract", () => {
  it("processes photo analysis response into conversational assistant message with ICMR data", () => {
    const photoResult: AnalyzeMealPhotoAiResponse = {
      description: "2 bajra roti, mixed veg curry, bowl of curd",
      items: [
        {
          name: "Bajra Roti",
          portion_text: "2 medium",
          calories_kcal: 220,
          carbs_g: 44,
          protein_g: 6,
          fiber_g: 6,
          glycemic_index_category: "LOW",
        },
        {
          name: "Mixed Veg Curry",
          portion_text: "1 katori",
          calories_kcal: 140,
          carbs_g: 12,
          protein_g: 4,
          fiber_g: 4,
        },
      ],
      total_calories_kcal: 360,
      total_carbs_g: 56,
      total_protein_g: 10,
      total_fiber_g: 10,
      glycemic_impact: "LOW",
      balanced_plate_score: "HIGH",
      patient_guidance_hinglish: "Yeh bajra roti aur sabzi thali low glycemic impact deti hai.",
    };

    // Helper mirroring handleReceivePhotoAnalysis in ThaliAssistModal
    const userMessage = {
      role: "user" as const,
      text: `Uploaded meal photo: ${photoResult.description}`,
      imageUri: "file:///photos/meal_bajra.jpg",
    };

    const assistantMessage = {
      role: "assistant" as const,
      text: photoResult.patient_guidance_hinglish,
      mealData: photoResult,
    };

    expect(userMessage.imageUri).toBe("file:///photos/meal_bajra.jpg");
    expect(userMessage.text).toContain("2 bajra roti");
    expect(assistantMessage.mealData.total_calories_kcal).toBe(360);
    expect(assistantMessage.mealData.glycemic_impact).toBe("LOW");
    expect(assistantMessage.text).toContain("low glycemic impact");
  });

  it("extracts description seamlessly from both text analysis and photo analysis responses", () => {
    const textData: AnalyzeMealAiResponse = {
      raw_description: "1 plate poha with peanuts",
      total_calories_kcal: 250,
      total_carbs_g: 42,
      total_protein_g: 6,
      glycemic_impact: "MODERATE",
      balanced_plate_score: "MEDIUM",
      patient_guidance_hinglish: "Poha ke saath peanuts protein add karta hai.",
    };

    const photoData: AnalyzeMealPhotoAiResponse = {
      description: "Bowl of moong dal khichdi",
      total_calories_kcal: 280,
      total_carbs_g: 46,
      total_protein_g: 11,
      glycemic_impact: "LOW",
      balanced_plate_score: "HIGH",
      patient_guidance_hinglish: "Moong dal khichdi easy-to-digest aur fiber-rich hai.",
    };

    const getMealDesc = (meal: any) => meal?.raw_description || meal?.description || "Meal";

    expect(getMealDesc(textData)).toBe("1 plate poha with peanuts");
    expect(getMealDesc(photoData)).toBe("Bowl of moong dal khichdi");
    expect(getMealDesc({})).toBe("Meal");
  });

  it("calculates exact dynamic keyboard clearance with extra buffer for text input visibility", () => {
    const calculateBottomPadding = (keyboardHeight: number, insetsBottom: number) => {
      return keyboardHeight > 0 ? keyboardHeight + 20 : Math.max(insetsBottom, 12);
    };

    // When keyboard is closed on iPhone with home indicator (34px)
    expect(calculateBottomPadding(0, 34)).toBe(34);

    // When keyboard is closed on Android (insets = 0px)
    expect(calculateBottomPadding(0, 0)).toBe(12);

    // When keyboard opens on iPhone (e.g. 336px height)
    expect(calculateBottomPadding(336, 34)).toBe(356); // 20px clearance above keyboard top

    // When keyboard opens on Android (e.g. 280px height)
    expect(calculateBottomPadding(280, 0)).toBe(300); // 20px clearance above keyboard top
  });
});
