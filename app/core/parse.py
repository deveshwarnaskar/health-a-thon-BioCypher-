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
from datetime import datetime, timedelta
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

# Patient-facing (Hinglish) names for the same tags in confirmations.
PATIENT_TAG_LABELS = {
    "fasting": "fasting", "pre": "khane se pehle",
    "postprandial": "khane ke baad",
    "postbreakfast": "breakfast ke baad",
    "postlunch": "lunch ke baad",
    "postdinner": "dinner ke baad",
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


# ---- follow-up answer detection (deterministic, dashboard-driven) ------
# Short replies that answer the reading-context/tag question the AI asked
# ("khane ke baad", "fasting", "post lunch" ...). Never treated as food/sugar.
_TAG_CUES = ("fasting", "fast", "fbs", "khali", "morning", "subah",
             "breakfast", "nashta", "lunch", "dopahar", "dinner", "raat",
             "pre", "before", "pehle", "post", "after", "baad", "pp", "khane")
_TAG_DENY = ("roti", "sabzi", "sabji", "paneer", "chana", "dahi", "chawal",
             "rice", "paratha", "dosa", "idli", "khana", "khaana", "mithai",
             "photo", "picture")

_RESOLUTION_CUES = ("hai", "theek", "thik", "sahi", "sachi", "correct",
                    "confirm", "pakka", "wala", "2nd", "second", "1st",
                    "first", "it is", "it's", "yahe", "yhi", "hi hai",
                    "definitely", "exact", "exactly", "choose ", "select ",
                    " wali")


def _is_tag_answer(text: Optional[str]) -> Optional[str]:
    """'khane ke baad' / 'fasting' / 'post lunch' -> the reading-context tag.

    Returns the tag when the message is a short answer to the tag question the
    AI asked, otherwise None. Purely deterministic.
    """
    low = str(text or "").strip().lower()
    if not low or len(low) > 22:
        return None
    if re.search(r"\d", low):
        return None
    if any(w in low for w in _TAG_DENY):
        return None
    if not any(c in low for c in _TAG_CUES):
        return None
    return _tag_from_text(low)


def _resolution_cue_value(text: Optional[str]) -> Optional[float]:
    """A single glucose value offered as THE answer ("230 hai", "it's 230",
    "first wala 230"). Returns the value or None."""
    low = str(text or "").lower()
    nums = [float(m) for m in re.findall(r"\b\d{2,3}(?:\.\d)?\b", low)
            if 20 <= float(m) <= 600]
    if len(nums) != 1:
        return None
    if any(c in low for c in _RESOLUTION_CUES):
        return nums[0]
    return None


def _single_number_value(text: Optional[str]) -> Optional[float]:
    low = str(text or "")
    nums = [float(m) for m in re.findall(r"\b\d{2,3}(?:\.\d)?\b", low)
            if 20 <= float(m) <= 600]
    return nums[0] if len(nums) == 1 else None


def _is_dup_answer(text: Optional[str]) -> Optional[str]:
    """Answer to the 'already logged — naya ya mistake?' question."""
    low = str(text or "").lower().strip()
    if not low:
        return None
    if re.search(r"\b(naya|nayi|new)\b", low):
        return "new"
    if re.search(r"\b(no?[h]?i add|dont add|do not add)\b", low):
        return "skip"
    if low in ("nahi", "nai", "no", "nhi", "mistake", "galat", "galti",
               "skip", "pehle se hai", "already hai", "already logged"):
        return "skip"
    if re.search(r"\b(mistake|galat|galti|pehle se|already)\b", low) and len(low.split()) <= 3:
        return "skip"
    return None


# ---- explicit date/time references ("yesterday evening near 3pm") -------
_TIME_SHIFTS = (
    (r"\b(parso[ _]kal|day before yesterday|two days ago|2 din pehle|do din pehle)\b", -2),
    (r"\b(parso[ _]parso|three days ago|3 din pehle|teen din pehle)\b", -3),
    (r"\b(pichhle[ _]din|past[ _]few[ _]days)\b", -3),
    (r"\b(kal|yesterday|last[ _]night|last[ _]evening)\b", -1),
    (r"\b(aaj|today|abh?i)\b", 0),
)
_PART_DEFAULTS = (
    (("subah", "savre", "morning", "pratha", "praata"), 8),
    (("dophar", "noon", "afternoon", "doupahar"), 13),
    (("shaam", "evening", "sanja", "sayankar"), 18),
    (("raat", "night", "rathri", "midnight"), 21),
)


def time_reference(text: Optional[str]) -> tuple[int, Optional[int]]:
    """(day_shift, minute_of_day|None) from explicit words in the message."""
    low = str(text or "").lower()
    shift = 0
    for pat, s in _TIME_SHIFTS:
        if re.search(pat, low):
            shift = s
            break
    minute: Optional[int] = None
    m = re.search(r"(\d{1,2})(?::(\d{2}))?(?:\s*(am|pm|baje)\b)", low)
    if not m:
        m = re.search(r"(\d{1,2}):(\d{2})\b", low)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2) or 0)
        period = (m.group(3) or "").strip()
        if period == "pm" and hh < 12:
            hh += 12
        elif period == "am" and hh == 12:
            hh = 0
        elif period == "baje" and hh < 12:
            pass
        minute = hh * 60 + mm
    if minute is None:
        for words, default_h in _PART_DEFAULTS:
            if any(w in low for w in words):
                minute = default_h * 60
                break
    return shift, minute


def reading_timestamp(text: Optional[str], msg_ts: str) -> datetime:
    """Timestamp for this reading: the message time by default, overridden
    only when the patient explicitly mentions another day/time
    ("yesterday evening near 3pm", ...)."""
    try:
        base = datetime.fromisoformat(str(msg_ts).replace("Z", "")[:19])
    except (ValueError, TypeError):
        base = datetime.now()
    shift, minute = time_reference(text)
    if shift == 0 and minute is None:
        return base
    if minute is None:
        minute = base.hour * 60 + base.minute
    day = base.date() + timedelta(days=shift)
    return datetime.combine(day, datetime.min.time().replace(
        hour=minute // 60, minute=minute % 60))


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