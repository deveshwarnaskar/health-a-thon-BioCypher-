"""Indian-food nutrition table for the prototype.

This module powers two things:
  * the *mock* vision / text classifier (no ML model installed yet), and
  * the doctor-only carb/GI numbers shown in the report.

Remember the product rule: the PATIENT only ever sees a calibrated katori portion
(Small / Medium / Large). Carb and GI numbers live on the doctor side only.
"""
from __future__ import annotations

from typing import Optional

# Calibrated katori bowls (ml). These are the units shown to the patient.
KATORI_LABELS = {"s": "Small (150 ml)", "m": "Medium (220 ml)", "l": "Large (350 ml)"}
GI_ORDER = {"low": 0, "med": 1, "high": 2}

# row = (item, genus, carbs_per_100g, gi_bucket, default_portion)
FOODS: list[tuple[str, str, float, str, str]] = [
    ("white rice", "rice", 28.0, "high", "m"),
    ("steamed rice", "rice", 28.0, "high", "m"),
    ("biryani", "biryani", 26.0, "high", "m"),
    ("pulao", "pulao", 26.0, "high", "m"),
    ("roti", "wheat", 24.0, "med", "m"),
    ("chapati", "wheat", 24.0, "med", "m"),
    ("phulka", "wheat", 24.0, "med", "m"),
    ("bajra roti", "millet", 22.0, "med", "m"),
    ("paratha", "paratha", 30.0, "high", "m"),
    ("puri", "fried bread", 32.0, "high", "m"),
    ("dal", "lentils", 15.0, "low", "m"),
    ("rajma", "legumes", 14.0, "med", "m"),
    ("chole", "legumes", 14.0, "med", "m"),
    ("mixed sabzi", "vegetable", 8.0, "low", "m"),
    ("paneer curries", "paneer", 6.0, "low", "m"),
    ("chicken curry", "chicken", 4.0, "low", "m"),
    ("fish curry", "fish", 3.0, "low", "m"),
    ("curd rice", "curd rice", 26.0, "med", "m"),
    ("dahi", "curd", 5.0, "low", "m"),
    ("idli", "idli", 25.0, "med", "m"),
    ("dosa", "dosa", 26.0, "med", "m"),
    ("vada", "fried snack", 28.0, "high", "m"),
    ("upma", "upma", 22.0, "med", "m"),
    ("poha", "poha", 21.0, "med", "m"),
    ("samosa", "fried snack", 30.0, "high", "m"),
    ("french fries", "fried snack", 32.0, "high", "m"),
    ("pakora", "fried snack", 29.0, "high", "m"),
    ("kheer", "dessert", 26.0, "high", "m"),
    ("laddu", "dessert", 34.0, "high", "m"),
    ("gulab jamun", "dessert", 36.0, "high", "m"),
    ("ice cream", "dessert", 30.0, "high", "m"),
    ("biscuit", "biscuit", 32.0, "high", "m"),
    ("sweet juice", "beverage", 12.0, "high", "m"),
    ("soft drink", "beverage", 11.0, "high", "m"),
    ("salad", "vegetable", 6.0, "low", "s"),
]

FoodDict = dict[str, object]

# Colloquial aliases -> canonical item name (item names themselves always match).
_ALIASES: dict[str, str] = {
    "rice": "white rice",
    "chawal": "white rice",
    "chapathi": "roti",
    "roti": "roti",
    "gharelu roti": "roti",
    "daliya": "poha",
    "bhindi": "mixed sabzi",
    "aloo gobi": "mixed sabzi",
    "saag": "mixed sabzi",
    "chicken": "chicken curry",
    "paneer bhurji": "paneer curries",
    "gulabjamun": "gulab jamun",
    "gulab jamun": "gulab jamun",
    "fanta/cola": "soft drink",
    "cold drink": "soft drink",
    "kheer/rice kheer": "kheer",
}


def _row_for(key: str) -> FoodDict:
    for item, genus, carbs, gi, portion in FOODS:
        if item == key or genus == key:
            return {"item": item, "genus": genus, "carbs_per_100g": carbs,
                    "gi": gi, "portion": portion}
    return {}


def classify_text(text: Optional[str]) -> list[FoodDict]:
    """Return food rows matched from a free-text meal description.

    Every FOODS item name matches on its own; aliases expand the everyday words.
    Returns up to 4 matched plates (patients confirm/correct afterwards).
    """
    if not text:
        return []
    words = text.lower().replace(",", " ").replace(" and ", " ")

    resolved: list[FoodDict] = []
    seen: set[str] = set()

    candidates: list[str] = []
    for item, *_rest in FOODS:
        candidates.append(item)
    candidates += sorted(_ALIASES, key=len, reverse=True)  # longest alias first

    for token in candidates:
        canonical = _ALIASES.get(token, token)
        if canonical in seen or token not in words:
            continue
        row = _row_for(canonical)
        if not row:
            continue
        seen.add(canonical)
        resolved.append(row)
        if len(resolved) >= 4:
            break
    return resolved


# A small "plausible plate" library used by mock-vision (photo mode).
_PHOTO_PLATES: list[list[FoodDict]] = [
    [{"item": "roti", "genus": "wheat", "carbs_per_100g": 24.0, "gi": "med",  "portion": "m"},
     {"item": "dal", "genus": "lentils", "carbs_per_100g": 15.0, "gi": "low",  "portion": "m"},
     {"item": "mixed sabzi", "genus": "vegetable", "carbs_per_100g": 8.0, "gi": "low", "portion": "m"}],
    [{"item": "white rice", "genus": "rice", "carbs_per_100g": 28.0, "gi": "high", "portion": "m"},
     {"item": "rajma", "genus": "legumes", "carbs_per_100g": 14.0, "gi": "med", "portion": "m"},
     {"item": "salad", "genus": "vegetable", "carbs_per_100g": 6.0, "gi": "low", "portion": "s"}],
    [{"item": "dosa", "genus": "dosa", "carbs_per_100g": 26.0, "gi": "med", "portion": "m"},
     {"item": "dahi", "genus": "curd", "carbs_per_100g": 5.0, "gi": "low", "portion": "s"}],
    [{"item": "poha", "genus": "poha", "carbs_per_100g": 21.0, "gi": "med", "portion": "m"},
     {"item": "mixed sabzi", "genus": "vegetable", "carbs_per_100g": 8.0, "gi": "low", "portion": "m"}],
    [{"item": "white rice", "genus": "rice", "carbs_per_100g": 28.0, "gi": "high", "portion": "m"},
     {"item": "biryani", "genus": "biryani", "carbs_per_100g": 26.0, "gi": "high", "portion": "m"}],
    [{"item": "paratha", "genus": "paratha", "carbs_per_100g": 30.0, "gi": "high", "portion": "m"},
     {"item": "curd rice", "genus": "curd rice", "carbs_per_100g": 26.0, "gi": "med", "portion": "m"}],
    [{"item": "idli", "genus": "idli", "carbs_per_100g": 25.0, "gi": "med", "portion": "m"},
     {"item": "sambar dal", "genus": "lentils", "carbs_per_100g": 15.0, "gi": "low", "portion": "m"}],
    [{"item": "samosa", "genus": "fried snack", "carbs_per_100g": 30.0, "gi": "high", "portion": "m"},
     {"item": "sweet juice", "genus": "beverage", "carbs_per_100g": 12.0, "gi": "high", "portion": "m"}],
]


def detect_photo(hour: int, day_ordinal: int, cfg) -> list[FoodDict]:
    """Mock vision: return a deterministic 'detected plate' for a photo.

    A real vision model will drop in behind the same function signature.
    """
    idx = (day_ordinal + hour // 6) % len(_PHOTO_PLATES)
    return [dict(r) for r in _PHOTO_PLATES[idx]]


def estimate_carbs_g(portion_ml: float, row: FoodDict) -> float:
    """Carb grams for a katori-sized serve (rough density 1 g/ml cooked bowl)."""
    carbs = float(row.get("carbs_per_100g", 0.0))
    return round(carbs * portion_ml * 0.009, 1)


def gi_bucket_index(gi: str) -> int:
    return GI_ORDER.get((gi or "").lower(), 1)