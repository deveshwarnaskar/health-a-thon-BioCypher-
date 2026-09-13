"""MealPortion value object placeholder (Gate 02B).

Katori-based volumetric portion references the Aahaar prototype taxonomy
(Small 150ml, Medium 220ml, Large 350ml).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MealPortion:
    food_key: str
    katori_size: str
    quantity: float