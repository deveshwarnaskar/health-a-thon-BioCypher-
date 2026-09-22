"""Indic Dietary and Nutrition Analyzer (ICMR-NIN & Sarvam AI Integration).

Grounds nutritional analysis in:
1. ICMR-NIN (National Institute of Nutrition, Hyderabad) Indian Food Composition Tables (IFCT)
2. RSSDI Clinical Practice Recommendations for Dietary Management
3. Indian portion measures: Katori (150ml small, 220ml medium, 350ml large), standard roti (35g), plate proportions

Features:
- Dual-engine: Sarvam LLM for nuanced Indic extraction with seamless deterministic ICMR fallback
- Calculates estimated Calories, Carbs, Protein, Fat, Dietary Fiber, and Glycemic Load
- Clinical safety guardrail: Information asymmetry preserved — no raw carb counting in patient chat,
  focuses instead on intuitive plate balance (Half plate vegetables, 1/4 protein, 1/4 grains).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from backend.infrastructure.ai.sarvam_client import SarvamClient, SarvamClientError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FoodItemNutrient:
    name: str
    portion_text: str
    calories_kcal: float
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float
    glycemic_index_category: str  # "LOW", "MEDIUM", "HIGH"


@dataclass(frozen=True)
class MealAnalysisResult:
    raw_description: str
    items: list[FoodItemNutrient]
    total_calories_kcal: float
    total_carbs_g: float
    total_protein_g: float
    total_fat_g: float
    total_fiber_g: float
    glycemic_impact: str  # "LOW", "MODERATE", "ELEVATED"
    balanced_plate_score: str  # "OPTIMAL", "ACCEPTABLE", "CARB_HEAVY"
    patient_guidance_hinglish: str
    clinician_notes: str
    source: str  # "sarvam_ai" or "icmr_deterministic"


# Reference ICMR-NIN Database for standard Indian foods per standard portion
_ICMR_FOOD_DB: dict[str, dict[str, Any]] = {
    "roti": {
        "label": "Wheat Roti",
        "portion_default": "1 medium (35g)",
        "calories": 85.0,
        "carbs": 18.0,
        "protein": 3.0,
        "fat": 0.5,
        "fiber": 2.8,
        "gi": "MEDIUM",
        "synonyms": ["roti", "chapati", "phulka", "fulka", "rotli"],
    },
    "paratha": {
        "label": "Plain Paratha",
        "portion_default": "1 piece",
        "calories": 180.0,
        "carbs": 24.0,
        "protein": 4.0,
        "fat": 8.0,
        "fiber": 2.5,
        "gi": "MEDIUM",
        "synonyms": ["paratha", "parontha", "porota"],
    },
    "bajra_roti": {
        "label": "Bajra Roti (Millet)",
        "portion_default": "1 medium",
        "calories": 110.0,
        "carbs": 21.0,
        "protein": 3.8,
        "fat": 1.2,
        "fiber": 4.2,
        "gi": "LOW",
        "synonyms": ["bajra roti", "bajre ki roti", "bajri roti"],
    },
    "jowar_roti": {
        "label": "Jowar Roti (Sorghum)",
        "portion_default": "1 medium",
        "calories": 105.0,
        "carbs": 20.0,
        "protein": 3.2,
        "fat": 1.0,
        "fiber": 3.8,
        "gi": "LOW",
        "synonyms": ["jowar roti", "jowari roti", "bhakri"],
    },
    "rice": {
        "label": "White Rice (Cooked)",
        "portion_default": "1 katori (150g)",
        "calories": 170.0,
        "carbs": 38.0,
        "protein": 3.5,
        "fat": 0.4,
        "fiber": 0.6,
        "gi": "HIGH",
        "synonyms": ["rice", "chawal", "bhat", "chaawal", "plain rice"],
    },
    "brown_rice": {
        "label": "Brown Rice (Cooked)",
        "portion_default": "1 katori (150g)",
        "calories": 160.0,
        "carbs": 34.0,
        "protein": 3.6,
        "fat": 1.2,
        "fiber": 2.8,
        "gi": "MEDIUM",
        "synonyms": ["brown rice", "unpolished rice"],
    },
    "dal": {
        "label": "Dal (Moong/Toor/Masoor)",
        "portion_default": "1 katori (150ml)",
        "calories": 120.0,
        "carbs": 16.0,
        "protein": 7.5,
        "fat": 3.0,
        "fiber": 4.5,
        "gi": "LOW",
        "synonyms": ["dal", "daal", "tadka dal", "yellow dal", "moong dal", "toor dal"],
    },
    "sambar": {
        "label": "Sambar with Veggies",
        "portion_default": "1 katori (150ml)",
        "calories": 95.0,
        "carbs": 14.0,
        "protein": 4.2,
        "fat": 2.5,
        "fiber": 3.8,
        "gi": "LOW",
        "synonyms": ["sambar", "sambhar"],
    },
    "rajma": {
        "label": "Rajma Curry (Kidney Beans)",
        "portion_default": "1 katori (150ml)",
        "calories": 180.0,
        "carbs": 26.0,
        "protein": 9.5,
        "fat": 4.5,
        "fiber": 7.0,
        "gi": "LOW",
        "synonyms": ["rajma", "kidney beans", "rajma curry"],
    },
    "chole": {
        "label": "Chole / Chana Masala",
        "portion_default": "1 katori (150ml)",
        "calories": 190.0,
        "carbs": 27.0,
        "protein": 9.0,
        "fat": 5.5,
        "fiber": 6.8,
        "gi": "LOW",
        "synonyms": ["chole", "chana", "chhole", "chickpeas", "kabuli chana"],
    },
    "sabzi": {
        "label": "Cooked Vegetable Sabzi",
        "portion_default": "1 katori (150g)",
        "calories": 75.0,
        "carbs": 8.5,
        "protein": 2.5,
        "fat": 3.5,
        "fiber": 4.2,
        "gi": "LOW",
        "synonyms": ["sabzi", "sabji", "bhaji", "tarkari", "subzi", "vegetables"],
    },
    "paneer": {
        "label": "Paneer Curry",
        "portion_default": "1 katori (100g paneer)",
        "calories": 240.0,
        "carbs": 5.0,
        "protein": 16.0,
        "fat": 18.0,
        "fiber": 1.0,
        "gi": "LOW",
        "synonyms": ["paneer", "panir", "cottage cheese", "paneer bhurji", "palak paneer"],
    },
    "curd": {
        "label": "Curd / Dahi (Plain)",
        "portion_default": "1 katori (150g)",
        "calories": 90.0,
        "carbs": 6.0,
        "protein": 5.5,
        "fat": 4.5,
        "fiber": 0.0,
        "gi": "LOW",
        "synonyms": ["curd", "dahi", "yogurt", "raita"],
    },
    "salad": {
        "label": "Fresh Green Salad",
        "portion_default": "1 small plate",
        "calories": 30.0,
        "carbs": 5.0,
        "protein": 1.2,
        "fat": 0.2,
        "fiber": 3.0,
        "gi": "LOW",
        "synonyms": ["salad", "cucumber", "kheera", "tamatar", "kakdi"],
    },
    "egg": {
        "label": "Whole Egg (Boiled/Omelette)",
        "portion_default": "1 egg",
        "calories": 78.0,
        "carbs": 0.6,
        "protein": 6.3,
        "fat": 5.3,
        "fiber": 0.0,
        "gi": "LOW",
        "synonyms": ["egg", "anda", "boiled egg", "omelette", "omlet"],
    },
    "chicken": {
        "label": "Chicken Curry / Breast",
        "portion_default": "1 katori (100g chicken)",
        "calories": 190.0,
        "carbs": 3.0,
        "protein": 24.0,
        "fat": 9.0,
        "fiber": 0.5,
        "gi": "LOW",
        "synonyms": ["chicken", "murgh", "chicken curry", "boiled chicken"],
    },
    "fish": {
        "label": "Fish Curry",
        "portion_default": "1 katori (100g fish)",
        "calories": 160.0,
        "carbs": 2.5,
        "protein": 20.0,
        "fat": 7.5,
        "fiber": 0.2,
        "gi": "LOW",
        "synonyms": ["fish", "machli", "maach", "fish curry"],
    },
    "idli": {
        "label": "Steamed Idli",
        "portion_default": "1 piece",
        "calories": 65.0,
        "carbs": 13.5,
        "protein": 2.0,
        "fat": 0.3,
        "fiber": 1.0,
        "gi": "MEDIUM",
        "synonyms": ["idli", "idly"],
    },
    "dosa": {
        "label": "Plain Dosa",
        "portion_default": "1 piece",
        "calories": 145.0,
        "carbs": 23.0,
        "protein": 3.2,
        "fat": 4.5,
        "fiber": 1.5,
        "gi": "MEDIUM",
        "synonyms": ["dosa", "plain dosa", "masala dosa"],
    },
    "poha": {
        "label": "Poha with Veggies & Peanuts",
        "portion_default": "1 plate / katori",
        "calories": 210.0,
        "carbs": 36.0,
        "protein": 4.5,
        "fat": 5.5,
        "fiber": 2.5,
        "gi": "MEDIUM",
        "synonyms": ["poha", "aval", "flattened rice"],
    },
    "khichdi": {
        "label": "Moong Dal Khichdi",
        "portion_default": "1 katori (180g)",
        "calories": 165.0,
        "carbs": 28.0,
        "protein": 6.5,
        "fat": 3.0,
        "fiber": 3.2,
        "gi": "MEDIUM",
        "synonyms": ["khichdi", "khichuri", "pongal"],
    },
    "oats": {
        "label": "Oatmeal with Water/Milk",
        "portion_default": "1 bowl",
        "calories": 150.0,
        "carbs": 25.0,
        "protein": 5.0,
        "fat": 2.5,
        "fiber": 4.0,
        "gi": "LOW",
        "synonyms": ["oats", "oatmeal"],
    },
    "chai": {
        "label": "Chai / Tea with Milk",
        "portion_default": "1 cup (100ml)",
        "calories": 45.0,
        "carbs": 5.0,
        "protein": 2.0,
        "fat": 1.8,
        "fiber": 0.0,
        "gi": "LOW",
        "synonyms": ["chai", "tea", "coffee"],
    },
}


class IndicNutritionAnalyzer:
    """Combines ICMR-NIN nutrition data with Sarvam AI for smart Indian meal analysis."""

    def __init__(self, sarvam_client: Optional[SarvamClient] = None) -> None:
        self.sarvam = sarvam_client or SarvamClient()

    def analyze_meal(self, raw_description: str, patient_name: str = "") -> MealAnalysisResult:
        """Analyze Indian meal description, calculating macronutrients, portion score, and guidance."""
        text = (raw_description or "").strip()
        if not text:
            return self._empty_result(text)

        # Attempt Sarvam AI parsing if configured
        if self.sarvam.is_configured:
            try:
                ai_result = self._analyze_with_sarvam(text, patient_name)
                if ai_result:
                    return ai_result
            except Exception as exc:
                logger.warning("Sarvam AI meal analysis fallback triggered: %s", exc)

        # Deterministic fallback using ICMR database
        return self._analyze_deterministic(text, patient_name)

    def _analyze_with_sarvam(self, text: str, patient_name: str) -> Optional[MealAnalysisResult]:
        system_prompt = (
            "You are a specialized Indian Clinical Nutritionist for diabetes care (ICMR-NIN & RSSDI).\n"
            "Analyze the patient's meal description and return valid JSON with:\n"
            "{\n"
            '  "items": [\n'
            '    {"name": "...", "portion_text": "...", "calories_kcal": 0.0, "carbs_g": 0.0, "protein_g": 0.0, "fat_g": 0.0, "fiber_g": 0.0, "gi": "LOW|MEDIUM|HIGH"}\n'
            "  ],\n"
            '  "guidance_hinglish": "Warm empathetic advice in Hinglish with patient name",\n'
            '  "balanced_score": "OPTIMAL|ACCEPTABLE|CARB_HEAVY"\n'
            "}\n"
            "Rule: Do NOT output raw carb grams to the patient in guidance. Focus on intuitive plate balance (salad/protein/grain proportions)."
        )

        user_prompt = f"Patient Name: {patient_name or 'Friend'}\nMeal Logged: {text}"

        res = self.sarvam.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=600,
        )

        content = res.get("content", "").strip()
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            return None

        data = json.loads(json_match.group(0))
        raw_items = data.get("items") or []
        items: list[FoodItemNutrient] = []

        total_cal = 0.0
        total_carb = 0.0
        total_prot = 0.0
        total_fat = 0.0
        total_fib = 0.0

        for it in raw_items:
            cal = float(it.get("calories_kcal") or 0.0)
            carb = float(it.get("carbs_g") or 0.0)
            prot = float(it.get("protein_g") or 0.0)
            fat = float(it.get("fat_g") or 0.0)
            fib = float(it.get("fiber_g") or 0.0)
            gi = str(it.get("gi") or "MEDIUM").upper()

            total_cal += cal
            total_carb += carb
            total_prot += prot
            total_fat += fat
            total_fib += fib

            items.append(
                FoodItemNutrient(
                    name=it.get("name", "Food Item"),
                    portion_text=it.get("portion_text", "1 serving"),
                    calories_kcal=round(cal, 1),
                    carbs_g=round(carb, 1),
                    protein_g=round(prot, 1),
                    fat_g=round(fat, 1),
                    fiber_g=round(fib, 1),
                    glycemic_index_category=gi,
                )
            )

        if not items:
            return None

        if total_carb > 60.0 or (total_carb > 45.0 and total_fib < 3.0):
            impact = "ELEVATED"
        elif total_carb > 35.0:
            impact = "MODERATE"
        else:
            impact = "LOW"

        score = data.get("balanced_score", "ACCEPTABLE").upper()
        guidance = data.get("guidance_hinglish") or self._generate_default_guidance(items, patient_name)
        clinician_note = (
            f"Sarvam AI Diet Analysis: {len(items)} items identified. "
            f"Est: {round(total_cal)} kcal, {round(total_carb)}g carbs, {round(total_prot)}g protein, {round(total_fib)}g fiber. "
            f"Glycemic Impact: {impact}."
        )

        return MealAnalysisResult(
            raw_description=text,
            items=items,
            total_calories_kcal=round(total_cal, 1),
            total_carbs_g=round(total_carb, 1),
            total_protein_g=round(total_prot, 1),
            total_fat_g=round(total_fat, 1),
            total_fiber_g=round(total_fib, 1),
            glycemic_impact=impact,
            balanced_plate_score=score,
            patient_guidance_hinglish=guidance,
            clinician_notes=clinician_note,
            source="sarvam_ai",
        )

    def _analyze_deterministic(self, text: str, patient_name: str) -> MealAnalysisResult:
        """Deterministic ICMR-NIN database match for Indian foods."""
        low = text.lower()
        items: list[FoodItemNutrient] = []

        total_cal = 0.0
        total_carb = 0.0
        total_prot = 0.0
        total_fat = 0.0
        total_fib = 0.0

        for key, entry in _ICMR_FOOD_DB.items():
            for syn in entry["synonyms"]:
                match = re.search(r"(\d+(\.\d+)?|\b(?:one|two|three|do|ek|teen)\b)?\s*" + re.escape(syn), low)
                if match:
                    qty_str = (match.group(1) or "1").strip().lower()
                    qty_map = {"ek": 1.0, "one": 1.0, "do": 2.0, "two": 2.0, "teen": 3.0, "three": 3.0}
                    try:
                        qty = qty_map.get(qty_str, float(qty_str))
                    except ValueError:
                        qty = 1.0

                    cal = entry["calories"] * qty
                    carb = entry["carbs"] * qty
                    prot = entry["protein"] * qty
                    fat = entry["fat"] * qty
                    fib = entry["fiber"] * qty

                    total_cal += cal
                    total_carb += carb
                    total_prot += prot
                    total_fat += fat
                    total_fib += fib

                    items.append(
                        FoodItemNutrient(
                            name=entry["label"],
                            portion_text=f"{qty:g}x {entry['portion_default']}",
                            calories_kcal=round(cal, 1),
                            carbs_g=round(carb, 1),
                            protein_g=round(prot, 1),
                            fat_g=round(fat, 1),
                            fiber_g=round(fib, 1),
                            glycemic_index_category=entry["gi"],
                        )
                    )
                    break

        if not items:
            items.append(
                FoodItemNutrient(
                    name="Logged Indian Meal",
                    portion_text="1 serving",
                    calories_kcal=300.0,
                    carbs_g=40.0,
                    protein_g=8.0,
                    fat_g=10.0,
                    fiber_g=4.0,
                    glycemic_index_category="MEDIUM",
                )
            )
            total_cal = 300.0
            total_carb = 40.0
            total_prot = 8.0
            total_fat = 10.0
            total_fib = 4.0

        if total_carb > 60.0:
            impact = "ELEVATED"
            score = "CARB_HEAVY"
        elif total_carb > 35.0:
            impact = "MODERATE"
            score = "ACCEPTABLE"
        else:
            impact = "LOW"
            score = "OPTIMAL"

        guidance = self._generate_default_guidance(items, patient_name)
        clinician_note = (
            f"ICMR-NIN Deterministic Analysis: {len(items)} items matched. "
            f"Est: {round(total_cal)} kcal, {round(total_carb)}g carbs, {round(total_prot)}g protein, {round(total_fib)}g fiber. "
            f"Glycemic Impact: {impact}."
        )

        return MealAnalysisResult(
            raw_description=text,
            items=items,
            total_calories_kcal=round(total_cal, 1),
            total_carbs_g=round(total_carb, 1),
            total_protein_g=round(total_prot, 1),
            total_fat_g=round(total_fat, 1),
            total_fiber_g=round(total_fib, 1),
            glycemic_impact=impact,
            balanced_plate_score=score,
            patient_guidance_hinglish=guidance,
            clinician_notes=clinician_note,
            source="icmr_deterministic",
        )

    def _generate_default_guidance(self, items: list[FoodItemNutrient], patient_name: str) -> str:
        name_str = f" {patient_name.strip()} ji" if patient_name.strip() else ""
        has_salad = any("Salad" in i.name or "Vegetable" in i.name for i in items)
        has_protein = any(i.protein_g >= 6.0 for i in items)

        if has_salad and has_protein:
            return (
                f"Bohot badhiya{name_str}! Aapki thali mein protein aur fiber ka accha balance hai. "
                "Yeh blood sugar ko steady rakhne mein madad karega! 👍"
            )
        elif not has_salad:
            return (
                f"Thali note ho gayi{name_str}! Agle meal mein thoda green salad ya dahi shamil karein "
                "taaki khane ke baad sugar spike na ho. 🥗"
            )
        else:
            return (
                f"Aapka meal darz ho gaya{name_str}. Khane ke 10-15 minute baad thodi halki walk karna labhkari rahega."
            )

    def _empty_result(self, text: str) -> MealAnalysisResult:
        return MealAnalysisResult(
            raw_description=text,
            items=[],
            total_calories_kcal=0.0,
            total_carbs_g=0.0,
            total_protein_g=0.0,
            total_fat_g=0.0,
            total_fiber_g=0.0,
            glycemic_impact="LOW",
            balanced_plate_score="ACCEPTABLE",
            patient_guidance_hinglish="Koi meal description nahi mila.",
            clinician_notes="Empty meal description provided.",
            source="icmr_deterministic",
        )
