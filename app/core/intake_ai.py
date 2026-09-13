"""AI intake notifier — a decoupled, on-demand consumer of STORED raw inbound rows.

This module is intentionally separate from the WhatsApp webhook path:

  * the webhook captures raw patient input and returns HTTP 200 (unchanged);
  * this module reads those STORED rows from the database later — via the
    dashboard ("Run AI Intake Analysis", POST /api/v1/analyze/stored), the
    live-feed auto-analysis, or the optional background worker
    (AAHAAR_AI_INTAKE=on);
  * follow-up replies and confirmations go out through the exact same outbound
    channel the doctor composer uses (backend.send), never from inside the
    webhook handler.

Gemini is used purely as an INPUT-COLLECTION assistant, not a doctor: it asks
for missing logging fields in short Hinglish and never gives medical advice,
targets, diagnoses, or prescriptions. All LOGGING decisions (which value is
real, reading-context tag, backdated timestamps, "already logged" duplicates)
are deterministic and decided here so the patient always gets ONE coherent
message per input. If Gemini is unavailable, a deterministic local notifier
takes over so the flow never breaks and the webhook behaviour never changes.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from ..config import Settings
from .clock import fmt_ts_log, iso_now
from .parse import (
    PATIENT_TAG_LABELS,
    _PORTION_MAP,
    _correction_value,
    _is_dup_answer,
    _is_tag_answer,
    _is_tag_negation,
    _resolution_cue_value,
    _tag_from_text,
    ambiguous_reading_values,
    parse_inbound,
    reading_timestamp,
)


def _meal_items(text: str, cfg: Settings) -> list:
    """Deterministically extract dish items (with carbs/GI) from stored text.

    Falls back to the nutrition classifier's "mixed meal" row for novel foods,
    so patient-described meals are never lost even when the dish is not in the
    catalog (e.g. 'whole steak with red wine').
    """
    from .parse import _items
    return list(_items(text, cfg))


# Words that mark the reading-context tag as explicitly stated by the patient.
# "morning"/"subah" are timing words, NOT fasting — they never tag a reading.
_TAG_KEYWORDS = (
    "fasting", "fast", "fbs", "khali", "roza",
    "breakfast", "nashta", "pb", "lunch", "dopahar", "pl",
    "dinner", "raat", "pd", "pre", "before", "pehle", "post", "after", "baad",
    "random",
)

# Words that imply a glucose reading is being reported (even without a number).
_READING_HINTS = ("sugar", "glucose", "fasting", "fast", "khali", "prick",
                  "glucometer", "reading", "level", "bg", "fbs", "rbs", "ppbg",
                  "random")

# Portion words that make the meal input complete.
_PORTION_WORDS = ("small", "medium", "large", "chota", "chhota", "chhoti",
                  "kam", "badi", "bara", "bada", "do roti", "2 roti",
                  "katori", "katora", "bowl", "bowls", "plate", "plates",
                  "glass", "cup", "ml", "full", "half")


def _portion_stated(low: str, parsed_letter: Optional[str]) -> bool:
    """True when the patient actually named a size (word, portion letter or
    verbatim text like "do katori" / "200ml"). Never invented otherwise."""
    return (any(k in low for k in _PORTION_WORDS)
            or bool(parsed_letter)
            or bool(portion_text(low)))

_PORTION_LABEL = {"s": "small", "m": "medium", "l": "large"}

_MODELS = ("gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite")


def _hm(ts_s: Optional[str]) -> str:
    """'23:06' from a stored ISO timestamp."""
    if not ts_s:
        return ""
    s = str(ts_s)
    return s[11:16] if len(s) >= 16 else s


# Patient-stated meal/portion sizes that we store verbatim ("200ml").
_SIZE_UNITS = ("ml", "g", "gm", "gr", "kg", "l", "litre", "litres", "liter")
_SIZE_BOWLS = ("bowl", "katori", "plate", "thali", "glass", "cup", "dona",
               "katori bhara", "pao")
_SIZE_COUNT = ("do", "teen", "char", "paanch", "ek", "two", "three", "four",
               "five", "one")


def portion_text(text: str) -> Optional[str]:
    """Extract the patient-stated size verbatim, e.g. '200ml', '2 bowls',
    'do katori'. Returns None when no explicit size was mentioned."""
    low = str(text or "").lower()
    m = re.search(r"(\d+(?:\.\d+)?\s*(?:ml|g|l|kg|glass|bowl|katori|plate|cup))", low)
    if m:
        return m.group(1).strip()
    m = re.search(r"(\d+\s*(?:ml|g|kg)?\s*(?:bowl|katori|plate|thali|glass|cup"
                  r"|dona)s?\b)", low)
    if m:
        return m.group(1).strip()
    m = re.search(r"((?:do|teen|char|paanch|ek|two|three|four|five)\s+"
                  r"(?:bowl|katori|plate|thali|glass|cup|dona)s?\b)", low)
    if m:
        return m.group(1).strip()
    return None


def _portion_answer(text: str) -> Optional[tuple]:
    """A portion answer: 'small', 'large bowl', or '<portion> <dish>' like
    'small choco'. Returns (portion_letter, remaining_text) or None. This lets
    '<small|medium|large|chota...> ...' replies finalize the pending meal
    instead of bouncing to a confused clarify."""
    low = str(text or "").strip().lower()
    low = re.sub(r"\b\d{1,2}:\d{2}\s*(?:am|pm)?\b", " ", low)
    low = re.sub(r"\b\d{1,2}\s*(?:am|pm|baje|o[ ']?clock)\b", " ", low)
    low = re.sub(r"\s+", " ", low).strip()
    if not low or " " not in low:
        return None
    first, rest = low.split(None, 1)
    letter = _PORTION_MAP.get(first)
    if not letter or len(rest) > 24 or re.search(r"\d", rest):
        return None
    return letter, rest


def _reading_deduction(text: str, msg_ts: Optional[str] = None) -> dict:
    """Deterministic deduction of a glucose READING from a stored message.

    Returns {"value": float|None, "tag": str|None, "candidates": [..],
             "status": "resolved"|"ambiguous"|"none", "ts_str": str|None}.
    - Ambiguous messages (>=2 distinct plausible values like "230 or 330") never
      pick a value — they wait for the patient to say which one is real.
    - Repeating the same number ("its reading was 311 ... 311") collapses to a
      single value and logs it once.
    - A single in-range number is a resolved reading (patients reply bare
      numbers like "200"); its tag and timestamp are honoured when the message
      explicitly states them ("yesterday evening near 3pm the post eating sugar
      was 300" -> yesterday 15:00, postprandial). "morning"/"subah" are timing,
      never fasting.
    """
    low = str(text or "")
    cand = ambiguous_reading_values(low)
    if cand:
        return {"value": None, "tag": None, "candidates": cand,
                "status": "ambiguous", "ts_str": None}
    nums = [float(m) for m in re.findall(r"\b\d{2,3}(?:\.\d)?\b", low.lower())
            if 20 <= float(m) <= 600]
    if not nums:
        return {"value": None, "tag": None, "candidates": [],
                "status": "none", "ts_str": None}
    counts = Counter(nums)
    single = None
    for value, count in counts.most_common():
        if count > 1 and 40 <= value <= 600:
            single = value
            break
    if single is None:
        high = [n for n in nums if n >= 60]
        keep = high if high else nums
        if len(set(keep)) > 1:
            return {"value": None, "tag": None,
                    "candidates": sorted(set(keep)),
                    "status": "ambiguous", "ts_str": None}
        single = keep[0]
    tag = None
    if any(k in low.lower() for k in _TAG_KEYWORDS):
        tag = _tag_from_text(low)
    ts_dt = reading_timestamp(low, msg_ts or iso_now())
    return {"value": single, "tag": tag, "candidates": [],
            "status": "resolved",
            "ts_str": ts_dt.strftime("%Y-%m-%dT%H:%M:%S")}


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
    reading_ts: Optional[str] = None
    meal_items: list = field(default_factory=list)
    meal_portion: Optional[str] = None
    meal_ts: Optional[str] = None


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


def _local_notifier(text: str, patient_name: str, cfg: Settings,
                    msg_ts: Optional[str] = None) -> IntakeResult:
    raw = re.sub(r"\s+", " ", (text or "")).strip()
    low = raw.lower()
    name = (patient_name or "ji").strip() or "ji"

    # The webhook normalizes typos before parsing; the AI path must too, so a
    # message like 'sugr 14o' still registers as a 140 reading. Answer words
    # stay on the RAW text (short exact phrases should not be rewritten).
    from .ai import refine_text_local
    ref_text = refine_text_local(raw)

    parsed = parse_inbound({"kind": "text", "text": raw,
                            "ts": msg_ts or iso_now()}, cfg)

    local_items = _meal_items(ref_text, cfg)
    meal_portion = parsed.portion_letter or None
    ded = _reading_deduction(ref_text, msg_ts)

    # ---- follow-up ANSWERS first (never misread as food/sugar) -----------
    # A negation ("wo fasting nhi thi") is its own intent — NEVER a tag.
    neg_tag = _is_tag_negation(raw)
    if neg_tag:
        return IntakeResult(intent="tag_negation", missing=["reading_tag"],
                            reply="", should_reply=True, raw_text=raw,
                            confidence=0.92, analyzed_by="local-refiner",
                            reading_tag=neg_tag,
                            meal_items=local_items, meal_portion=meal_portion)

    res_ans = _resolution_cue_value(raw)
    if res_ans is not None:
        return IntakeResult(intent="resolution", missing=[], reply="",
                            should_reply=True, raw_text=raw, confidence=0.9,
                            analyzed_by="local-refiner",
                            reading_value=res_ans, reading_status="resolved",
                            reading_ts=ded.get("ts_str"),
                            meal_items=local_items, meal_portion=meal_portion)

    # A correction ("130 not 120", "change 120 to 130") edits the last reading.
    corr = _correction_value(raw)
    if corr is not None:
        return IntakeResult(intent="correction", missing=[], reply="",
                            should_reply=True, raw_text=raw, confidence=0.9,
                            analyzed_by="local-refiner",
                            reading_value=corr, reading_status="resolved",
                            reading_tag=ded.get("tag"), reading_ts=ded.get("ts_str"),
                            meal_items=local_items, meal_portion=meal_portion)

    tag_ans = _is_tag_answer(raw)
    if tag_ans:
        return IntakeResult(intent="tag_answer", missing=[], reply="",
                            should_reply=True, raw_text=raw, confidence=0.97,
                            analyzed_by="local-refiner")

    dup_ans = _is_dup_answer(raw)
    if dup_ans:
        return IntakeResult(intent="dup_answer", missing=[], reply="",
                            should_reply=True, raw_text=raw, confidence=0.97,
                            analyzed_by="local-refiner",
                            meal_items=local_items, meal_portion=meal_portion)

    # ---- reading: ambiguous -> ask the true value, never guess -----------
    if ded["status"] == "ambiguous":
        cand = ded["candidates"]
        q = " ya ".join(f"{v:.0f}" for v in cand)
        return IntakeResult(
            intent="reading",
            missing=["reading_value"],
            reply=f"{name} ji, exact reading kya thi — {q}? (jaise 'sugar {cand[0]:.0f}')",
            should_reply=True, raw_text=raw, confidence=0.6,
            analyzed_by="local-refiner",
            reading_candidates=cand, reading_status="ambiguous",
            reading_ts=ded.get("ts_str"),
            meal_items=local_items, meal_portion=meal_portion)

    # ---- reading: one clear value -> confirm it (single message) ---------
    # Default type is "after eating" (post-prandial) — the patient logs fasting
    # only when they say so; "morning"/"subah" are never fasting.
    if ded["status"] == "resolved":
        v = float(ded["value"])
        tag = ded.get("tag") or "postprandial"
        hm = _hm(ded.get("ts_str"))
        label = PATIENT_TAG_LABELS.get(tag, tag)
        reply = (f"✅ Logged sugar {v:g} ({label}) — {hm}. "
                 "Aur kuch log karna hai — sugar ya khana?")
        # A reading whose message ALSO named food asks for the meal size in the
        # same single reply (the meal stays pending until the size is answered).
        if local_items and not _portion_stated(low, parsed.portion_letter):
            names = list(dict.fromkeys(
                str(it.get("item") or "") for it in local_items if it.get("item")))
            dishes = ", ".join(names) or "khana"
            reply = (f"✅ Logged sugar {v:g} ({label}) — {hm}. "
                     f"Khana ({dishes}) ka size kya tha — "
                     "small, medium ya large?")
        return IntakeResult(
            intent="reading",
            missing=[],
            reply=reply,
            should_reply=True, raw_text=raw, confidence=0.9,
            analyzed_by="local-refiner",
            reading_value=v, reading_tag=tag, reading_status="resolved",
            reading_ts=ded.get("ts_str"),
            meal_items=local_items, meal_portion=meal_portion)

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

    # ---- portion answer: '<small|medium|large...> <dish>' or a bare 'small'
    # finalizes the pending meal with the stated size (never a confused clarify)
    p_ans = _portion_answer(raw)
    if p_ans:
        letter, rest = p_ans
        extra = _meal_items(rest, cfg) if rest else []
        return IntakeResult(
            intent="meal_confirm", missing=[], reply="",
            should_reply=True, raw_text=raw, confidence=0.95,
            analyzed_by="local-refiner",
            meal_portion=letter, meal_items=extra,
            meal_ts=reading_timestamp(raw, msg_ts or iso_now()).strftime(
                "%Y-%m-%dT%H:%M:%S"))
    if parsed.kind == "confirm" and parsed.portion_letter:
        return IntakeResult(
            intent="meal_confirm", missing=[], reply="",
            should_reply=True, raw_text=raw, confidence=0.95,
            analyzed_by="local-refiner",
            meal_portion=parsed.portion_letter,
            meal_ts=reading_timestamp(raw, msg_ts or iso_now()).strftime(
                "%Y-%m-%dT%H:%M:%S"))

    # ---- meal: log + one confirm (portion question merged into the same text)
    if parsed.kind in ("photo", "voice", "correct") or parsed.items or local_items:
        names_set, names = [], []
        for it in local_items:
            nm = str(it.get("item") or "")
            if nm and nm not in names_set:
                names_set.append(nm)
                names.append(nm)
        dishes = ", ".join(names) or "khana"
        has_portion = _portion_stated(low, parsed.portion_letter)
        portion_label = _PORTION_LABEL.get(meal_portion or "m", "medium")
        # Meals honour the same explicit day/time the text refers to
        # ("yesterday i ate...", "14 july lunch") so backdated meals land on the
        # right date instead of the message's own receive date.
        meal_ts = reading_timestamp(raw, msg_ts or iso_now()).strftime(
            "%Y-%m-%dT%H:%M:%S")
        if not has_portion:
            reply = (f"✅ Logged khana: {dishes}. "
                     "Kya portion thi — small, medium ya large?")
            missing = ["portion"]
        else:
            reply = f"✅ Logged khana: {dishes} ({portion_label})."
            missing = []
        return IntakeResult(
            intent="meal", missing=missing, reply=reply,
            should_reply=True, raw_text=raw, confidence=0.88,
            analyzed_by="local-refiner",
            meal_items=local_items, meal_portion=meal_portion, meal_ts=meal_ts)

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
                   cfg: Optional[Settings] = None,
                   msg_ts: Optional[str] = None) -> IntakeResult:
    """Analyze a STORED patient message and produce an intake-notifier result.

    This is only ever called off the live webhook path (dashboard trigger or the
    background worker). ALL logging decisions are deterministic; Gemini (when a
    key is present) only helps the genuinely-unclear case word a better question.
    """
    cfg = cfg or Settings()
    raw = str(text or "").strip()
    local = _local_notifier(raw, patient_name, cfg, msg_ts)
    key = os.environ.get("GEMINI_API_KEY") or getattr(cfg, "gemini_api_key", "")
    if not key:
        return local
    parsed = _call_gemini_intake(raw, patient_name, key)
    if not parsed:
        return local
    try:
        from .ai import _last_ai_status
        _last_ai_status["last_status"] = "intake_success"
        _last_ai_status["last_call_ts"] = iso_now()
        _last_ai_status["last_model"] = str(parsed.get("_model", ""))
    except Exception:
        pass
    gem_reply = str(parsed.get("reply") or "").strip()
    if local.intent == "clarify" and gem_reply:
        local.reply = gem_reply
        local.analyzed_by = f"gemini:{parsed.get('_model', '')}"
        local.confidence = 0.98
    if not local.meal_items:
        raw_items = parsed.get("items") or []
        g_items = []
        if isinstance(raw_items, str) and raw_items.strip():
            g_items = _meal_items(raw_items, cfg)
        elif isinstance(raw_items, list):
            names = [str(x).strip() for x in raw_items if str(x).strip()]
            if names:
                g_items = _meal_items(", ".join(names[:4]), cfg)
        if g_items:
            local.meal_items = g_items
            g_portion = str(parsed.get("portion") or "").strip().lower()[:1]
            if g_portion in ("s", "m", "l"):
                local.meal_portion = g_portion
    return local