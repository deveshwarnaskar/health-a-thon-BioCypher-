"""AI intake notifier — a decoupled, on-demand consumer of STORED raw inbound rows.

This module is intentionally separate from the WhatsApp webhook path:

  * the webhook captures raw patient input and returns HTTP 200 (unchanged);
  * this module reads those STORED rows from the database later — via the
    dashboard ("Run AI Intake Analysis", POST /api/v1/analyze/stored) or the
    optional background worker (AAHAAR_AI_INTAKE=on);
  * follow-up replies go out through the exact same outbound channel the doctor
    composer uses (backend.send), never from inside the webhook handler.

Gemini is used purely as an INPUT-COLLECTION assistant, not a doctor: it asks
for missing logging fields (reading number, reading context tag, meal items,
portion) in short Hinglish and never gives medical advice, targets, diagnoses,
or prescriptions. If Gemini is unavailable, a deterministic local notifier
takes over so the flow never breaks and the webhook behaviour never changes.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..config import Settings
from .parse import ambiguous_reading_values, parse_inbound


def _meal_items(text: str, cfg: Settings) -> list:
    """Deterministically extract dish items (with carbs/GI) from stored text.

    Falls back to the nutrition classifier's "mixed meal" row for novel foods,
    so patient-described meals are never lost even when the dish is not in the
    catalog (e.g. 'whole steak with red wine').
    """
    from .parse import _items
    return list(_items(text, cfg))

# Words that mark the reading-context tag as explicitly stated by the patient.
_TAG_KEYWORDS = (
    "fasting", "fast", "fbs", "khali", "morning", "subah",
    "breakfast", "nashta", "pb", "lunch", "dopahar", "pl",
    "dinner", "raat", "pd", "pre", "before", "pehle", "post", "after", "baad",
)

# Words that imply a glucose reading is being reported (even without a number).
_READING_HINTS = ("sugar", "glucose", "fasting", "fast", "khali", "prick",
                  "glucometer", "reading", "level", "bg", "fbs", "rbs", "ppbg")

# Portion words that make the meal input complete.
_PORTION_WORDS = ("small", "medium", "large", "chota", "chhota", "chhoti",
                  "kam", "badi", "bara", "bada", "do roti", "2 roti")

_MODELS = ("gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite")


def _reading_deduction(text: str) -> dict:
    """Deterministic deduction of a glucose READING from a stored message.

    Returns {"value": float|None, "tag": str|None, "candidates": [..],
             "status": "resolved"|"ambiguous"|"none"}.
    Ambiguous messages (>=2 plausible values like "230 or 330") are never picked
    — they wait for the patient's resolution. A single candidate only counts as
    resolved when the message also carries reading context words.
    """
    cand = ambiguous_reading_values(text)
    if cand:
        return {"value": None, "tag": None, "candidates": cand, "status": "ambiguous"}
    nums = [float(m) for m in re.findall(r"\b\d{2,3}(?:\.\d)?\b", (text or "").lower())
            if 20 <= float(m) <= 600]
    if len(nums) == 1:
        low = (text or "").lower()
        if any(k in low for k in _READING_HINTS):
            return {"value": nums[0], "tag": None, "candidates": [],
                    "status": "resolved"}
    return {"value": None, "tag": None, "candidates": [], "status": "none"}


@dataclass
class IntakeResult:
    intent: str
    missing: list
    reply: str
    should_reply: bool
    raw_text: str
    confidence: float
    analyzed_by: str = "local-refiner"
    reading_value: Optional[float] = None
    reading_tag: Optional[str] = None
    reading_candidates: list = field(default_factory=list)
    reading_status: str = "none"  # resolved | ambiguous | none
    meal_items: list = field(default_factory=list)
    meal_portion: Optional[str] = None


_INTAKE_PROMPT = (
    "You are the intake collector assistant for a diabetes-logging system. You are NOT a doctor. "
    "You never give medical advice, targets, diagnoses, doses, or diet prescriptions, and you never "
    "comment on what a reading number means.\n"
    "Your only job: decide which logging fields the patient's latest message provided, and if "
    "anything is missing or ambiguous, ask for EXACTLY ONE in a short friendly Hinglish question "
    "(under 70 characters). Recognise Hindi/Hinglish and typos (e.g. 'mithai', 'khana', 'sugar 120', "
    "'fasting', 'khali pet', 'prick 140').\n"
    "Required fields: 1) reading number 2) reading context tag (fasting / post-breakfast / post-lunch / "
    "post-dinner / pre-meal) 3) meal items 4) portion size (small/medium/large).\n"
    "If everything required was supplied, return missing=[] and an empty reply — do NOT ask anything extra.\n"
    'Return strictly valid JSON: {"intent":"reading"|"meal"|"confirm"|"clarify", '
    '"missing":["reading_value"|"reading_tag"|"meal_items"|"portion"], "reply":"<one short Hinglish question or empty>", '
    '"items":["dish 1","dish 2"] (only the dish names the patient mentioned, or []), '
    '"portion":"s"|"m"|"l" (only when the patient stated it)}'
)


def _call_gemini_intake(text: str, patient_name: str, key: str) -> Optional[dict]:
    """Direct Gemini call for intake decisions. Never runs in the webhook path."""
    prompt = f"{_INTAKE_PROMPT}\nPatient: {patient_name}\nMessage: '{str(text)[:200]}'"
    last_err = None
    try:
        from .ai import discover_models
        model_list = discover_models(key) or list(_MODELS)
    except Exception:
        model_list = list(_MODELS)
    for model in model_list:
        try:
            import httpx
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
                   f":generateContent?key={key}")
            resp = httpx.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=6.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                m = re.search(r"\{.*\}", raw_text, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(0))
                    return {**parsed, "_model": model}
            else:
                last_err = f"intake {model}: HTTP {resp.status_code}"
        except Exception as e:  # noqa: BLE001
            last_err = f"intake {model}: {e}"
    try:
        from .ai import _last_ai_status
        _last_ai_status["last_status"] = "intake_error"
        _last_ai_status["last_error"] = last_err
    except Exception:
        pass
    return None


def _local_notifier(text: str, patient_name: str, cfg: Settings) -> IntakeResult:
    raw = re.sub(r"\s+", " ", (text or "")).strip()
    low = raw.lower()
    name = (patient_name or "ji").strip() or "ji"

    parsed = parse_inbound({"kind": "text", "text": raw,
                            "ts": datetime.now().isoformat()}, cfg)

    local_items = _meal_items(raw, cfg)
    meal_portion = (parsed.portion_letter
                    or (local_items[0].get("portion", "m") if local_items else None))

    # Reading: value present, tag explicitly stated -> complete, never nag.
    if parsed.is_reading and parsed.reading is not None:
        tag_stated = any(k in low for k in _TAG_KEYWORDS)
        if tag_stated:
            return IntakeResult(intent="reading", missing=[], reply="",
                                should_reply=False, raw_text=raw, confidence=0.9,
                                analyzed_by="local-refiner",
                                reading_value=parsed.reading,
                                reading_tag=parsed.reading_tag,
                                reading_status="resolved",
                                meal_items=local_items, meal_portion=meal_portion)
        return IntakeResult(
            intent="reading",
            missing=["reading_tag"],
            reply=(f"{name} ji, reading {parsed.reading:.0f} note ho gaya. "
                   "Ye fasting thi ya khane ke baad? (jaise 'fasting' ya 'post lunch')"),
            should_reply=True, raw_text=raw, confidence=0.8,
            analyzed_by="local-refiner",
            reading_value=parsed.reading,
            reading_tag=parsed.reading_tag,
            reading_status="resolved")

    # Reading hinted but the number is missing.
    reading_hint = any(k in low for k in _READING_HINTS)
    if reading_hint and parsed.reading is None and not parsed.items:
        return IntakeResult(
            intent="reading",
            missing=["reading_value"],
            reply=(f"{name} ji, reading number bataiye (jaise 'fasting 120' ya 'sugar 135')."),
            should_reply=True, raw_text=raw, confidence=0.75,
            analyzed_by="local-refiner",
            meal_items=local_items, meal_portion=meal_portion)

    # Unresolved reading ("230 or 330"): reflect it back, never guess a number.
    cand = ambiguous_reading_values(raw)
    if cand:
        q = " ya ".join(f"{v:.0f}" for v in cand)
        return IntakeResult(
            intent="reading",
            missing=["reading_value"],
            reply=f"{name} ji, exact reading kya thi — {q}? (jaise 'sugar {cand[0]:.0f}')",
            should_reply=True, raw_text=raw, confidence=0.6,
            analyzed_by="local-refiner",
            reading_candidates=cand, reading_status="ambiguous",
            meal_items=local_items, meal_portion=meal_portion)

    # Meal: portion unknown -> one follow-up; portion given -> done.
    if parsed.is_meal or (parsed.kind == "text" and parsed.items):
        has_portion = any(k in low for k in _PORTION_WORDS)
        if not has_portion:
            return IntakeResult(
                intent="meal",
                missing=["portion"],
                reply=(f"{name} ji, meal note ho gaya! Kya portion thi — "
                       "small, medium ya large?"),
                should_reply=True, raw_text=raw, confidence=0.85,
                analyzed_by="local-refiner",
                meal_items=local_items, meal_portion=meal_portion)
        return IntakeResult(intent="meal", missing=[], reply="",
                            should_reply=False, raw_text=raw, confidence=0.9,
                            analyzed_by="local-refiner",
                            meal_items=local_items, meal_portion=meal_portion)

    # Confirmations / corrections are fully handled by the deterministic path.
    if parsed.kind in ("confirm", "correct"):
        return IntakeResult(intent="confirm", missing=[], reply="",
                            should_reply=False, raw_text=raw, confidence=0.95,
                            analyzed_by="local-refiner")

    # Safety refusals (e.g. out-of-range values) stay untouched — no reframing.
    if parsed.kind == "refusal":
        return IntakeResult(intent="refusal", missing=[], reply="",
                            should_reply=False, raw_text=raw, confidence=0.9,
                            analyzed_by="local-refiner")

    # Anything else: ask a single friendly clarifying input-collection question.
    return IntakeResult(
        intent="clarify",
        missing=["reading_value", "meal_items"],
        reply=(f"{name} ji, thoda aur bataiye — kripya apni sugar reading "
               "bataiye (jaise 'sugar 130' ya 'fasting 120')."),
        should_reply=True, raw_text=raw, confidence=0.5,
        analyzed_by="local-refiner")


def analyze_intake(text: str, patient_name: str = "Patient",
                   cfg: Optional[Settings] = None) -> IntakeResult:
    """Analyze a STORED patient message and produce an intake-notifier reply.

    This is only ever called off the live webhook path (dashboard trigger or the
    background worker). It prefers Gemini when a key is present and falls back
    to a deterministic local notifier otherwise.
    """
    cfg = cfg or Settings()
    raw = str(text or "").strip()
    key = os.environ.get("GEMINI_API_KEY") or getattr(cfg, "gemini_api_key", "")
    if key:
        parsed = _call_gemini_intake(raw, patient_name, key)
        if parsed:
            intent = str(parsed.get("intent") or "clarify")
            missing = [str(x) for x in (parsed.get("missing") or [])
                       if str(x).strip() and str(x).strip().lower() != "none"]
            reply = str(parsed.get("reply") or "").strip()
            # Server-side safety rule decides whether a message actually goes out:
            # follow-ups only when a field is genuinely missing or input was unclear.
            should_reply = (intent == "clarify") or bool(missing)
            if should_reply and not reply:
                fallback = _local_notifier(raw, patient_name, cfg)
                reply = fallback.reply
            try:
                from .ai import _last_ai_status
                _last_ai_status["last_status"] = "intake_success"
                _last_ai_status["last_call_ts"] = datetime.now().isoformat()
                _last_ai_status["last_model"] = str(parsed.get("_model", ""))
            except Exception:
                pass
            ded = _reading_deduction(raw)
            # Map Gemini dish names onto the nutrition classifier (carbs/GI rows),
            # so recognized food can be registered into the meal log off-webhook.
            g_items = []
            raw_items = parsed.get("items") or []
            if isinstance(raw_items, str) and raw_items.strip():
                g_items = _meal_items(raw_items, cfg)
            elif isinstance(raw_items, list):
                names = [str(x).strip() for x in raw_items if str(x).strip()]
                if names:
                    g_items = _meal_items(", ".join(names[:4]), cfg)
            g_portion = str(parsed.get("portion") or "").strip().lower()[:1]
            if g_portion not in ("s", "m", "l"):
                g_portion = (g_items[0].get("portion", "m") if g_items else None)
            return IntakeResult(intent=intent, missing=missing, reply=reply,
                                should_reply=should_reply, raw_text=raw,
                                confidence=0.98,
                                analyzed_by=f"gemini:{parsed.get('_model', '')}",
                                reading_value=ded.get("value"),
                                reading_candidates=ded.get("candidates") or [],
                                reading_status=ded.get("status", "none"),
                                meal_items=g_items, meal_portion=g_portion)
    return _local_notifier(raw, patient_name, cfg)