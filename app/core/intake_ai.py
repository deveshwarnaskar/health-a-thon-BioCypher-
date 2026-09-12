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
from .parse import parse_inbound

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

_MODELS = ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash")


@dataclass
class IntakeResult:
    intent: str
    missing: list
    reply: str
    should_reply: bool
    raw_text: str
    confidence: float
    analyzed_by: str = "local-refiner"


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
    '"missing":["reading_value"|"reading_tag"|"meal_items"|"portion"], "reply":"<one short Hinglish question or empty>"}'
)


def _call_gemini_intake(text: str, patient_name: str, key: str) -> Optional[dict]:
    """Direct Gemini call for intake decisions. Never runs in the webhook path."""
    prompt = f"{_INTAKE_PROMPT}\nPatient: {patient_name}\nMessage: '{str(text)[:200]}'"
    last_err = None
    for model in _MODELS:
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

    # Reading: value present, tag explicitly stated -> complete, never nag.
    if parsed.is_reading and parsed.reading is not None:
        tag_stated = any(k in low for k in _TAG_KEYWORDS)
        if tag_stated:
            return IntakeResult(intent="reading", missing=[], reply="",
                                should_reply=False, raw_text=raw, confidence=0.9,
                                analyzed_by="local-refiner")
        return IntakeResult(
            intent="reading",
            missing=["reading_tag"],
            reply=(f"{name} ji, reading {parsed.reading:.0f} note ho gaya. "
                   "Ye fasting thi ya khane ke baad? (jaise 'fasting' ya 'post lunch')"),
            should_reply=True, raw_text=raw, confidence=0.8,
            analyzed_by="local-refiner")

    # Reading hinted but the number is missing.
    reading_hint = any(k in low for k in _READING_HINTS)
    if reading_hint and parsed.reading is None and not parsed.items:
        return IntakeResult(
            intent="reading",
            missing=["reading_value"],
            reply=(f"{name} ji, reading number bataiye (jaise 'fasting 120' ya 'sugar 135')."),
            should_reply=True, raw_text=raw, confidence=0.75,
            analyzed_by="local-refiner")

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
                analyzed_by="local-refiner")
        return IntakeResult(intent="meal", missing=[], reply="",
                            should_reply=False, raw_text=raw, confidence=0.9,
                            analyzed_by="local-refiner")

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
        reply=(f"{name} ji, thoda aur bataiye — sugar reading bhejna hai "
               "(jaise 'sugar 130') ya khana (jaise '2 roti dal')?"),
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
            return IntakeResult(intent=intent, missing=missing, reply=reply,
                                should_reply=should_reply, raw_text=raw,
                                confidence=0.98,
                                analyzed_by=f"gemini:{parsed.get('_model', '')}")
    return _local_notifier(raw, patient_name, cfg)