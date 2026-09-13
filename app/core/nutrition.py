"""Indian-food nutrition table for the prototype.

This module powers two things:
  * the *mock* vision / text classifier (no ML model installed yet), and
  * the doctor-only carb/GI numbers shown in the report.

Remember the product rule: the PATIENT only ever sees a calibrated katori portion
(Small / Medium / Large). Carb and GI numbers live on the doctor side only.
"""
from __future__ import annotations

import re
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
    ("bhature", "fried bread", 34.0, "high", "m"),
    ("chole bhature", "street food", 30.0, "med", "m"),
    ("pani puri", "street food", 27.0, "med", "m"),
    ("pav bhaji", "street food", 28.0, "med", "m"),
    ("vada pav", "street food", 30.0, "high", "m"),
    ("maggi", "instant noodles", 34.0, "high", "m"),
    ("noodles", "instant noodles", 34.0, "high", "m"),
    ("sandwich", "bread snack", 24.0, "med", "m"),
    ("toast", "bread snack", 24.0, "med", "m"),
    ("burger", "fast food", 28.0, "high", "m"),
    ("pizza", "fast food", 22.0, "med", "m"),
    ("apple", "fruit", 13.0, "low", "s"),
    ("banana", "fruit", 21.0, "med", "s"),
    ("chocolate", "dessert", 55.0, "high", "s"),
    ("omelette", "egg", 3.0, "low", "m"),
    ("kadi", "curry", 12.0, "low", "m"),
    ("mutton", "meat", 3.0, "low", "m"),
    ("egg curry", "egg", 4.0, "low", "m"),
    ("rasgulla", "dessert", 30.0, "high", "m"),
    ("jalebi", "dessert", 32.0, "high", "m"),
]

FoodDict = dict[str, object]

# Colloquial aliases -> canonical item name (item names themselves always match).
_ALIASES: dict[str, str] = {
    "rice": "white rice",
    "chawal": "white rice",
    "bhat": "white rice",
    "bhaat": "white rice",
    "pulao": "white rice",
    "chapathi": "roti",
    "chapati": "roti",
    "phulka": "roti",
    "fulka": "roti",
    "roti": "roti",
    "gharelu roti": "roti",
    "paratha": "paratha",
    "parantha": "paratha",
    "naan": "roti",
    "puri": "puri",
    "poori": "puri",
    "bhatura": "bhature",
    "bhature": "bhature",
    "chole bhature": "chole bhature",
    "chana masala": "chole",
    "chana": "chole",
    "chole": "chole",
    "panipuri": "pani puri",
    "pani puri": "pani puri",
    "vadapav": "vada pav",
    "vada pav": "vada pav",
    "pavbhaji": "pav bhaji",
    "pav bhaji": "pav bhaji",
    "maggie": "maggi",
    "bread": "toast",
    "seb": "apple",
    "kadhi": "kadi",
    "keema": "mutton",
    "uttapam": "dosa",
    "daliya": "poha",
    "oats": "poha",
    "khichdi": "poha",
    "bhindi": "mixed sabzi",
    "aloo gobi": "mixed sabzi",
    "aloo matar": "mixed sabzi",
    "aloo": "mixed sabzi",
    "gobi": "mixed sabzi",
    "palak": "mixed sabzi",
    "tarkari": "mixed sabzi",
    "sabji": "mixed sabzi",
    "subji": "mixed sabzi",
    "sabzi": "mixed sabzi",
    "bhaji": "mixed sabzi",
    "curry": "mixed sabzi",
    "saag": "mixed sabzi",
    "daal": "dal",
    "dhal": "dal",
    "dal": "dal",
    "sambar": "dal",
    "tadka": "dal",
    "chicken": "chicken curry",
    "chicken curry": "chicken curry",
    "murgh": "chicken curry",
    "fish": "fish curry",
    "machhi": "fish curry",
    "egg": "omelette",
    "anda": "omelette",
    "paneer bhurji": "paneer curries",
    "paneer": "paneer curries",
    "curd": "dahi",
    "dahi": "dahi",
    "yogurt": "dahi",
    "chaas": "dahi",
    "lassi": "dahi",
    "doodh": "dahi",
    "milk": "dahi",
    "chai": "sweet juice",
    "tea": "sweet juice",
    "coffee": "sweet juice",
    "biscuit": "biscuit",
    "choco": "chocolate",
    "chocolate": "chocolate",
    "salad": "salad",
    "gulabjamun": "gulab jamun",
    "gulab jamun": "gulab jamun",
    "mithai": "laddu",
    "sweet": "laddu",
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

    Every FOODS item name matches on its own; aliases expand everyday Hindi/English words.
    Falls back gracefully to a composite meal row so natural descriptions are never rejected.
    """
    if not text:
        return []
    cleaned = text.lower().replace(",", " ").replace(" and ", " ").replace(" aur ", " ")
    words = cleaned.split()

    resolved: list[FoodDict] = []
    seen: set[str] = set()

    candidates: list[str] = []
    for item, *_rest in FOODS:
        candidates.append(item)
    candidates += sorted(_ALIASES, key=len, reverse=True)
    candidates = list(dict.fromkeys(candidates))

    matched_spans: list[tuple[int, int]] = []
    for token in sorted(candidates, key=len, reverse=True):
        canonical = _ALIASES.get(token, token)
        if canonical in seen:
            continue
        # Whole-word / whole-phrase matching only — a substring hit like "bhat"
        # inside "bhature" must never turn a bhatura into "white rice".
        m = re.search(r"(?<!\w)" + re.escape(token) + r"(?!\w)", cleaned)
        if not m:
            continue
        # Once "chole bhature" matches as a phrase, "chole" and "bhature" must
        # not ALSO match (overlapping span) and produce a duplicate row.
        if any(not (m.end() <= s or m.start() >= e) for s, e in matched_spans):
            continue
        row = _row_for(canonical)
        if not row:
            continue
        seen.add(canonical)
        matched_spans.append((m.start(), m.end()))
        row = dict(row)
        # The item is the patient's EXACT words — never a swapped canonical name.
        row["item"] = cleaned[m.start():m.end()]
        if row.get("gi") is not None:
            row["known"] = True
        resolved.append(row)
        if len(resolved) >= 4:
            break

    # Graceful fallback: If no candidate catalog dish matched, but the user typed
    # a message with eating/meal clues, treat it as a valid meal so novel foods
    # are not lost. Kept minimal/safe: the "dish" is the short food phrase right
    # after the eat markers ("i ate a chocolate and its reading was 311" ->
    # "chocolate"), never the whole chatty sentence. Fallback rows are flagged
    # known=False so no carbs/GI are ever invented for them.
    food_clues = ("had", "ate", "eating", "eaten", "khaya", "khaye", "khana",
                  "khaana", "meal", "lunch", "dinner", "breakfast", "nashta",
                  "bowl", "plate", "roti", "chawal", "biryani", "pani puri",
                  "chole", "paratha", "mithai", "laddu", "sandwich", "toast",
                  "omelette", "eat")
    if not resolved and text and any(c in text.lower() for c in food_clues):
        phrase = _fallback_dish(text)
        if phrase:
            plate_name = phrase[:30].strip(" ,:")
            resolved.append({
                "item": plate_name,
                "genus": "mixed meal",
                "carbs_per_100g": 0.0,
                "gi": None,
                "portion": "m",
                "known": False,
            })

    return resolved


# Words that never describe food. Filtered out of the fallback dish so a message
# like "...not the one i told was wrong" can NEVER fabricate an "I Told Was" row.
_JUNK_WORDS = {
    # pronouns / links / small words
    "i", "me", "my", "we", "us", "you", "he", "she", "it", "they", "them",
    "the", "a", "an", "and", "or", "but", "so", "to", "of", "for", "with",
    "in", "on", "at", "as", "what", "which", "who",
    # auxiliary / verbs that are not eat-markers
    "was", "were", "is", "are", "been", "being", "be", "had", "have", "has",
    "did", "do", "does", "will", "would", "can", "could", "should", "se", "us",
    "not", "no", "its", "it's", "it", "told", "tell", "said", "say", "saying",
    # meal-time / reference words
    "meal", "meals", "khana", "khaana", "dinner", "lunch", "breakfast",
    "nashta", "food", "eating", "eaten", "ate", "khaya", "khaye", "had",
    "wrong", "galat", "galti", "mistake", "same", "actually", "said",
    "took", "taken", "having", "got", "get",
    # time words
    "today", "yesterday", "tomorrow", "kal", "aaj", "abhi", "again", "then",
    "now", "rn", "subah", "shaam", "raat", "dopahar", "morning", "evening",
    "night", "after", "before", "phir", "ke", "baad",
    # hindi particles
    "bhi", "hi", "wo", "us", "ye", "tha", "thi", "theek", "sahi", "ji", "h",
    "aur", "ka", "ki", "ko", "se", "me", "mein", "par", "pe", "kar", "ke",
    "bata", "bola", "boli", "bhai", "plz", "please", "ok", "okay", "hmm",
}
_ALNUM_WORD = re.compile(r"^[a-z][a-z-]*$")


def _fallback_dish(text: str) -> str:
    """'i ate a chocolate and its reading was 311' -> 'chocolate'.
    Picks the short food phrase after the eat/meal markers, keeping only words
    that could actually name a dish. Returns '' when nothing food-like remains
    (e.g. "the meal i told was wrong" -> '') so we never invent a dish name."""
    low = text.lower()
    for m in re.finditer(
            r"\b(?:ate|had|eating|eaten|khaya|khaye|khaana|khana|meal|had\s+a|"
            r"took|having)\b", low):
        rest = low[m.end():].strip(" ,.:-")
        # stop at the first sentence/reading-like boundary
        for cut in re.finditer(r"\b(and\s+its?\b|and reading|reading\b|sugar was|"
                               r"sugar\b|was\s+\d{2,3}\b|\bat\b|\b[yY]esterday\b|"
                               r"\b(today|abhi|rn|now|again|then|so|but|and|"
                               r"phir|after|kal|aaj|subah|shaam|raat)\b|"
                               r"\btook\b|\btaken\b|\bchecked\b|\bmeasured\b|"
                               r"ke\s+baad\b)", rest):
            rest = rest[:cut.start()]
            break
        rest = re.sub(r"\b(?:the|a|an|some|about|for|of)\b", " ", rest).strip()
        words = [w for w in re.split(r"\s+", rest) if w]
        if not words:
            continue
        # keep only plausible dish words: alphabetic, not junk, not time/size
        keep = [w.strip(".,:;") for w in words
                if _ALNUM_WORD.match(w.strip(".,:;")) and w.strip(".,:;") not in _JUNK_WORDS]
        if not keep:
            continue
        dish = " ".join(keep[:3])
        return dish.title() if dish.lower() != "mixed" else "Mixed meal"
    return ""


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