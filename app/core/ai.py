"""Conversational AI layer for Aahaar.

Handles:
  1. Human typing errors, phonetic typos, mixed Hindi/English/Hinglish speech.
  2. Intent & entity extraction (blood sugar readings vs meal descriptions vs confirms).
  3. "Talking Back AI": Warm, empathetic conversational responses; asks polite clarifying
     questions when genuinely confused rather than failing silently.
  4. Pluggable: Uses Gemini/OpenAI/Groq if an API key is set, with a rock-solid,
     zero-latency local fuzzy semantic refiner as the resilient baseline.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..config import Settings

# Common OCR / keyboard typos, dialects, visual descriptions
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


@dataclass
class AIRefinement:
    intent: str                      # "reading" | "meal" | "confirm" | "clarify" | "unknown"
    confidence: float
    raw_text: str
    reading: Optional[float] = None
    reading_tag: Optional[str] = None
    dishes: list[str] = field(default_factory=list)
    portion: Optional[str] = "m"
    clarification_question: Optional[str] = None
    conversational_reply: Optional[str] = None


_last_ai_status: dict = {
    "configured": False,
    "last_call_ts": None,
    "last_model": None,
    "last_status": "idle",
    "last_error": None,
}

# Current stable Gemini flash endpoints (2026). Older generations (2.x, 1.x)
# 404 for new API keys, so keep only the current stable Flash family here and
# prefer live model discovery for anything newer.
_CURRENT_MODELS: tuple = ("gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite")

_model_cache: dict = {"ts": None, "models": None}


def discover_models(api_key: str, cache_for: float = 900.0) -> list[str]:
    """Pick the newest available generateContent flash models for a key.

    Asks the models endpoint once (cached per-process), then filters for
    chat-capable Gemini text models. Never raises: any failure falls back to the
    hardcoded current list.
    """
    import time
    now = time.time()
    cached = _model_cache.get("models")
    if cached and _model_cache.get("ts") and (now - _model_cache["ts"]) < cache_for:
        return cached
    chosen = list(_CURRENT_MODELS)
    try:
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        resp = httpx.get(url, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            names = []
            for m in data.get("models", []):
                name = str(m.get("name") or "")
                methods = m.get("supportedGenerationMethods") or []
                if "generateContent" not in methods or not name.startswith("models/gemini-"):
                    continue
                short = name.split("/")[-1]
                if not re.search(r"flash|lite", short, re.I):
                    continue
                if any(tag in short for tag in ("-tts", "-live", "-image",
                                                "-transcribe", "-translator")):
                    continue
                names.append(short)
            # newest first is not guaranteed; prefer short newer-ish names,
            # otherwise just present them all for runtime fallback
            names.sort(key=lambda s: (not s.startswith("gemini-3"), s))
            if names:
                chosen = names[:5]
    except Exception:
        pass
    _model_cache["ts"] = now
    _model_cache["models"] = chosen
    return chosen


def get_last_ai_status() -> dict:
    key = os.environ.get("GEMINI_API_KEY", "")
    _last_ai_status["configured"] = bool(key)
    _last_ai_status["masked_key"] = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else ("set" if key else "not_set")
    return dict(_last_ai_status)


def test_gemini_api(api_key: Optional[str] = None) -> dict:
    """Explicit test probe for Gemini API connectivity."""
    key = (api_key or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        return {"success": False, "error": "No GEMINI_API_KEY provided or set in environment"}

    models = discover_models(key)
    errors = []
    for model in models:
        try:
            import httpx
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            resp = httpx.post(
                url,
                json={"contents": [{"parts": [{"text": "Hello! Reply strictly with 'Aahaar Gemini AI is active!'"}]}]},
                timeout=5.0
            )
            if resp.status_code == 200:
                data = resp.json()
                reply = data["candidates"][0]["content"]["parts"][0]["text"]
                return {
                    "success": True,
                    "model": model,
                    "reply": reply.strip(),
                    "message": f"Successfully connected to Google Gemini API using model {model}!"
                }
            else:
                errors.append(f"{model}: HTTP {resp.status_code} - {resp.text[:120]}")
        except Exception as e:
            errors.append(f"{model}: {str(e)}")

    return {"success": False, "error": "All models failed", "details": errors}


def call_llm_reasoning(text: str, patient_name: str, cfg: Optional[Settings] = None) -> Optional[AIRefinement]:
    """Call Google Gemini if API key is provided for deep dialect & reasoning."""
    key = os.environ.get("GEMINI_API_KEY") or getattr(cfg, "gemini_api_key", "")
    if not key:
        _last_ai_status["configured"] = False
        _last_ai_status["last_status"] = "key_missing"
        return None

    # Safety gate (AAHAAR_AI_ON_INBOUND): the live WhatsApp/webhook path never
    # calls an LLM by default. Patient input is stored verbatim; the deep model
    # is only usable offline (scripts/analyze_stored.py) unless explicitly opted in.
    if not getattr(cfg, "ai_on_inbound", False):
        _last_ai_status["configured"] = bool(key)
        _last_ai_status["last_status"] = "gated_offlive"
        return None

    _last_ai_status["configured"] = True
    _last_ai_status["last_call_ts"] = datetime.now().isoformat()

    # Ultra-compact ~100 token prompt to preserve context window and reduce latency
    prompt = (
        f"Clinical diabetes assistant. Patient: {patient_name}. Message: '{text[:200]}'.\n"
        "Analyze intent and return strictly valid JSON: "
        "{\"intent\": \"reading\"|\"meal\"|\"confirm\"|\"clarify\", "
        "\"reading\": number or null, "
        "\"reading_tag\": \"fasting\"|\"postbreakfast\"|\"postlunch\"|\"postdinner\"|\"pre\"|\"postprandial\" or null, "
        "\"dishes\": [\"dish1\", ...], "
        "\"conversational_reply\": \"short helpful reply in patient language\"}"
    )

    models = discover_models(key)
    last_err = None

    for model in models:
        try:
            import httpx
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            resp = httpx.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=4.0
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_content = data["candidates"][0]["content"]["parts"][0]["text"]
                m = re.search(r"\{.*\}", raw_content, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(0))
                    _last_ai_status["last_status"] = "success"
                    _last_ai_status["last_model"] = model
                    _last_ai_status["last_error"] = None
                    return AIRefinement(
                        intent=parsed.get("intent", "clarify"),
                        confidence=0.98,
                        raw_text=text,
                        reading=parsed.get("reading"),
                        reading_tag=parsed.get("reading_tag"),
                        dishes=parsed.get("dishes", []),
                        conversational_reply=parsed.get("conversational_reply"),
                        clarification_question=parsed.get("conversational_reply") if parsed.get("intent") == "clarify" else None
                    )
            elif resp.status_code == 404:
                last_err = f"{model} returned 404 Not Found"
                continue
            else:
                last_err = f"{model} returned HTTP {resp.status_code}: {resp.text[:120]}"
        except Exception as e:
            last_err = f"{model} exception: {str(e)}"

    _last_ai_status["last_status"] = "error"
    _last_ai_status["last_error"] = last_err
    return None


def refine_text_local(text: str) -> str:
    """Correct common keyboard typos, dialects, and phonetic misspellings."""
    s = text.strip()
    for pattern, replacement in _TYPO_MAP.items():
        s = re.sub(pattern, replacement, s, flags=re.I)
    return s


def analyze_patient_input(text: str, patient_name: str = "Patient",
                          cfg: Optional[Settings] = None) -> AIRefinement:
    """Analyze messy/typo-filled patient text into structured intent."""
    raw = text or ""
    # 0. If Gemini/LLM is configured, use deep multimodal semantic reasoning
    llm_res = call_llm_reasoning(raw, patient_name, cfg)
    if llm_res is not None:
        return llm_res

    cleaned = refine_text_local(raw)
    low = cleaned.lower()

    # 1. Check for simple confirmations
    confirm_words = {"yes", "y", "ok", "okay", "confirm", "ha", "haan", "theek",
                     "theek hai", "thik", "sahi", "sahi hai", "ji", "ji haan", "done"}
    words = set(low.split())
    if words and (words.issubset(confirm_words) or low in confirm_words):
        return AIRefinement(
            intent="confirm",
            confidence=0.95,
            raw_text=raw,
            conversational_reply="Ji, note kar liya hai! Report me add ho gaya hai."
        )

    # 2. Check for blood sugar reading (allows typos, Hindi, conversational phrasing)
    num_match = re.search(r"\b(\d{2,3}(?:\.\d)?)\s*(?:mg/?dl)?\b", low)
    sugar_hints = ("sugar", "glucose", "bg", "fbs", "rbs", "ppbg", "fasting", "fast",
                   "khali", "pet", "subah", "morning", "lunch", "dinner", "nashta",
                   "reading", "level", "aaya", "tha", "hai", "mgdl", "mg/dl",
                   "prick", "fingerprick", "finger prick", "glucometer", "strip", "blood sugar", "pricking")

    if num_match:
        try:
            val = float(num_match.group(1))
        except ValueError:
            val = None

        if val is not None and 20 <= val <= 600:
            has_sugar_hint = any(h in low for h in sugar_hints)
            # If explicit sugar hint, or text is mostly just the number
            if has_sugar_hint or len(low.split()) <= 3:
                tag = "postprandial"
                if any(k in low for k in ("fasting", "fast", "fbs", "khali", "roza", "empty stomach")):
                    tag = "fasting"
                elif any(k in low for k in ("random", "rdn", "rbg")):
                    tag = "random"
                elif any(k in low for k in ("breakfast", "nashta", "pb")):
                    tag = "postbreakfast"
                elif any(k in low for k in ("lunch", "dopahar", "pl")):
                    tag = "postlunch"
                elif any(k in low for k in ("dinner", "raat", "pd")):
                    tag = "postdinner"
                elif any(k in low for k in ("pre", "before", "pehle")):
                    tag = "pre"

                friendly_tag = {
                    "fasting": "fasting (khali pet)",
                    "postbreakfast": "post-breakfast (nashte ke baad)",
                    "postlunch": "post-lunch (dopahar ke baad)",
                    "postdinner": "post-dinner (raat ke baad)",
                    "postprandial": "postprandial (khane ke baad)",
                    "random": "random",
                    "pre": "pre-meal (khane se pehle)",
                }.get(tag, tag)

                reply = (
                    f"Ji {patient_name} ji! Aapka {friendly_tag} sugar reading {val:.0f} mg/dL "
                    f"record ho gaya hai. Doctor consult me ye dikhega."
                )
                return AIRefinement(
                    intent="reading",
                    confidence=0.92,
                    raw_text=raw,
                    reading=val,
                    reading_tag=tag,
                    conversational_reply=reply
                )

    # 2b. Patient sent glucose tag/keyword without the reading number
    tag_only_hints = ("fasting", "fast", "fbs", "sugar", "glucose", "ppbg", "rbs", "khali pet", "prick", "glucometer", "finger prick")
    if any(th in low for th in tag_only_hints) and not num_match:
        tag_name = "fasting (khali pet)" if any(k in low for k in ("fasting", "fast", "fbs", "khali")) else "sugar"
        reply = (
            f"Namaste {patient_name} ji! Aapne '{cleaned}' likha hai. "
            f"Kripya apna {tag_name} reading number batayein (jaise 'fasting 120' ya 'sugar 140')."
        )
        return AIRefinement(
            intent="clarify",
            confidence=0.85,
            raw_text=raw,
            clarification_question=reply,
            conversational_reply=reply
        )

    # 3. Check for food / meal description
    food_hints = ("roti", "chapati", "phulka", "rice", "chawal", "dal", "daal",
                  "sabzi", "sabji", "curry", "paneer", "chicken", "salad", "dahi",
                  "khichdi", "paratha", "dosa", "idli", "poha", "upma", "khaya",
                  "ate", "eating", "food", "dinner", "lunch", "breakfast", "nashta")

    matched_foods = [f for f in food_hints if f in low and f not in ("khaya", "ate", "eating", "food")]
    if matched_foods or any(w in low for w in ("khaya", "ate", "eating", "dinner", "lunch", "breakfast", "nashta")):
        dishes = matched_foods or [cleaned[:30].strip()]
        reply = (
            f"Maine aapka meal ({', '.join(dishes)}) note kar liya. "
            f"Portion Medium (220 ml) hai na? Reply karein YES, ya 'small/large'."
        )
        return AIRefinement(
            intent="meal",
            confidence=0.88,
            raw_text=raw,
            dishes=dishes,
            portion="m",
            conversational_reply=reply
        )

    # 4. Ambiguous / Confusing input -> Ask polite clarifying question ("Talking Back AI")
    clarify = (
        f"Namaste {patient_name} ji! I didn't understand that completely (mujhe thoda samajh nahi aaya). "
        f"Kripya apni sugar reading bataiye (jaise 'sugar 130' ya 'fasting 120')."
    )
    return AIRefinement(
        intent="clarify",
        confidence=0.40,
        raw_text=raw,
        clarification_question=clarify,
        conversational_reply=clarify
    )
