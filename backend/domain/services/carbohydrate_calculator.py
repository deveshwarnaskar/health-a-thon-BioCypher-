"""Deterministic carbohydrate calculation service (Gate 10J-B).

Pure domain calculation service based on standard Indian food nutritional catalog,
calibrated household Katori volumetric sizing (150, 220, 350 ml), and quantity.

Mathematical formula:
    carbs_grams = round(carbs_per_100g * volume_ml * quantity * 0.009, 1)

Information asymmetry rule:
    Carbohydrate grams and glycemic index are CLINICIAN-ONLY analytical values.
    They must never be projected onto patient-facing views.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..exceptions import (
    InvalidKatoriVolume,
    InvalidPortionQuantityError,
    UnknownFoodItemError,
)
from ..value_objects import KatoriVolume, MealPortion

# Canonical household katori volumes
KATORI_VOLUMES_ML = frozenset({150, 220, 350})

# Standard Indian food catalog: carbs per 100g and glycemic index bucket
# Sourced from standard reference tables (NIN / ICMR dietary guidelines)
FOOD_CATALOG: dict[str, dict[str, Any]] = {
    "white rice": {"genus": "rice", "carbs_per_100g": 28.0, "gi": "high"},
    "steamed rice": {"genus": "rice", "carbs_per_100g": 28.0, "gi": "high"},
    "biryani": {"genus": "biryani", "carbs_per_100g": 26.0, "gi": "high"},
    "pulao": {"genus": "pulao", "carbs_per_100g": 26.0, "gi": "high"},
    "roti": {"genus": "wheat", "carbs_per_100g": 24.0, "gi": "med"},
    "chapati": {"genus": "wheat", "carbs_per_100g": 24.0, "gi": "med"},
    "phulka": {"genus": "wheat", "carbs_per_100g": 24.0, "gi": "med"},
    "bajra roti": {"genus": "millet", "carbs_per_100g": 22.0, "gi": "med"},
    "paratha": {"genus": "paratha", "carbs_per_100g": 30.0, "gi": "high"},
    "puri": {"genus": "fried bread", "carbs_per_100g": 32.0, "gi": "high"},
    "dal": {"genus": "lentils", "carbs_per_100g": 15.0, "gi": "low"},
    "rajma": {"genus": "legumes", "carbs_per_100g": 14.0, "gi": "med"},
    "chole": {"genus": "legumes", "carbs_per_100g": 14.0, "gi": "med"},
    "mixed sabzi": {"genus": "vegetable", "carbs_per_100g": 8.0, "gi": "low"},
    "paneer curries": {"genus": "paneer", "carbs_per_100g": 6.0, "gi": "low"},
    "chicken curry": {"genus": "chicken", "carbs_per_100g": 4.0, "gi": "low"},
    "fish curry": {"genus": "fish", "carbs_per_100g": 3.0, "gi": "low"},
    "curd rice": {"genus": "curd rice", "carbs_per_100g": 26.0, "gi": "med"},
    "dahi": {"genus": "curd", "carbs_per_100g": 5.0, "gi": "low"},
    "idli": {"genus": "idli", "carbs_per_100g": 25.0, "gi": "med"},
    "dosa": {"genus": "dosa", "carbs_per_100g": 26.0, "gi": "med"},
    "vada": {"genus": "fried snack", "carbs_per_100g": 28.0, "gi": "high"},
    "upma": {"genus": "upma", "carbs_per_100g": 22.0, "gi": "med"},
    "poha": {"genus": "poha", "carbs_per_100g": 21.0, "gi": "med"},
    "samosa": {"genus": "fried snack", "carbs_per_100g": 30.0, "gi": "high"},
    "french fries": {"genus": "fried snack", "carbs_per_100g": 32.0, "gi": "high"},
    "pakora": {"genus": "fried snack", "carbs_per_100g": 29.0, "gi": "high"},
    "kheer": {"genus": "dessert", "carbs_per_100g": 26.0, "gi": "high"},
    "laddu": {"genus": "dessert", "carbs_per_100g": 34.0, "gi": "high"},
    "gulab jamun": {"genus": "dessert", "carbs_per_100g": 36.0, "gi": "high"},
    "ice cream": {"genus": "dessert", "carbs_per_100g": 30.0, "gi": "high"},
    "biscuit": {"genus": "biscuit", "carbs_per_100g": 32.0, "gi": "high"},
    "sweet juice": {"genus": "beverage", "carbs_per_100g": 12.0, "gi": "high"},
    "soft drink": {"genus": "beverage", "carbs_per_100g": 11.0, "gi": "high"},
    "salad": {"genus": "vegetable", "carbs_per_100g": 6.0, "gi": "low"},
}

FOOD_ALIASES: dict[str, str] = {
    "rice": "white rice",
    "chawal": "white rice",
    "bhat": "white rice",
    "bhaat": "white rice",
    "chapathi": "chapati",
    "fulka": "phulka",
    "gharelu roti": "roti",
    "parantha": "paratha",
    "poori": "puri",
    "daal": "dal",
    "dhal": "dal",
    "sambar": "dal",
    "tadka dal": "dal",
    "paneer": "paneer curries",
    "paneer bhurji": "paneer curries",
    "curd": "dahi",
    "yogurt": "dahi",
    "doodh": "dahi",
    "sabzi": "mixed sabzi",
    "sabji": "mixed sabzi",
    "subji": "mixed sabzi",
    "vegetables": "mixed sabzi",
    "chicken": "chicken curry",
    "murgh": "chicken curry",
    "fish": "fish curry",
    "machhi": "fish curry",
}


@dataclass(frozen=True)
class CarbohydrateCalculationResult:
    """Analytical result of deterministic carbohydrate calculation (Clinician view)."""

    carbs_grams: float
    glycemic_index: str
    food_key: str
    portion_volume_ml: int
    quantity: float


class CarbohydrateCalculator:
    """Pure domain service for deterministic carbohydrate and GI estimation."""

    def __init__(
        self,
        catalog: dict[str, dict[str, Any]] | None = None,
        aliases: dict[str, str] | None = None,
    ) -> None:
        self._catalog = catalog if catalog is not None else FOOD_CATALOG
        self._aliases = aliases if aliases is not None else FOOD_ALIASES

    def resolve_food(self, key: str) -> dict[str, Any]:
        normalized = key.strip().lower()
        if not normalized:
            raise UnknownFoodItemError("Food key cannot be empty")
        canonical = self._aliases.get(normalized, normalized)
        if canonical in self._catalog:
            return self._catalog[canonical]
        raise UnknownFoodItemError(f"Unknown food item: '{key}'")

    def calculate(
        self,
        food_key: str,
        volume_ml: int,
        quantity: float = 1.0,
    ) -> CarbohydrateCalculationResult:
        if quantity <= 0:
            raise InvalidPortionQuantityError(
                f"Portion quantity must be strictly positive, got {quantity}"
            )
        if volume_ml not in KATORI_VOLUMES_ML:
            raise InvalidKatoriVolume(
                f"Unsupported katori volume {volume_ml} ml; must be one of {sorted(KATORI_VOLUMES_ML)}"
            )

        food_data = self.resolve_food(food_key)
        carbs_per_100g = float(food_data["carbs_per_100g"])
        carbs_grams = round(carbs_per_100g * volume_ml * quantity * 0.009, 1)
        gi = food_data["gi"]

        return CarbohydrateCalculationResult(
            carbs_grams=carbs_grams,
            glycemic_index=gi,
            food_key=food_key,
            portion_volume_ml=volume_ml,
            quantity=quantity,
        )

    def calculate_for_portion(
        self,
        portion: MealPortion,
    ) -> CarbohydrateCalculationResult:
        return self.calculate(
            food_key=portion.food_key,
            volume_ml=portion.katori.volume_ml,
            quantity=portion.quantity,
        )
