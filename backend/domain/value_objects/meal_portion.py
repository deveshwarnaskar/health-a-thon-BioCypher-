"""MealPortion value object (Gate 03).

References the canonical katori volumetric vocabulary without adding any
nutritional interpretation at the value-object layer.
"""

from dataclasses import dataclass

from .katori_volume import KatoriVolume


@dataclass(frozen=True)
class MealPortion:
    food_key: str
    katori: KatoriVolume
    quantity: float = 1.0