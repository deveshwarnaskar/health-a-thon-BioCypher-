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
    _dated_edit_value,
    _is_done,
    _is_dup_answer,
    _is_meal_delete,
    _is_reading_delete,
    _is_size_answer,
    _is_tag_answer,
    _is_tag_negation,
    _reference_correction,
    _resolution_cue_value,
    _tag_from_text,
    ambiguous_reading_values,
    parse_inbound,
    portion_text,
    reading_timestamp,
    strip_reading_noise,
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


# Patient-stated meal/portion sizes come from parse.portion_text (kept in
# parse.py so the webhook path shares the same size parsing).


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
    - Time/size clutter is stripped FIRST so clock minutes ("8 30 am"),
      portion counts ("100 ml", "do katori") can never be read as glucose.
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
    low = strip_reading_noise(text)
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
    ts_dt = reading_timestamp(text, msg_ts or iso_now())
    return {"value": single, "tag": tag, "candidates": [],
            "status": "resolved",
            "ts_str": ts_dt.strftime("%Y-%m-%dT%H:%M:%S")}


_MULTI_SEP = re.compile(
    r"[,;]|\b(?:and|aur|phir|fir|then|ke\s+baad|ke\s+bad)\b", re.I)


def _multi_readings(text: str, msg_ts: Optional[str] = None) -> list[dict]:
    """Split a message that reports SEVERAL readings ("8am 130, 9am 145",
    "subah 130 aur shaam 150"). Each segment must resolve to exactly one
    glucose-sized number that is not itself ambiguous. Returns [] unless at
    least two such readings exist with distinct values OR timestamps — so a
    genuine "230 or 330" stays a candidate question, never a double-log."""
    out = []
    for raw_seg in re.split(_MULTI_SEP, str(text or "")):
        raw_seg = raw_seg.strip()
        if not raw_seg:
            continue
        seg = strip_reading_noise(raw_seg)
        if ambiguous_reading_values(seg):
            continue
        nums = [float(m) for m in re.findall(r"\b\d{2,3}(?:\.\d)?\b", seg)
                if 20 <= float(m) <= 600]
        if len(nums) != 1:
            continue
        v = nums[0]
        tag = _tag_from_text(seg) if any(
            k in seg.lower() for k in _TAG_KEYWORDS) else None
        # The raw segment keeps its time words ("8am 130" -> 08:00) even though
        # the number scan strips them.
        ts_dt = reading_timestamp(raw_seg, msg_ts or iso_now())
        out.append({"value": v, "tag": tag,
                    "ts_str": ts_dt.strftime("%Y-%m-%dT%H:%M:%S")})
    pairs = {(r["ts_str"], r["value"]) for r in out}
    if len(out) >= 2 and len(pairs) >= 2:
        return out
    return []


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
    meal_portion_text: Optional[str] = None
    meal_ts: Optional[str] = None
    multi_readings: list = field(default_factory=list)
    language: str = "hi"


_INTAKE_PROMPT = (
    "You are the intake collector assistant for a diabetes-logging system. You are NOT a doctor. "
    "You never give medical advice, targets, diagnoses, doses, or diet prescriptions, and you never "
    "comment on what a reading number means.\n"
    "Understand the patient's message in ANY language it is written in (Hindi, Hinglish, Tamil, Urdu, "
    "Bengali, Telugu, Punjabi, Gujarati, Kannada, Malayalam, Odia, English...). Also catch typos "
    "('mithai', 'khana', 'sugar 120', 'fasting', 'khali pet', 'prick 140').\n"
    "Your only job: decide which logging fields the patient's latest message provided, and if "
    "anything is missing or ambiguous, ask for EXACTLY ONE in a short friendly question written in the "
    "patient's OWN language (under 70 characters).\n"
    "Required fields: 1) reading number 2) reading context tag (fasting / post-breakfast / post-lunch / "
    "post-dinner / pre-meal) 3) meal items 4) portion size (small/medium/large).\n"
    "Rules:\n"
    "- Only report a reading number that the patient ACTUALLY wrote. Never invent one.\n"
    "- When the message changes/corrects a meal said earlier ('not the one i told', 'the meal i told was "
    "wrong') but names no new dish and no number, set is_reference=true and items=[].\n"
    "- When the message asks to delete a reading or a meal, set is_delete=true and reply=''.\n"
    "- If everything required was supplied, return missing=[] and an empty reply — do NOT ask anything extra.\n"
    'Return strictly valid JSON: {"intent":"reading"|"meal"|"confirm"|"clarify"|"reference"|"delete", '
    '"missing":["reading_value"|"reading_tag"|"meal_items"|"portion"], "reply":"<one short question in the '
    'patient language or empty>", "reading": <number the patient wrote or null>, '
    '"reading_tag":"fasting"|"postprandial"|"postbreakfast"|"postlunch"|"postdinner"|"pre"|"random"|null, '
    '"items":["dish 1","dish 2"] (only what the patient mentioned, or []), '
    '"portion":"s"|"m"|"l" (only when the patient stated it), '
    '"readings":[{"value": <number>, "tag": <tag or null>}, ...] (ONLY when the message reports several '
    'readings, e.g. "8am 130, 9am 145"; else []), '
    '"is_reference": true|false, "is_delete": true|false, '
    '"detected_language":"hi"|"ta"|"bn"|"te"|"pa"|"gu"|"kn"|"ml"|"or"|"ur"|"en"}'
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


# ---- multilingual understanding --------------------------------------
# Patient messages are understood in ANY language; replies are mirrored back in
# the patient's language (deterministic script detection always, translation
# through Gemini only when a key is present — never inventing clinical words).
_LANG_NAMES = {
    "hi": "Hindi", "ta": "Tamil", "bn": "Bengali", "te": "Telugu",
    "pa": "Punjabi", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
    "or": "Odia", "ur": "Urdu", "en": "English",
}
_SCRIPT_RANGES = {
    "hi": ((0x0900, 0x097F),),
    "bn": ((0x0980, 0x09FF),),
    "ta": ((0x0B80, 0x0BFF),),
    "te": ((0x0C00, 0x0C7F),),
    "kn": ((0x0C80, 0x0CFF),),
    "ml": ((0x0D00, 0x0D7F),),
    "gu": ((0x0A80, 0x0AFF),),
    "pa": ((0x0A00, 0x0A7F),),
    "or": ((0x0B00, 0x0B7F),),
    "ur": ((0x0600, 0x06FF),),
}
_HINDI_LOAN_TOKENS = {"ji", "bataiye", "batao", "khana", "khaana", "theek",
                      "thik", "sahi", "nahi", "nhi", "hai", "log", "karo",
                      "karke", "bana", "pet", "roti", "dal", "sabzi", "subah",
                      "shaam", "raat", "ki", "ke", "ka", "bahut", "badiya",
                      "achha", "achchha", "kya", "kal", "aaj", "tha", "thi",
                      "khaya", "khayi", "chole", "bhature",
                      "biryani", "chawal", "paneer", "kadi", "phir", "aur",
                      "maine", "tumne", "wo", "ye", "koi", "naya", "baad"}


def detect_language(text: Optional[str]) -> str:
    """Patient's reply language by script. Latin script that carries Hindi
    loanwords is 'hi' (the default Hinglish UI), otherwise 'en'."""
    low = str(text or "")
    counts: dict[str, int] = {}
    for ch in low:
        cp = ord(ch)
        for lang, ranges in _SCRIPT_RANGES.items():
            for lo, hi in ranges:
                if lo <= cp <= hi:
                    counts[lang] = counts.get(lang, 0) + 1
                    break
    if not counts:
        lat = re.sub(r"[^a-z\s]", " ", low.lower())
        if set(lat.split()) & _HINDI_LOAN_TOKENS:
            return "hi"
        return "en"
    return max(counts, key=counts.get)


def _call_gemini_plain(prompt: str, key: str) -> Optional[str]:
    """Bare Gemini completion returning the raw text (for translations).
    Returns None on any failure so callers keep their safe default."""
    model_list = list(_MODELS)
    try:
        from .ai import discover_models
        model_list = discover_models(key) or list(_MODELS)
    except Exception:
        pass
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
                out = data["candidates"][0]["content"]["parts"][0]["text"]
                return (out or "").strip() or None
        except Exception:  # noqa: BLE001
            continue
    return None


def localize_reply(reply: Optional[str], lang: Optional[str]) -> Optional[str]:
    """Mirror a bot reply into the patient's language. Hinglish (hi/en/) is the
    native reply language and is never touched; regional scripts are translated
    only when Gemini is available, and the result is bounded + screened so we
    never relay invented clinical wording."""
    if not reply:
        return reply
    lng = (lang or "hi").strip()
    if lng in ("", "hi", "en", "sa") or lng not in _LANG_NAMES:
        return reply
    key = os.environ.get("GEMINI_API_KEY") or ""
    if not key:
        return reply
    prompt = (
        f"You are a translation helper. Translate the following short healthcare "
        f"log-message into {_LANG_NAMES[lng]}. Reply with ONLY the translation, "
        f"keeping numbers, times and emoji exactly as they are. Do not add advice "
        f"or instructions.\nMessage:\n{reply[:300]}"
    )
    out = _call_gemini_plain(prompt, key)
    if not out:
        return reply
    cleaned = " ".join(str(out).split())
    if len(cleaned) > 400:
        return reply
    forbidden = ("target", "dose", "insulin", "prescrib", "diagnos", "medicine",
                 "medication", "consult", "suggest")
    if any(w in cleaned.lower() for w in forbidden):
        return reply
    return cleaned


_EXPLICIT_TIME_RE = re.compile(
    r"\b(?:yesterday|kal|aaj|today|subah|shaam|raat|dopahar|morning|afternoon|"
    r"evening|night|am|pm|baje|o'?clock|abhi|just now|rn|now)\b|"
    r"\d{1,2}:\d{2}")


def _has_explicit_time(text: str) -> bool:
    """True when the message names a day-part, clock time, or temporal word —
    so an independent log is NOT stamped blindly at the received time."""
    return bool(_EXPLICIT_TIME_RE.search(str(text or "").lower()))


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

    # An explicit day/time correction ("kal 8 am wala galat tha, 140 tha")
    # edits THAT past reading — checked before resolution/correction so the
    # "wala" cue can never hijack a dated edit into a bare value answer.
    dated_edit = _dated_edit_value(raw, msg_ts)
    if dated_edit is not None:
        value, ts_str = dated_edit
        return IntakeResult(intent="correction", missing=[], reply="",
                            should_reply=True, raw_text=raw, confidence=0.94,
                            analyzed_by="local-refiner",
                            reading_value=value, reading_status="resolved",
                            reading_tag=ded.get("tag"), reading_ts=ts_str,
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

    # ---- edit/delete existing log entries --------------------------------
    if _is_meal_delete(raw):
        return IntakeResult(intent="meal_delete", missing=[], reply="",
                            should_reply=True, raw_text=raw, confidence=0.97,
                            analyzed_by="local-refiner",
                            meal_items=local_items, meal_portion=meal_portion,
                            meal_ts=reading_timestamp(raw, msg_ts or iso_now())
                            .strftime("%Y-%m-%dT%H:%M:%S"))
    if _is_reading_delete(raw):
        return IntakeResult(intent="reading_delete", missing=[], reply="",
                            should_reply=True, raw_text=raw, confidence=0.97,
                            analyzed_by="local-refiner",
                            reading_ts=ded.get("ts_str"),
                            meal_items=local_items, meal_portion=meal_portion)

    # A meal REFERENCE/correction ("not the one i told", "the meal i told was
    # wrong") with no new dish and no number — must never fabricate a dish.
    if not local_items and _reference_correction(raw):
        return IntakeResult(intent="meal_reference", missing=[], reply="",
                            should_reply=True, raw_text=raw, confidence=0.93,
                            analyzed_by="local-refiner",
                            meal_items=local_items, meal_portion=meal_portion,
                            meal_ts=reading_timestamp(raw, msg_ts or iso_now())
                            .strftime("%Y-%m-%dT%H:%M:%S"))

    # A bare portion-size answer ("100ml", "2 bowls", "was 200ml") finalizes
    # the pending meal with the verbatim size — never a confused clarify.
    sz = _is_size_answer(raw)
    if sz:
        letter = (_PORTION_MAP.get(str(sz).lower().split()[0])
                  if str(sz).split() else None)
        return IntakeResult(intent="meal_confirm", missing=[], reply="",
                            should_reply=True, raw_text=raw, confidence=0.95,
                            analyzed_by="local-refiner",
                            meal_portion=letter, meal_portion_text=sz,
                            meal_ts=reading_timestamp(raw, msg_ts or iso_now())
                            .strftime("%Y-%m-%dT%H:%M:%S"))

    # Several readings reported together ("8am 130, 9am 145") land separately.
    # True ambiguity ("230 or 330") produces no split readings and still falls
    # through to the single-question path below.
    multi = _multi_readings(raw, msg_ts)
    if multi:
        return IntakeResult(intent="multi_reading", missing=[], reply="",
                            should_reply=True, raw_text=raw, confidence=0.88,
                            analyzed_by="local-refiner",
                            multi_readings=multi,
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
    # Default type is Random Blood Glucose (RBG). Fasting is only ever logged
    # when the patient says "fasting"; "postprandial" only when they say
    # after/baad/post-2hr; "morning"/"subah" are never fasting.
    if ded["status"] == "resolved":
        v = float(ded["value"])
        tag = ded.get("tag") or "random"
        hm = _hm(ded.get("ts_str"))
        label = PATIENT_TAG_LABELS.get(tag, tag)
        # An independent log with no stated time (meal or reading) gets ONE
        # courteous timing line — the log lands at the received time.
        if not local_items and not _has_explicit_time(raw):
            time_note = (" Samay sahi hai? Alag tha to bataiye "
                         "(jaise 'kal subah 8').")
        else:
            time_note = ""
        reply = (f"✅ Logged sugar {v:g} ({label}) — {hm}.{time_note} "
                 "Aur kuch log karna hai — sugar ya khana?")
        # A reading whose message ALSO named food asks for the meal size in the
        # same single reply (the meal stays pending until the size is answered).
        # When the size IS already stated (letter or verbatim count like "3
        # strawberries") the meal is registered right away in the same message.
        pt = portion_text(low)
        if local_items and not _portion_stated(low, parsed.portion_letter):
            names = list(dict.fromkeys(
                str(it.get("item") or "") for it in local_items if it.get("item")))
            dishes = ", ".join(names) or "khana"
            reply = (f"✅ Logged sugar {v:g} ({label}) — {hm}. "
                     f"Khana ({dishes}) ka size kya tha — "
                     "small, medium ya large?")
        elif local_items:
            names = list(dict.fromkeys(
                str(it.get("item") or "") for it in local_items if it.get("item")))
            dishes = ", ".join(names) or "khana"
            pl = (_PORTION_LABEL.get(meal_portion or
                  local_items[0].get("portion") or "m", "medium")
                  if not pt else "")
            disp = f" ({pt.strip()}) " if pt else f" ({pl}) "
            reply = (f"✅ Logged sugar {v:g} ({label}) — {hm}. "
                     f"Khana ({dishes}){disp}ke saath bhi log ho gaya."
                     " Aur kuch log karna hai — sugar ya khana?")
        return IntakeResult(
            intent="reading",
            missing=[],
            reply=reply,
            should_reply=True, raw_text=raw, confidence=0.9,
            analyzed_by="local-refiner",
            reading_value=v, reading_tag=tag, reading_status="resolved",
            reading_ts=ded.get("ts_str"),
            meal_items=local_items, meal_portion=meal_portion,
            meal_portion_text=pt)

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
            meal_portion_text=portion_text(low),
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
        # A verbatim count IS the stated size ("3 strawberries").
        pt = portion_text(low)
        disp = pt if pt else portion_label
        # Meals honour the same explicit day/time the text refers to
        # ("yesterday i ate...", "14 july lunch") so backdated meals land on the
        # right date instead of the message's own receive date.
        meal_ts = reading_timestamp(raw, msg_ts or iso_now()).strftime(
            "%Y-%m-%dT%H:%M:%S")
        # Independent logs get ONE timing line and a friendly pairing courtesy.
        time_note = (" Samay sahi hai? Alag tha to bataiye "
                     "(jaise 'kal subah 8')." if not _has_explicit_time(raw)
                     else "")
        if not has_portion:
            reply = (f"✅ Logged khana: {dishes}. "
                     f"Kya portion thi — small, medium ya large?{time_note}")
            missing = ["portion"]
        else:
            assoc = " Is ke saath sugar reading bhi log karein?"
            reply = (f"✅ Logged khana: {dishes} ({disp}).{assoc}{time_note}")
            missing = []
        return IntakeResult(
            intent="meal", missing=missing, reply=reply,
            should_reply=True, raw_text=raw, confidence=0.88,
            analyzed_by="local-refiner",
            meal_items=local_items, meal_portion=meal_portion,
            meal_portion_text=pt if has_portion else None, meal_ts=meal_ts)

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

    # "that's all" / "bas" / "ho gaya" — polite ack, nothing is logged.
    if _is_done(raw):
        return IntakeResult(
            intent="done", missing=[], should_reply=True, raw_text=raw,
            confidence=0.96, analyzed_by="local-refiner",
            reply=(f"{name} ji, sab log ho gaya! Koi naya khana ya sugar ho to "
                   "bataiye, main log kar dungi."))

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
    # The patient's own script decides the reply language (deterministically).
    local.language = detect_language(raw)
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
    g_intent = str(parsed.get("intent") or "").strip()
    gem_reply = str(parsed.get("reply") or "").strip()
    noise = strip_reading_noise(raw)
    known_nums = sorted({float(m) for m in re.findall(r"\d{2,3}(?:\.\d)?", noise)
                         if 20 <= float(m) <= 600})

    def _real(readable: Optional[object]) -> Optional[float]:
        """A Gemini-reported reading is only real when it matches an actual
        number the patient wrote (in range). Never invents a value."""
        try:
            f = float(readable)
        except (TypeError, ValueError):
            return None
        if not (20 <= f <= 600):
            return None
        if any(abs(f - x) < 0.5 for x in known_nums):
            return f
        return None

    def _tag_ok(tag: Optional[object]) -> Optional[str]:
        t = str(tag or "").strip().lower().replace(" ", "")
        if t in ("fasting", "postprandial", "random", "postbreakfast",
                 "postlunch", "postdinner", "pre"):
            return t
        return None

    def _meal_items_from(raw_items: object) -> list:
        if isinstance(raw_items, str) and raw_items.strip():
            return _meal_items(raw_items, cfg)
        if isinstance(raw_items, list):
            names = [str(x).strip() for x in raw_items if str(x).strip()]
            if names:
                return _meal_items(", ".join(names[:4]), cfg)
        return []

    now_iso = reading_timestamp(raw, msg_ts or iso_now()).strftime(
        "%Y-%m-%dT%H:%M:%S")

    # 1) A genuinely unclear message → Gemini words the ONE follow-up question
    #    in the patient's language.
    if local.intent == "clarify" and gem_reply:
        local.reply = gem_reply
        local.analyzed_by = f"gemini:{parsed.get('_model', '')}"
        local.confidence = 0.98

    # 2) Reference / delete raises — only for cases the deterministic refiner
    #    could not already see (never double-handles naya/mistake answers).
    if parsed.get("is_reference") and local.intent == "clarify":
        local.intent = "meal_reference"
        local.missing = []
        local.reply = ""
        local.meal_ts = now_iso
    if parsed.get("is_delete") and local.intent == "clarify":
        low_ = raw.lower()
        if any(mw in low_ for mw in ("khana", "khaana", "meal", "dish",
                                     "food", "makan")):
            local.intent = "meal_delete"
        else:
            local.intent = "reading_delete"
            local.reading_ts = now_iso
        local.missing = []
        local.reply = ""
        local.should_reply = True

    # 3) Multiple readings ("8am 130, 9am 145") — every value must be real.
    gem_readings = parsed.get("readings") if isinstance(
        parsed.get("readings"), list) else []
    validated = []
    for mr in gem_readings:
        if not isinstance(mr, dict):
            continue
        gv = _real(mr.get("value"))
        if gv is None:
            continue
        validated.append({"value": gv,
                          "tag": _tag_ok(mr.get("tag")) or "random",
                          "ts_str": now_iso})
    if (g_intent == "reading" and local.intent != "multi_reading"
            and len(validated) >= 2):
        local.intent = "multi_reading"
        local.missing = []
        local.reply = ""
        local.multi_readings = validated
        local.meal_items = _meal_items_from(parsed.get("items"))

    # 4) Single reading upgrade (never invents a number).
    if (local.intent == "clarify" and g_intent in ("reading", "confirm")
            and not validated):
        gv = _real(parsed.get("reading"))
        if gv is not None:
            local.intent = "reading"
            local.reading_value = gv
            local.reading_status = "resolved"
            local.reading_tag = _tag_ok(parsed.get("reading_tag")) or "random"
            local.reading_ts = now_iso
            local.missing = []
            local.reply = (f'✅ Logged sugar {gv:g} '
                           f'({PATIENT_TAG_LABELS.get(local.reading_tag, local.reading_tag)}) — '
                           f'{_hm(now_iso)}. Aur kuch log karna hai — sugar ya khana?')

    # 5) Meal items — Gemini's dish extraction only fills a gap and only from
    #    real words the patient wrote.
    if local.intent == "meal" and not local.meal_items:
        g_items = _meal_items_from(parsed.get("items"))
        if g_items:
            local.meal_items = g_items
            g_portion = str(parsed.get("portion") or "").strip().lower()[:1]
            if g_portion in ("s", "m", "l"):
                local.meal_portion = g_portion
                if "portion" in (local.missing or []):
                    local.missing.remove("portion")
            local.meal_ts = now_iso
    elif local.intent == "clarify" and g_intent == "meal" and validated:
        g_items = _meal_items_from(parsed.get("items"))
        if g_items:
            local.intent = "meal"
            local.meal_items = g_items
            g_portion = str(parsed.get("portion") or "").strip().lower()[:1]
            local.meal_portion = g_portion if g_portion in ("s", "m", "l") else None
            local.missing = [] if local.meal_portion else ["portion"]
            local.meal_ts = now_iso
            local.reply = (f"✅ Logged khana: {', '.join(local.meal_items)}. "
                           f"Kya portion thi — small, medium ya large?")
    return local