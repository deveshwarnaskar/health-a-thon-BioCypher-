"""Domain services (Gate 10J-B)."""

from .carbohydrate_calculator import (
    CarbohydrateCalculationResult,
    CarbohydrateCalculator,
    FOOD_CATALOG,
    FOOD_ALIASES,
)

__all__ = [
    "CarbohydrateCalculationResult",
    "CarbohydrateCalculator",
    "FOOD_CATALOG",
    "FOOD_ALIASES",
]
