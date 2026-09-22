"""Indian food nutrition taxonomy.

Ported from app/core/nutrition.py — all imports to app.* removed.
Pure, stateless module: no database, no network, no settings dependency.

Provides:
  - 35-staple FOODS database (carbs_per_100g, gi_bucket, default portion)
  - classify_text()    — match food items from free text
  - estimate_nutrition() — compute carbs_grams + gi_category for a plate
  - KATORI_VOLUMES / KATORI_LABELS
  - gi_bucket_index()

Information-asymmetry invariant: carb grams and GI are DOCTOR-ONLY metrics.
Patient-facing code must use KATORI_LABELS (Small / Medium / Large) only.
"""
from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Katori portions (shown to patients — NO carb/GI numbers)
# ---------------------------------------------------------------------------

KATORI_LABELS: dict[str, str] = {
    "s": "Small (150 ml)",
    "m": "Medium (220 ml)",
    "l": "Large (350 ml)",
}
KATORI_VOLUMES: dict[str, int] = {"s": 150, "m": 220, "l": 350}

GI_ORDER: dict[str, int] = {"low": 0, "med": 1, "high": 2}

# ---------------------------------------------------------------------------
# Food database
# row = (item_name, genus, carbs_per_100g, gi_bucket, default_portion)
# ---------------------------------------------------------------------------

FOODS: list[tuple[str, str, float, str, str]] = [
    ("white rice",      "rice",         28.0, "high", "m"),
    ("steamed rice",    "rice",         28.0, "high", "m"),
    ("biryani",         "biryani",      26.0, "high", "m"),
    ("pulao",           "pulao",        26.0, "high", "m"),
    ("roti",            "wheat",        24.0, "med",  "m"),
    ("chapati",         "wheat",        24.0, "med",  "m"),
    ("phulka",          "wheat",        24.0, "med",  "m"),
    ("bajra roti",      "millet",       22.0, "med",  "m"),
    ("paratha",         "paratha",      30.0, "high", "m"),
    ("puri",            "fried bread",  32.0, "high", "m"),
    ("dal",             "lentils",      15.0, "low",  "m"),
    ("rajma",           "legumes",      14.0, "med",  "m"),
    ("chole",           "legumes",      14.0, "med",  "m"),
    ("mixed sabzi",     "vegetable",     8.0, "low",  "m"),
    ("paneer curries",  "paneer",        6.0, "low",  "m"),
    ("chicken curry",   "chicken",       4.0, "low",  "m"),
    ("fish curry",      "fish",          3.0, "low",  "m"),
    ("curd rice",       "curd rice",    26.0, "med",  "m"),
    ("dahi",            "curd",          5.0, "low",  "m"),
    ("idli",            "idli",         25.0, "med",  "m"),
    ("dosa",            "dosa",         26.0, "med",  "m"),
    ("vada",            "fried snack",  28.0, "high", "m"),
    ("upma",            "upma",         22.0, "med",  "m"),
    ("poha",            "poha",         21.0, "med",  "m"),
    ("samosa",          "fried snack",  30.0, "high", "m"),
    ("french fries",    "fried snack",  32.0, "high", "m"),
    ("pakora",          "fried snack",  29.0, "high", "m"),
    ("kheer",           "dessert",      26.0, "high", "m"),
    ("laddu",           "dessert",      34.0, "high", "m"),
    ("gulab jamun",     "dessert",      36.0, "high", "m"),
    ("ice cream",       "dessert",      30.0, "high", "m"),
    ("biscuit",         "biscuit",      32.0, "high", "m"),
    ("sweet juice",     "beverage",     12.0, "high", "m"),
    ("soft drink",      "beverage",     11.0, "high", "m"),
    ("salad",           "vegetable",     6.0, "low",  "s"),
]

# Colloquial aliases → canonical item name
_ALIASES: dict[str, str] = {
    "rice": "white rice",       "chawal": "white rice",  "bhat": "white rice",
    "bhaat": "white rice",
    "chapathi": "roti",         "chapati": "roti",       "phulka": "roti",
    "fulka": "roti",            "naan": "roti",          "puri": "roti",
    "poori": "roti",            "bhatura": "roti",
    "parantha": "paratha",
    "daliya": "poha",           "oats": "poha",          "khichdi": "poha",
    "bhindi": "mixed sabzi",    "aloo gobi": "mixed sabzi", "aloo matar": "mixed sabzi",
    "aloo": "mixed sabzi",      "gobi": "mixed sabzi",   "palak": "mixed sabzi",
    "tarkari": "mixed sabzi",   "sabji": "mixed sabzi",  "subji": "mixed sabzi",
    "sabzi": "mixed sabzi",     "bhaji": "mixed sabzi",  "curry": "mixed sabzi",
    "saag": "mixed sabzi",
    "daal": "dal",              "dhal": "dal",           "sambar": "dal",
    "tadka": "dal",
    "chicken": "chicken curry", "murgh": "chicken curry",
    "fish": "fish curry",       "machhi": "fish curry",
    "egg": "chicken curry",     "anda": "chicken curry",
    "paneer bhurji": "paneer curries", "paneer": "paneer curries",
    "curd": "dahi",             "yogurt": "dahi",        "chaas": "dahi",
    "lassi": "dahi",            "doodh": "dahi",         "milk": "dahi",
    "chai": "sweet juice",      "tea": "sweet juice",    "coffee": "sweet juice",
    "gulabjamun": "gulab jamun",
    "mithai": "laddu",          "sweet": "laddu",
    "cold drink": "soft drink", "fanta/cola": "soft drink",
    "kheer/rice kheer": "kheer",
    "fruit": "salad",           "fruits": "salad",       "apple": "salad",
    "banana": "salad",
}

FoodDict = dict[str, object]


def _row_for(key: str) -> FoodDict:
    for item, genus, carbs, gi, portion in FOODS:
        if item == key or genus == key:
            return {"item": item, "genus": genus, "carbs_per_100g": carbs,
                    "gi": gi, "portion": portion}
    return {}


# ---------------------------------------------------------------------------
# Public API & Scientific Quantity Parsing (ICMR / IFCT Guidelines)
# ---------------------------------------------------------------------------

_NUM_WORDS: dict[str, float] = {
    "half": 0.5, "aadha": 0.5, "adha": 0.5, "1/2": 0.5,
    "quarter": 0.25,
    "one": 1.0, "ek": 1.0, "1": 1.0,
    "two": 2.0, "do": 2.0, "2": 2.0,
    "three": 3.0, "teen": 3.0, "tin": 3.0, "3": 3.0,
    "four": 4.0, "char": 4.0, "chaar": 4.0, "4": 4.0,
    "five": 5.0, "paanch": 5.0, "panch": 5.0, "5": 5.0,
    "six": 6.0, "chhe": 6.0, "che": 6.0, "6": 6.0,
    "dedh": 1.5, "dhai": 2.5,
}

GI_NUMERIC: dict[str, float] = {"low": 35.0, "med": 58.0, "high": 75.0}


def _extract_quantity_before_token(text: str, token_start: int) -> float:
    """Extract quantity preceding a food token in natural text (e.g. '2 roti' -> 2.0)."""
    prefix = text[:token_start].strip()
    if not prefix:
        return 1.0
    m = re.search(
        r"(?:^|[\s,;+])(\d+(?:\.\d+)?|\d+/\d+|half|aadha|adha|quarter|one|two|three|four|five|six|ek|do|teen|tin|char|chaar|paanch|panch|dedh|dhai)\s*(?:katori|katoris|bowl|bowls|plate|plates|cup|cups|glass|piece|pieces|tukda|vati)?\s*$",
        prefix,
        re.I,
    )
    if m:
        val_str = m.group(1).lower()
        if val_str in _NUM_WORDS:
            return _NUM_WORDS[val_str]
        try:
            if "/" in val_str:
                num, denom = val_str.split("/")
                return round(float(num) / float(denom), 2)
            val = float(val_str)
            if 0 < val <= 20:
                return val
        except ValueError:
            pass
    return 1.0


def classify_text(text: Optional[str]) -> list[FoodDict]:
    """Return food rows matched from a free-text meal description.

    Matches FOODS item names, colloquial aliases, and natural quantities.
    Falls back to a generic "mixed meal" row when meaningful eating clues
    exist but no specific staple is recognised.
    """
    if not text:
        return []

    cleaned = text.lower().replace(",", " ").replace(" and ", " ").replace(" aur ", " ")
    resolved: list[FoodDict] = []
    seen: set[str] = set()

    # Build candidate list: exact item names + aliases (longest first)
    candidates: list[str] = [item for item, *_ in FOODS]
    candidates += sorted(_ALIASES, key=len, reverse=True)

    for token in candidates:
        canonical = _ALIASES.get(token, token)
        if canonical in seen:
            continue
        idx = cleaned.find(token)
        if idx != -1:
            row = _row_for(canonical)
            if not row:
                continue
            seen.add(canonical)
            qty = _extract_quantity_before_token(cleaned, idx)
            item_row = dict(row)
            item_row["quantity"] = qty
            resolved.append(item_row)
            if len(resolved) >= 4:
                break

    if not resolved and len(text.strip()) >= 2:
        desc = text.strip().lower()
        food_clues = (
            "had", "ate", "eating", "khaya", "khaye", "khana", "khaana",
            "meal", "lunch", "dinner", "breakfast", "nashta", "bowl", "plate",
        )
        if any(c in desc for c in food_clues):
            clean_desc = text.strip()
            for filler in (
                "maine", "humne", "aaj", "i had", "ate", "eating", "khaya",
                "meal", "lunch", "dinner", "breakfast",
            ):
                if clean_desc.lower().startswith(filler):
                    clean_desc = clean_desc[len(filler):].strip()
            plate_name = clean_desc[:30].strip() or "Mixed meal"
            resolved.append({
                "item": plate_name,
                "genus": "mixed meal",
                "carbs_per_100g": 16.0,
                "gi": "med",
                "portion": "m",
                "quantity": 1.0,
            })

    return resolved


def estimate_carbs_g(portion_ml: float, row: FoodDict) -> float:
    """Carb grams for a katori-sized serve (density ~1 g/ml cooked bowl)."""
    carbs = float(row.get("carbs_per_100g", 0.0))  # type: ignore[arg-type]
    qty = float(row.get("quantity", 1.0))
    return round(carbs * portion_ml * qty * 0.009, 1)


class NutritionEstimate:
    """Result of estimating nutrition for a full plate."""

    def __init__(self, carbs_grams: float, gi_category: str) -> None:
        self.carbs_grams = carbs_grams
        self.gi_category = gi_category


def estimate_nutrition(items: list[FoodDict], portion: str = "m") -> NutritionEstimate:
    """Estimate total carbs and composite GI for a list of classified food items.

    Uses scientifically validated FAO/WHO/ADA weighted composite glycemic index.
    """
    portion_ml = float(KATORI_VOLUMES.get(portion, 220))
    total_carbs = sum(estimate_carbs_g(portion_ml, row) for row in items)

    if total_carbs > 0:
        weighted_gi_sum = sum(
            estimate_carbs_g(portion_ml, row) * GI_NUMERIC.get(str(row.get("gi", "med")).lower(), 58.0)
            for row in items
        )
        composite_gi = weighted_gi_sum / total_carbs
        if composite_gi < 55.0:
            dominant_gi = "low"
        elif composite_gi < 70.0:
            dominant_gi = "med"
        else:
            dominant_gi = "high"
    else:
        gi_buckets = [str(row.get("gi", "med")) for row in items]
        ranked = sorted(set(gi_buckets), key=lambda g: GI_ORDER.get(g, 1), reverse=True)
        dominant_gi = ranked[0] if ranked else "med"

    return NutritionEstimate(carbs_grams=round(total_carbs, 1), gi_category=dominant_gi)


def gi_bucket_index(gi: str) -> int:
    return GI_ORDER.get((gi or "").lower(), 1)


__all__ = [
    "FOODS",
    "KATORI_LABELS",
    "KATORI_VOLUMES",
    "GI_ORDER",
    "FoodDict",
    "NutritionEstimate",
    "classify_text",
    "estimate_carbs_g",
    "estimate_nutrition",
    "gi_bucket_index",
]
