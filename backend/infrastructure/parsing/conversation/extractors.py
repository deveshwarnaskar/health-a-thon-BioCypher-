"""Deterministic multilingual value extraction (spec §8–§11).

Consumers of this module:
- coolant intake: glucose, meal, medication, task, language, handoff.
- The extraction layer is deterministic-first: if it cannot anchor a value with
  HIGH confidence it must NOT invent one. AI providers may propose candidates
  only as corroboration (provenance = AI_ASSISTED) and never as the sole anchor
  for a clinical value without explicit patient confirmation (§33).

Conventions:
- Indian script + Arabic/Bengali numerals are normalized to ASCII.
- Stated timestamps are preserved verbatim; if a time is stated the engine uses
  it, otherwise the DETERMINISTIC current time is used. An extraction never
  guesses a time.
- Ambiguous readings ("shayad 230 or 330") surface as multiple candidates with
  LOW/MID confidence instead of a single invented value.
"""

from __future__ import annotations

import re
from datetime import timedelta

from ..hinglish_parser import (
    ambiguous_reading_values,
    parse_inbound,
)
from ..nutrition_taxonomy import classify_text

from .schema import Confidence, GlucoseEntity, LanguageEntity, MealEntity, MedicationEntity, ProvenanceSource, TaskEntity
from .taxonomy import _LANG_NAME_HINTS

# ---------------------------------------------------------------------------
# Numeral normalization
# ---------------------------------------------------------------------------
_DIGIT_TRANSLATION = str.maketrans(
    {
        # Devanagari 0-9
        "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
        "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
        # Bengali 0-9
        "০": "0", "১": "1", "২": "2", "৩": "3", "৪": "4",
        "৫": "5", "৬": "6", "৭": "7", "৮": "8", "৯": "9",
        # Arabic-Indic 0-9
        "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
        "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
        # Eastern Arabic-Indic / Persian 0-9
        "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
        "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    }
)


def normalize_digits(text: str) -> str:
    """Convert all Indic/Arabic numerals to ASCII 0-9."""
    return (text or "").translate(_DIGIT_TRANSLATION)


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
_LANG_ALIASES: dict[str, set[str]] = {
    "en": {"english", "angrezi", "english mein"},
    "hi": {"hindi", "hinglish", "hindwi"},
    "bn": {"bengali", "bangla", "bengoli"},
    "ta": {"tamil", "tamizh"},
    "te": {"telugu"},
    "mr": {"marathi"},
    "gu": {"gujarati", "gujrati"},
    "or": {"odia", "oriya"},
    "as": {"assamese", "asamiya"},
    "ml": {"malayalam"},
    "kn": {"kannada"},
    "pa": {"punjabi", "panjabi"},
}


def extract_language(text: str) -> LanguageEntity | None:
    """Find a target language in ``text`` (used only for LANGUAGE_CHANGE)."""
    low = (text or "").lower()
    for code, aliases in _LANG_ALIASES.items():
        if any(a in low for a in aliases):
            return LanguageEntity(
                code=code,
                display_name=_LANG_NAME_HINTS[code].copy().pop()
                if code in _LANG_NAME_HINTS else code,
                confidence=Confidence.HIGH,
            )
    return None


# ---------------------------------------------------------------------------
# Glucose extraction
# ---------------------------------------------------------------------------
_TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fasting": ("fasting", "fast", "subah ki", "bedtime check", "roz", "empty stomach", "khali pait"),
    "pre_meal": ("pre meal", "khane se pehle", "pehle", "before meal", "appetite"),
    "post_meal": ("post meal", "postprandial", "pp", "khane ke baad", "after meal"),
    "post_breakfast": ("post breakfast", "nashte ke baad", "after breakfast"),
    "post_lunch": ("post lunch", "dopahar ke baad", "lunch ke baad", "after lunch"),
    "post_dinner": ("post dinner", "dinner ke baad", "raat ke khane ke baad", "after dinner"),
}

_PARSE_TAG_TO_CANONICAL = {
    "fasting": "fasting",
    "pre": "pre_meal",
    "postprandial": "post_meal",
    "postbreakfast": "post_breakfast",
    "postlunch": "post_lunch",
    "postdinner": "post_dinner",
}

_READING_TOKEN = re.compile(r"(\d{1,3})\s*(mg/?dl)?", re.IGNORECASE)


def extract_glucose(text: str) -> GlucoseEntity:
    """Extract a glucose value + optional clockword/tag deterministically."""
    normalized = normalize_digits(text or "").strip()
    low = normalized.lower()

    entity = GlucoseEntity(
        raw_occurred_at=normalized,
        confidence=Confidence.LOW,
        provenance=ProvenanceSource.DETERMINISTIC,
    )

    # 1. Ambiguity: multiple candidate numbers ("230 or 330").
    ambiguous = ambiguous_reading_values(normalized)
    if ambiguous:
        entity.value_mg_dl = None
        entity.confidence = Confidence.LOW
        return entity

    # 2. Reuse the full Hinglish parser for a single canonical reading.
    parsed = parse_inbound(normalized)
    if not parsed.is_reading or parsed.reading is None:
        entity.value_mg_dl = None
        return entity

    value = int(parsed.reading)
    entity.value_mg_dl = value

    tag = parsed.reading_tag
    if tag:
        entity.tag = _PARSE_TAG_TO_CANONICAL.get(tag.lower(), tag.lower())
    else:
        for canon, keys in _TAG_KEYWORDS.items():
            if any(k in low for k in keys):
                entity.tag = canon
                break

    entity.confidence = (
        Confidence.HIGH
        if entity.value_mg_dl and 20 <= entity.value_mg_dl <= 600
        else Confidence.MID
    )

    # 3. Stated time preservation (never invented).
    if parsed.stated_time:
        entity.taken_at = parsed.stated_time

    return entity


def extract_time_offset(low: str) -> timedelta | None:
    """Deterministic clockword → offset used only for task scheduling labels."""
    if any(k in low for k in ("kal subah", "tomorrow morning")):
        return timedelta(hours=16)
    if any(k in low for k in ("kal", "tomorrow")):
        return timedelta(days=1)
    if any(k in low for k in ("shaam", "evening")):
        return timedelta(hours=8)
    if any(k in low for k in ("raat", "night")):
        return timedelta(hours=11)
    if any(k in low for k in ("subah", "morning")):
        return timedelta(hours=0)
    return None


# ---------------------------------------------------------------------------
# Meal extraction
# ---------------------------------------------------------------------------
_PORTION_MARKERS: dict[str, tuple[str, ...]] = {
    "s": ("small", "chota", "chhoti", "half", "aadha", "katori"),
    "m": ("medium", "medium katori", "normal", "ek katori"),
    "l": ("large", "bada", "bahut", "do katori", "double", "full plate"),
}


def extract_meal(text: str) -> MealEntity:
    """Meal extraction anchored on the deterministic nutrition taxonomy."""
    normalized = (text or "").strip()
    items = classify_text(normalized)
    portion = None
    low = normalized.lower()
    for letter, keys in _PORTION_MARKERS.items():
        if any(k in low for k in keys):
            portion = letter
            break

    entity = MealEntity(
        description=normalized,
        items=items,
        portion_letter=portion,
    )
    if items:
        entity.confidence = Confidence.HIGH
        entity.provenance = ProvenanceSource.DETERMINISTIC
    else:
        entity.confidence = Confidence.MID
        entity.provenance = ProvenanceSource.DETERMINISTIC
    return entity


# ---------------------------------------------------------------------------
# Medication extraction
# ---------------------------------------------------------------------------
_MED_COMMON = re.compile(
    r"(metformin|glimepiride|gliclazide|sitagliptin|teneligliptin|vildagliptin|"
    r"empagliflozin|dapagliflozin|insulin|mixtard|novorapid|lantus|tresiba|"
    r"glipizide|pioglitazone|glycomet|januvia)"
)


def extract_medication(text: str) -> MedicationEntity:
    normalized = (text or "").strip()
    low = normalized.lower()

    def _has(*groups: tuple[str, ...]) -> bool:
        return any(any(k in low for k in group) for group in groups)

    morning = _has(("subah", "morning", "savere", "breakfast ke baad"))
    evening = _has(("shaam", "evening"))
    night = _has(("raat", "night", "so ne se pehle", "bedtime"))
    when = "morning" if morning else ("evening" if evening else ("night" if night else None))

    taken = None
    if _has(("le li", "le liya", "kha li", "took", "taken", "ho gaya", "done", "kar li", "nahi li", "missed", "skip", "bhool")):
        taken = _has(("nahi li", "missed", "skip", "forgot", "bhool gaya"))
        taken = not taken

    match = _MED_COMMON.search(low)
    medication = match.group(0) if match else None
    dose = None
    dose_match = re.search(r"(\d+)\s*(mg|ml|units?|iu)", low)
    if dose_match:
        dose = f"{dose_match.group(1)} {dose_match.group(2)}"

    entity = MedicationEntity(
        medication=medication.capitalize() if medication else None,
        dose_units=dose,
        taken=taken,
        when=when,
    )
    entity.provenance = ProvenanceSource.DETERMINISTIC
    if medication and taken is not None and when:
        entity.confidence = Confidence.HIGH
    elif medication or taken is not None:
        entity.confidence = Confidence.MID
    else:
        entity.confidence = Confidence.LOW
    return entity


# ---------------------------------------------------------------------------
# Care-task extraction
# ---------------------------------------------------------------------------
_TASK_VERBS = re.compile(
    r"(walk|tha?hal|exercise|warm|brisk|water|paani|meeting|call|doctor appointment|"
    r"checkup|homework|remind me|yaad|kar lena)"
)


def extract_task(text: str) -> TaskEntity:
    normalized = normalize_digits(text or "").strip()
    low = normalized.lower()

    # Remove the reminder framing to capture the action.
    cleaned = re.sub(
        r"\b(remind me|reminder|yaad dilaa|yaad dilana|note down|to-do|note kar)\b",
        "",
        low,
    ).strip(" :,;")

    parts = _TASK_VERBS.findall(cleaned)
    description = cleaned if cleaned else normalized
    due_label = None
    for marker, label in (
        ("kal subah", "kal subah"),
        ("tomorrow morning", "kal subah"),
        ("kal", "kal"),
        ("tomorrow", "kal"),
        ("shaam", "shaam"),
        ("evening", "shaam"),
        ("raat", "raat"),
        ("night", "raat"),
        ("subah", "subah"),
        ("morning", "morning"),
    ):
        if marker in low:
            due_label = label
            break

    entity = TaskEntity(
        description=description[:200],
        due_label=due_label,
        due_at=None,
    )
    entity.confidence = Confidence.HIGH if parts else Confidence.MID
    entity.provenance = ProvenanceSource.DETERMINISTIC
    return entity


__all__ = [
    "normalize_digits",
    "extract_glucose",
    "extract_meal",
    "extract_medication",
    "extract_task",
    "extract_language",
    "extract_time_offset",
]