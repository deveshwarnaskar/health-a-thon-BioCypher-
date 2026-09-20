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
from datetime import datetime
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
    "yes", "y", "ok", "okay", "confirm", "hmm", "ha", "haan", "correct",
    "right", "theek", "theek hai", "thik", "thik h", "acha", "achha",
    "sahi", "sahi hai", "ji", "ji haan", "done", "yep", "sure",
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


def _is_confirm(text: str) -> bool:
    low = text.strip().lower()
    if low in _CONFIRM:
        return True
    words = low.split()
    return len(words) <= 4 and all(
        w in _CONFIRM or w in ("hai", "h", "ji", "to", "bhi", "tha", "sir")
        for w in words
    )


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
    num_match = re.search(r"\b(\d{1,4}(?:\.\d)?)\s*(?:mg/?dl)?\b", low)
    if num_match:
        context_words = (
            "sugar", "glucose", "bg", "fbs", "rbs", "ppbg", "mg/dl", "mgdl",
            "reading", "level", "fasting", "fast", "khali", "pet", "subah",
            "morning", "pre", "pehle", "post", "after", "baad", "breakfast",
            "nashta", "lunch", "dopahar", "dinner", "raat", "before", "meal",
            "prick", "pricking", "fingerprick", "finger prick", "glucometer", "strip", "test",
        )
        if any(cw in low for cw in context_words):
            try:
                val = float(num_match.group(1))
            except ValueError:
                return None
            return ParsedInput(kind="reading", reading=val, reading_tag=_tag_from_text(low) or "postprandial", ts=ts, raw=stripped)

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

    # 1. Reading?
    r = _reading_from_text(text_stripped, raw_dict if ts else None)
    if r:
        return r

    # 2. Confirm / correct?
    if _is_confirm(text_stripped):
        return ParsedInput(kind="confirm", text=low, ts=parsed_ts, raw=low)

    pm = re.match(r"^(correct|nhi|nahi|no)\s*.?\s*([a-z]+)$", low)
    portion_word = (pm.group(2) if pm else low).strip()
    if portion_word in _PORTION_MAP:
        return ParsedInput(
            kind="confirm",
            text=low,
            portion_letter=_PORTION_MAP[portion_word],
            ts=parsed_ts,
            raw=low,
        )

    cm = re.match(r"^correct\s+(.+)$", low)
    if cm:
        return ParsedInput(kind="correct", text=cm.group(1), ts=parsed_ts, raw=low)

    # 3. Default: meal text
    return ParsedInput(kind="text", text=text_stripped, ts=parsed_ts, raw=text_stripped)


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
    "READING_TAG_LABELS",
]
