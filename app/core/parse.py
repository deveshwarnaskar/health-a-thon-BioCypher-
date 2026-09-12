"""Turn a raw inbound message into a typed, safe ParsedInput.

The prototype speaks one neutral wire-format (dict) that either the WhatsApp
Cloud webhook or the built-in simulator produces:

    {
      "patient_id": int,          # which patient this message belongs to
      "sender_phone": str,        # stable identity — decides patient vs caregiver role
      "kind": "text"|"photo"|"voice"|"reading"|None,   # None = auto-detect
      "ts": "2026-...Z",          # optional, defaults to now
      "text": str|None,           # raw text / STT result / photo caption
      "photo_path": str|None,     # local path when kind == photo
      "reading": float|None,      # glucose value when ready-provided
      "reading_tag": "fasting|pre|postprandial|postbreakfast|postlunch|postdinner"
    }

Parsing never raises: anything unparseable becomes a Refusal object so the
channel gets a polite help message instead of a crash.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..config import Settings

_READING_FULL = re.compile(
    r"^\s*([a-z][a-z ]*?)\??\s*[:=]?\s*(\d{2,3}(?:\.\d)?)\s*(mg/dl)?\s*$", re.I)
_READING_SHORT = re.compile(r"^\s*(\d{2,3}(?:\.\d)?)\s*$")
_TAG_MAP = {"fasting": "fasting", "fast": "fasting", "fbs": "fasting",
            "pre": "pre", "before": "pre", "pre meal": "pre",
            "post": "postprandial", "after": "postprandial", "postprandial": "postprandial",
            "pp": "postprandial", "ppbg": "postprandial", "pp2": "postprandial",
            "post breakfast": "postbreakfast", "postbreakfast": "postbreakfast",
            "after breakfast": "postbreakfast", "pb": "postbreakfast",
            "post lunch": "postlunch", "postlunch": "postlunch",
            "after lunch": "postlunch", "pl": "postlunch",
            "post dinner": "postdinner", "postdinner": "postdinner",
            "after dinner": "postdinner", "pd": "postdinner",
            "prick": "postprandial", "fingerprick": "postprandial", "glucometer": "postprandial"}

READING_TAG_LABELS = {
    "fasting": "fasting", "pre": "pre-meal",
    "postprandial": "postprandial",
    "postbreakfast": "post-breakfast",
    "postlunch": "post-lunch",
    "postdinner": "post-dinner",
}

_CONFIRM = {"yes", "y", "ok", "okay", "confirm", "hmm", "ha", "haan", "correct",
            "right", "theek", "theek hai", "thik", "thik h", "acha", "achha",
            "sahi", "sahi hai", "ji", "ji haan", "done", "yep", "sure"}

_PORTION_MAP = {
    "s": "s", "small": "s", "chota": "s", "chhota": "s", "kam": "s",
    "m": "m", "medium": "m", "theek": "m", "normal": "m",
    "l": "l", "large": "l", "bada": "l", "zyada": "l", "jyada": "l",
}


@dataclass
class ParsedInput:
    kind: str                      # text | photo | voice | reading | confirm | correct | refusal
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


def _is_confirm(text: str) -> bool:
    low = text.strip().lower()
    if low in _CONFIRM:
        return True
    words = low.split()
    if len(words) <= 4 and all(w in _CONFIRM or w in ("hai", "h", "ji", "to", "bhi", "tha", "sir") for w in words):
        return True
    return False


def _tag_from_text(prefix: str) -> str:
    cleaned = prefix.lower().strip()
    if cleaned in _TAG_MAP:
        return _TAG_MAP[cleaned]
    # Meal-slot specific words take precedence over generic fasting
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
    if re.search(r"\b(post|after|baad|pp|ppbg)\b", cleaned):
        return "postprandial"
    return "postprandial"


def parse_inbound(raw: dict, cfg: Settings, mock_vision=None) -> ParsedInput:
    """Normalize a raw wire message. Never raises."""
    if not isinstance(raw, dict):
        return ParsedInput(kind="refusal", raw=str(raw)[:80])

    kind = raw.get("kind")
    text = raw.get("text")
    if text:
        from .ai import refine_text_local
        text = refine_text_local(text)

    photo = raw.get("photo_path")
    reading = raw.get("reading")

    if kind == "reading" or reading is not None:
        return _as_reading(raw, reading)

    # A raw text that is itself a glucose number/reading → reading.
    if kind in (None, "text") and text:
        r = _reading_from_text(text, raw)
        if r:
            return r

    # Confirm / correct replies to a pending meal estimate.
    if text:
        low = text.strip().lower()
        if _is_confirm(text):
            return ParsedInput(kind="confirm", text=low, ts=_ts(raw), raw=low)
        pm = re.match(r"^(correct|nhi|nahi|no)\s*.?\s*([a-z]+)$", low)
        portion_word = (pm.group(2) if pm else low).strip()
        if portion_word in _PORTION_MAP:
            return ParsedInput(kind="confirm", text=low,
                               portion_letter=_PORTION_MAP[portion_word],
                               ts=_ts(raw), raw=low)
        cm = re.match(r"^correct\s+(.+)$", low)
        if cm:
            return ParsedInput(kind="correct", text=cm.group(1), ts=_ts(raw), raw=low)

    if kind in (None, "text", "voice") and text:
        return ParsedInput(kind="text", text=text, items=_items(text, cfg),
                           ts=_ts(raw), raw=text)

    if kind == "photo" or photo:
        items = _mock_photo(raw, cfg, mock_vision)
        return ParsedInput(kind="photo", text=text, items=items,
                           ts=_ts(raw), raw="photo")

    return ParsedInput(kind="refusal", raw="unrecognized input")


_AMBIGUITY_MARKERS = (
    "or", "ya ", "yaa", "shayad", "shaydd", "maybe", "may be", "mabbe",
    "approx", "approximately", "around", "roughly", "pata", "under", "close to",
    "almost", "nearly",
)


def ambiguous_reading_values(text: str) -> list[float]:
    """Deterministic (no-LLM) detector for an UNRESOLVED glucose reading.

    Returns the sorted candidate values (20-600) when a single message carries
    two or more plausible readings joined by an uncertainty/alternative word
    ("230 or 330", "shayad 230 ya 330..."). Used so the webhook path never also
    fires a meal portion-confirm for the same message — the dashboard AI intake
    asks the one clarifying question instead. Returns [] when unambiguous.
    """
    if not text:
        return []
    low = str(text).lower()
    if not any(m in low for m in _AMBIGUITY_MARKERS):
        return []
    vals = sorted({float(m) for m in re.findall(r"\b\d{2,3}(?:\.\d)?\b", low)
                   if 20 <= float(m) <= 600})
    return vals if len(vals) >= 2 else []


def _ts(raw: dict) -> datetime:
    try:
        return datetime.fromisoformat(raw["ts"].replace("Z", ""))
    except (KeyError, ValueError, AttributeError):
        return datetime.now()


def _as_reading(raw: dict, value) -> ParsedInput:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = math.nan
    tag = str(raw.get("reading_tag") or "").lower().strip()
    tag = _TAG_MAP.get(tag, tag or "postprandial")
    if not (20 <= v <= 600):
        return ParsedInput(kind="refusal", raw=f"reading out of range: {value}")
    return ParsedInput(kind="reading", reading=v, reading_tag=tag,
                       ts=_ts(raw), raw=str(value))


def _reading_from_text(text: str, raw: Optional[dict] = None) -> Optional[ParsedInput]:
    ts = _ts(raw) if raw else datetime.now()
    m = _READING_SHORT.match(text.strip())
    if m:
        val = float(m.group(1))
        if 20 <= val <= 600:
            return ParsedInput(kind="reading", reading=val, reading_tag="postprandial",
                               ts=ts, raw=text.strip())
        return ParsedInput(kind="refusal", raw=text.strip())

    m_full = _READING_FULL.match(text)
    if m_full:
        val = float(m_full.group(2))
        prefix = m_full.group(1).lower().strip()
        tag = _tag_from_text(prefix)
        if 20 <= val <= 600:
            return ParsedInput(kind="reading", reading=val, reading_tag=tag,
                               ts=ts, raw=text.strip())
        return ParsedInput(kind="refusal", raw=text.strip())

    # Natural conversational pattern: e.g. "aaj subah fasting 135 tha", "my sugar is 142"
    low = text.lower().strip()
    # Find any standalone 2 to 3 digit number (with optional decimal)
    num_match = re.search(r"\b(\d{2,3}(?:\.\d)?)\s*(?:mg/?dl)?\b", low)
    if num_match:
        context_words = (
            "sugar", "glucose", "bg", "fbs", "rbs", "ppbg", "mg/dl", "mgdl",
            "reading", "level", "fasting", "fast", "khali", "pet", "subah",
            "morning", "pre", "pehle", "post", "after", "baad", "breakfast",
            "nashta", "lunch", "dopahar", "dinner", "raat",
            "prick", "pricking", "fingerprick", "finger prick", "glucometer", "strip", "test"
        )
        if any(cw in low for cw in context_words):
            try:
                val = float(num_match.group(1))
            except ValueError:
                return None
            if not (20 <= val <= 600):
                return ParsedInput(kind="refusal", raw=text.strip())

            tag = _tag_from_text(low)
            return ParsedInput(kind="reading", reading=val, reading_tag=tag,
                               ts=ts, raw=text.strip())

    return None


def _items(text: str, cfg: Settings) -> list[dict]:
    from .nutrition import estimate_carbs_g, classify_text, KATORI_LABELS
    rows = classify_text(text)
    out = []
    for r in rows:
        out.append({
            "item": r["item"], "genus": r["genus"],
            "portion": r.get("portion", "m"),
            "portion_label": KATORI_LABELS.get(r.get("portion", "m")),
            "carbs": estimate_carbs_g(cfg.katori(r.get("portion", "m")), r),
            "gi": r["gi"],
        })
    return out


def _mock_photo(raw: dict, cfg: Settings, mock_vision) -> list[dict]:
    from .nutrition import estimate_carbs_g, detect_photo, KATORI_LABELS
    if mock_vision is not None and callable(mock_vision):
        rows = mock_vision(raw.get("photo_path") or "", datetime.now().hour, 0)
    else:
        ts = raw.get("ts", "")
        day = int(ts[:10].replace("-", "")) if len(ts) >= 10 else int(datetime.now().strftime("%Y%m%d"))
        rows = detect_photo(datetime.now().hour, day, cfg)
    out = []
    for r in rows:
        out.append({
            "item": r["item"], "genus": r["genus"],
            "portion": r.get("portion", "m"),
            "portion_label": KATORI_LABELS.get(r.get("portion", "m")),
            "carbs": estimate_carbs_g(cfg.katori(r.get("portion", "m")), r),
            "gi": r["gi"],
        })
    # health-year safety: keep the echo identical for later text correction
    return out


def describe_items(items: list[dict]) -> str:
    """Patient-facing echo of a detected plate — portion labels only, never numbers."""
    if not items:
        return "nothing I could recognise yet"
    parts = []
    for it in items[:4]:
        label = it.get("portion_label", "Medium (220 ml)")
        parts.append(f"{it['item']} · {label}")
    return ", ".join(parts) + ("." if parts else "")