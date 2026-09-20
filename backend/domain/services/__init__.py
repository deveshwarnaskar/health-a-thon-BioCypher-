"""Domain services (Gate 10J-B)."""

from .carbohydrate_calculator import (
    CarbohydrateCalculationResult,
    CarbohydrateCalculator,
    FOOD_CATALOG,
    FOOD_ALIASES,
)
from .glycemic_metrics import (
    GLUCOSE_HIGH,
    GLUCOSE_LOW,
    compute_window_metrics,
)

__all__ = [
    "CarbohydrateCalculationResult",
    "CarbohydrateCalculator",
    "FOOD_CATALOG",
    "FOOD_ALIASES",
    "GLUCOSE_HIGH",
    "GLUCOSE_LOW",
    "compute_window_metrics",
]
