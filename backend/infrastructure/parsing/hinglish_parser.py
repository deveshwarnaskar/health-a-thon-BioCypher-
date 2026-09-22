"""Hinglish / Indian-English inbound message parser.

Ported from app/core/parse.py — all imports to app.* removed.
Pure, stateless module: no database, no network, no settings dependency.

Parses WhatsApp free-text into a typed ParsedInput:
  - Glucose readings  ("fasting 138", "sugar 142 mg/dl", "aaj subah 135 tha")
  - Meal descriptions ("2 roti dal sabzi", "rice rajma", "had biryani")
  - Confirmations     ("yes", "haan", "ok", "correct l")
  - Ambiguous readings ("shayad 230 or 330")
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Tag maps
# ---------------------------------------------------------------------------

_TAG_MAP: dict[str, str] = {
    "fasting": "fasting", "fast": "fasting", "fbs": "fasting",
    "pre": "pre", "before": "pre", "pre meal": "pre",
    "post": "postprandial", "after": "postprandial", "postprandial": "postprandial",
    "pp": "postprandial", "ppbg": "postprandial", "pp2": "postprandial",
    "post breakfast": "postbreakfast", "postbreakfast": "postbreakfast",
    "after breakfast": "postbreakfast", "pb": "postbreakfast",
    "post lunch": "postlunch", "postlunch": "postlunch",
    "after lunch": "postlunch", "pl": "postlunch",
    "post dinner": "postdinner", "postdinner": "postdinner",
    "after dinner": "postdinner", "pd": "postdinner",
    "prick": "postprandial", "fingerprick": "postprandial", "glucometer": "postprandial",
}

READING_TAG_LABELS: dict[str, str] = {
    "fasting": "fasting",
    "pre": "pre-meal",
    "postprandial": "postprandial",
    "postbreakfast": "post-breakfast",
    "postlunch": "post-lunch",
    "postdinner": "post-dinner",
}

_CONFIRM: set[str] = {
    "yes", "y", "ok", "okay", "confirm", "hmm", "ha", "haan", "han", "correct",
    "right", "theek", "theek hai", "thik", "thik h", "thik hai", "acha", "achha",
    "sahi", "sahi hai", "sahi h", "ji", "ji haan", "ji han", "done", "yep", "sure",
    "confirm_yes", "btn_confirm", "bilkul", "yup", "ha ji", "haan ji", "sahi baat",
}

_CANCEL: set[str] = {
    "cancel", "radd", "chhod do", "mat karo", "delete", "stop",
    "dismiss", "nahi chahiye", "abort", "confirm_cancel", "btn_cancel",
    "galat", "no", "nahi", "nhi", "na", "mat",
}

_PORTION_MAP: dict[str, str] = {
    "s": "s", "small": "s", "chota": "s", "chhota": "s", "kam": "s",
    "m": "m", "medium": "m", "theek": "m", "normal": "m",
    "l": "l", "large": "l", "bada": "l", "zyada": "l", "jyada": "l",
}

_TYPO_MAP = {
    r"\b(\d{2,3})[oO]\b": r"\g<1>0",
    r"\b[sS]ug[ae]r\b": "sugar",
    r"\b[sS]hug[ae]r\b": "sugar",
    r"\bfstng\b": "fasting",
    r"\bfastng\b": "fasting",
    r"\bkhali\s*pet\b": "fasting",
    r"\bchapti\b": "chapati",
    r"\bchappati\b": "chapati",
    r"\bruti\b": "roti",
    r"\brotii\b": "roti",
    r"\bdaaal\b": "dal",
    r"\bred\s+lentils?\b": "dal",
    r"\byellow\s+lentils?\b": "dal",
    r"\bmasoor\b": "dal",
    r"\bmoong\b": "dal",
    r"\bmatar\b": "mixed sabzi",
    r"\bgreen\s+peas?\b": "mixed sabzi",
    r"\bsmall\s+green\s+circular\s+(?:stuff|things?|balls?)\b": "mixed sabzi",
    r"\bsabjii\b": "sabzi",
}


def refine_text_local(text: str) -> str:
    """Correct common keyboard typos, dialects, and phonetic misspellings."""
    s = text.strip()
    for pattern, replacement in _TYPO_MAP.items():
        s = re.sub(pattern, replacement, s, flags=re.I)
    return s


_READING_FULL = re.compile(
    r"^\s*([a-z][a-z ]*?)\??\s*[:=]?\s*(\d{1,4}(?:\.\d)?)\s*(mg/dl)?\s*$", re.I
)
_READING_NUMBER_FIRST = re.compile(
    r"^\s*(\d{1,4}(?:\.\d)?)\s*(?:mg/dl)?\s+([a-z][a-z ]*?)\s*$", re.I
)
_READING_SHORT = re.compile(r"^\s*(\d{1,4}(?:\.\d)?)\s*$")

_AMBIGUITY_MARKERS = (
    "or", "ya ", "yaa", "shayad", "shaydd", "maybe", "may be", "mabbe",
    "approx", "approximately", "around", "roughly", "pata", "under", "close to",
    "almost", "nearly",
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ParsedInput:
    """Typed, sanitised result of parsing one inbound message."""

    kind: str  # text | photo | voice | reading | confirm | correct | refusal
    text: Optional[str] = None
    items: list[dict] = field(default_factory=list)
    reading: Optional[float] = None
    reading_tag: Optional[str] = None
    portion_letter: Optional[str] = None
    ts: datetime = field(default_factory=datetime.now)
    stated_time: Optional[datetime] = None
    raw: str = ""

    @property
    def is_reading(self) -> bool:
        return self.kind == "reading"

    @property
    def is_meal(self) -> bool:
        return self.kind in ("text", "photo", "voice", "correct")

    @property
    def is_confirm(self) -> bool:
        return self.kind == "confirm"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ts(raw: dict) -> datetime:
    try:
        return datetime.fromisoformat(raw["ts"].replace("Z", ""))
    except (KeyError, ValueError, AttributeError):
        return datetime.now()


def _extract_portion_letter(text: str) -> Optional[str]:
    low = text.lower()
    for token in re.findall(r"\b[a-zA-Z]+\b", low):
        if token in _PORTION_MAP:
            return _PORTION_MAP[token]
    if re.search(r"\b(150\s*ml|chhota|chota|small)\b", low):
        return "s"
    if re.search(r"\b(220\s*ml|medium|theek|normal)\b", low):
        return "m"
    if re.search(r"\b(350\s*ml|large|bada)\b", low):
        return "l"
    return None


def _is_cancel(text: str) -> bool:
    low = text.strip().lower()
    if low in _CANCEL:
        return True
    cleaned = re.sub(r"[^\w\s]", " ", low)
    words = cleaned.split()
    if not words:
        return False
    if len(words) <= 5 and all(
        w in _CANCEL or w in ("hai", "h", "ji", "to", "sir", "kripya", "please", "karo", "do")
        for w in words
    ):
        return True
    return False


def _is_confirm(text: str) -> bool:
    low = text.strip().lower()
    if low in _CONFIRM:
        return True
    cleaned = re.sub(r"[^\w\s]", " ", low)
    words = cleaned.split()
    if not words:
        return False
    filler_and_portion = {
        "hai", "h", "ji", "to", "bhi", "tha", "sir", "portion", "kripya", "please",
        "small", "medium", "large", "s", "m", "l", "chota", "chhota", "bada", "normal",
        "katori", "katoris", "bowl", "plate",
    }
    if len(words) <= 6 and all(w in _CONFIRM or w in filler_and_portion for w in words):
        if any(w in _CONFIRM for w in words) or any(w in _PORTION_MAP for w in words):
            return True
    return False


def _tag_from_text(prefix: str, default_none: bool = False) -> Optional[str]:
    cleaned = prefix.lower().strip()
    if cleaned in _TAG_MAP:
        return _TAG_MAP[cleaned]
    if re.search(r"\b(breakfast|nashta|pb)\b", cleaned):
        return "postbreakfast"
    if re.search(r"\b(lunch|dopahar|pl)\b", cleaned):
        return "postlunch"
    if re.search(r"\b(dinner|raat|pd)\b", cleaned):
        return "postdinner"
    if re.search(r"\b(fasting|fast|fbs|khali\s*pet|morning|subah)\b", cleaned):
        return "fasting"
    if re.search(r"\b(pre|before|pehle)\b", cleaned):
        return "pre"
    return None if default_none else "postprandial"


def _as_reading(raw: dict, value: object) -> ParsedInput:
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        v = math.nan
    tag = str(raw.get("reading_tag") or "").lower().strip()
    tag = _TAG_MAP.get(tag, tag or "postprandial")
    if not (20 <= v <= 600):
        return ParsedInput(kind="refusal", raw=f"reading out of range: {value}")
    return ParsedInput(kind="reading", reading=v, reading_tag=tag, ts=_ts(raw), raw=str(value))


def _reading_from_text(text: str, raw: Optional[dict] = None) -> Optional[ParsedInput]:
    ts = _ts(raw) if raw else datetime.now()
    stripped = text.strip()

    # 1. Bare number
    m = _READING_SHORT.match(stripped)
    if m:
        val = float(m.group(1))
        return ParsedInput(kind="reading", reading=val, reading_tag="postprandial", ts=ts, raw=stripped)

    # 2. Tag followed by number (e.g. "fasting 138", "before meal: 95")
    m_full = _READING_FULL.match(stripped)
    if m_full:
        tag = _tag_from_text(m_full.group(1).lower().strip(), default_none=True)
        if tag is not None:
            val = float(m_full.group(2))
            return ParsedInput(kind="reading", reading=val, reading_tag=tag, ts=ts, raw=stripped)

    # 3. Number followed by tag (e.g. "180 fasting", "95 before meal", "190 after dinner")
    m_num_first = _READING_NUMBER_FIRST.match(stripped)
    if m_num_first:
        tag = _tag_from_text(m_num_first.group(2).lower().strip(), default_none=True)
        if tag is not None:
            val = float(m_num_first.group(1))
            return ParsedInput(kind="reading", reading=val, reading_tag=tag, ts=ts, raw=stripped)

    # 4. Natural conversational sentence
    low = stripped.lower()
    context_words = (
        "sugar", "glucose", "bg", "fbs", "rbs", "ppbg", "mg/dl", "mgdl",
        "reading", "level", "fasting", "fast", "khali", "pet", "subah",
        "morning", "pre", "pehle", "post", "after", "baad", "breakfast",
        "nashta", "lunch", "dopahar", "dinner", "raat", "before", "meal",
        "prick", "pricking", "fingerprick", "finger prick", "glucometer", "strip", "test",
    )
    if any(cw in low for cw in context_words):
        # Strip time tokens (e.g. "8 am", "8:30 pm", "8 baje") so time numbers aren't confused for glucose
        cleaned_for_reading = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm|baje|ta)\b", "", low)
        matches = re.findall(r"\b(\d{1,4}(?:\.\d)?)\s*(?:mg/?dl)?\b", cleaned_for_reading)
        for m_str in matches:
            try:
                val = float(m_str)
                if 20 <= val <= 600:
                    return ParsedInput(
                        kind="reading",
                        reading=val,
                        reading_tag=_tag_from_text(low) or "postprandial",
                        ts=ts,
                        raw=stripped,
                    )
            except ValueError:
                continue

    return None


# ---------------------------------------------------------------------------
# Stated Time Extraction
# ---------------------------------------------------------------------------

def extract_stated_time(text: str, reference_time: Optional[datetime] = None) -> Optional[datetime]:
    """Extract stated time of day/event from Hinglish or English free-text.

    Supports expressions such as:
      - 'aaj subah' / 'aj shokale' (today morning ~08:00)
      - 'kal raat' / 'yesterday night' (yesterday ~21:00)
      - 'dopahar' / 'afternoon' (~13:00)
      - 'shaam' / 'evening' (~18:00)
      - '8 am', '8:30 pm', '8 baje'
    Returns None if no time expression is found.
    """
    if not text:
        return None

    low = text.lower()
    ref = reference_time or datetime.now()
    tz = ref.tzinfo

    # Determine day offset
    day_offset = 0
    if re.search(r"\b(kal|yesterday|goto\s*kal)\b", low):
        day_offset = -1
    elif re.search(r"\b(aaj|aj|today)\b", low):
        day_offset = 0

    target_date = (ref + timedelta(days=day_offset)).date()

    # 1. Look for explicit time: e.g. "8 am", "8:30 pm", "8am", "8:30pm"
    m_time = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", low)
    if m_time:
        hour = int(m_time.group(1))
        minute = int(m_time.group(2) or 0)
        ampm = m_time.group(3).lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        return datetime(target_date.year, target_date.month, target_date.day, hour, minute, 0, tzinfo=tz)

    # 2. Look for "8 baje" or "8 ta"
    m_baje = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(?:baje|ta)\b", low)
    if m_baje:
        hour = int(m_baje.group(1))
        minute = int(m_baje.group(2) or 0)
        # Check context for am/pm
        if re.search(r"\b(raat|rat|night|shaam|shondha|evening|dopahar|dupur)\b", low):
            if hour < 12:
                hour += 12
        return datetime(target_date.year, target_date.month, target_date.day, hour, minute, 0, tzinfo=tz)

    # 3. Categorical time-of-day periods
    if re.search(r"\b(subah|shokal|shokale|morning|breakfast|nashta)\b", low):
        return datetime(target_date.year, target_date.month, target_date.day, 8, 0, 0, tzinfo=tz)
    if re.search(r"\b(dopahar|dupur|afternoon|lunch)\b", low):
        return datetime(target_date.year, target_date.month, target_date.day, 13, 0, 0, tzinfo=tz)
    if re.search(r"\b(shaam|shondha|evening|tea\s*time)\b", low):
        return datetime(target_date.year, target_date.month, target_date.day, 18, 0, 0, tzinfo=tz)
    if re.search(r"\b(raat|rat|night|dinner)\b", low):
        return datetime(target_date.year, target_date.month, target_date.day, 21, 0, 0, tzinfo=tz)

    if day_offset != 0:
        return datetime(target_date.year, target_date.month, target_date.day, ref.hour, ref.minute, 0, tzinfo=tz)

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_inbound(text: str, ts: Optional[str] = None) -> ParsedInput:
    """Parse a single free-text WhatsApp message. Never raises.

    Args:
        text: Raw message body (already refine-normalised if applicable).
        ts:   Optional ISO timestamp string.

    Returns a ``ParsedInput`` with kind in:
        ``reading`` | ``confirm`` | ``correct`` | ``text`` | ``refusal``
    """
    if not text or not text.strip():
        return ParsedInput(kind="refusal", raw="")

    raw_dict: dict = {"ts": ts} if ts else {}
    parsed_ts = _ts(raw_dict) if ts else datetime.now()

    text_stripped = text.strip()
    low = text_stripped.lower()
    stated = extract_stated_time(text_stripped, reference_time=parsed_ts)

    # 1. Reading?
    r = _reading_from_text(text_stripped, raw_dict if ts else None)
    if r:
        r.stated_time = stated
        return r

    # 2. Cancel?
    if _is_cancel(text_stripped):
        return ParsedInput(kind="cancel", text=low, ts=parsed_ts, stated_time=stated, raw=low)

    # 3. Confirm / correct?
    portion_letter = _extract_portion_letter(text_stripped)
    if _is_confirm(text_stripped):
        return ParsedInput(
            kind="confirm",
            text=low,
            portion_letter=portion_letter,
            ts=parsed_ts,
            stated_time=stated,
            raw=low,
        )

    pm = re.match(r"^(correct|nhi|nahi|no)\s*.?\s*([a-z]+)$", low)
    portion_word = (pm.group(2) if pm else low).strip()
    if portion_word in _PORTION_MAP:
        return ParsedInput(
            kind="confirm",
            text=low,
            portion_letter=_PORTION_MAP[portion_word],
            ts=parsed_ts,
            stated_time=stated,
            raw=low,
        )

    cm = re.match(r"^correct\s+(.+)$", low)
    if cm:
        return ParsedInput(kind="correct", text=cm.group(1), ts=parsed_ts, stated_time=stated, raw=low)

    # 4. Default: meal text
    return ParsedInput(kind="text", text=text_stripped, ts=parsed_ts, stated_time=stated, raw=text_stripped)


def ambiguous_reading_values(text: str) -> list[float]:
    """Return candidate glucose values when a message is ambiguously multi-valued.

    E.g. "shayad 230 or 330" → [230.0, 330.0].
    Returns [] when unambiguous.
    """
    if not text:
        return []
    low = str(text).lower()
    if not any(m in low for m in _AMBIGUITY_MARKERS):
        return []
    vals = sorted(
        {float(m) for m in re.findall(r"\b\d{2,3}(?:\.\d)?\b", low) if 20 <= float(m) <= 600}
    )
    return vals if len(vals) >= 2 else []


def describe_items(items: list[dict]) -> str:
    """Patient-facing echo of detected plate — portion labels only, no numbers."""
    from backend.infrastructure.parsing.nutrition_taxonomy import KATORI_LABELS

    if not items:
        return "nothing I could recognise yet"
    parts = []
    for it in items[:4]:
        label = KATORI_LABELS.get(it.get("portion", "m"), "Medium (220 ml)")
        parts.append(f"{it['item']} · {label}")
    return ", ".join(parts) + ("." if parts else "")


__all__ = [
    "ParsedInput",
    "parse_inbound",
    "ambiguous_reading_values",
    "describe_items",
    "extract_stated_time",
    "READING_TAG_LABELS",
    "_is_confirm",
    "_is_cancel",
    "_extract_portion_letter",
]
