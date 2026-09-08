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
      "reading_tag": "fasting|pre|postprandial"
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
    r"^\s*([a-z]+)\??\s*[:=]?\s*(\d{2,3}(?:\.\d)?)\s*(mg/dl)?\s*$", re.I)
_READING_SHORT = re.compile(r"^\s*(\d{2,3}(?:\.\d)?)\s*$")
_TAG_MAP = {"fasting": "fasting", "fast": "fasting", "fbs": "fasting",
            "pre": "pre", "before": "pre", "pre meal": "pre",
            "post": "postprandial", "after": "postprandial", "postprandial": "postprandial",
            "pp": "postprandial", "ppbg": "postprandial", "pp2": "postprandial"}

_CONFIRM = {"yes", "y", "ok", "okay", "confirm", "hmm", "ha", "correct",
            "right", "theek", "acha", "haan", "hey"}


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


def parse_inbound(raw: dict, cfg: Settings, mock_vision=None) -> ParsedInput:
    """Normalize a raw wire message. Never raises."""
    if not isinstance(raw, dict):
        return ParsedInput(kind="refusal", raw=str(raw)[:80])

    kind = raw.get("kind")
    text = raw.get("text")
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
        if low in _CONFIRM:
            return ParsedInput(kind="confirm", text=low, ts=_ts(raw), raw=low)
        pm = re.match(r"^(correct|nhi|nahi|no)\s*.?\s*([slm])$", low)
        if pm or low in {"s", "m", "l"}:
            letter = (pm.group(2) if pm else low)
            return ParsedInput(kind="confirm", text=low, portion_letter=letter,
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
    tag = str(raw.get("reading_tag") or "").lower()
    tag = _TAG_MAP.get(tag, tag or "postprandial")
    if not (20 <= v <= 600):
        return ParsedInput(kind="refusal", raw=f"reading out of range: {value}")
    return ParsedInput(kind="reading", reading=v, reading_tag=tag,
                       ts=_ts(raw), raw=str(value))


def _reading_from_text(text: str, raw: Optional[dict] = None) -> Optional[ParsedInput]:
    ts = _ts(raw) if raw else datetime.now()
    m = _READING_FULL.match(text)
    if m:
        val = float(m.group(2))
        if 20 <= val <= 600:
            return ParsedInput(kind="reading", reading=val,
                               reading_tag=_TAG_MAP.get(m.group(1).lower(), "postprandial"),
                               ts=ts, raw=text.strip())
        return ParsedInput(kind="refusal", raw=text.strip())
    m = _READING_SHORT.match(text.strip())
    if m:
        val = float(m.group(1))
        if 20 <= val <= 600:
            return ParsedInput(kind="reading", reading=val, reading_tag="postprandial",
                               ts=ts, raw=text.strip())
        return ParsedInput(kind="refusal", raw=text.strip())
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