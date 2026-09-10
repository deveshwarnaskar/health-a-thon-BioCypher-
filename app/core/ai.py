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


def call_llm_reasoning(text: str, patient_name: str, cfg: Optional[Settings] = None) -> Optional[AIRefinement]:
    """Call an LLM (Gemini or OpenAI) if API key is provided for deep dialect & reasoning."""
    key = os.environ.get("GEMINI_API_KEY") or getattr(cfg, "gemini_api_key", "")
    if not key:
        return None
    try:
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
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
        resp = httpx.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=3.5
        )
        if resp.status_code == 200:
            data = resp.json()
            raw_content = data["candidates"][0]["content"]["parts"][0]["text"]
            # Extract JSON block
            m = re.search(r"\{.*\}", raw_content, re.DOTALL)
            if m:
                parsed = json.loads(m.group(0))
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
    except Exception as e:
        # LLM network timeout or parsing issue; seamlessly fall back to local engine
        pass
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
                if any(k in low for k in ("fasting", "fast", "fbs", "khali", "morning", "subah")):
                    tag = "fasting"
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
        f"Kya aap sugar reading bhejna chahte hain (jaise 'sugar 130') ya khana (jaise '2 roti dal')? "
        f"Kripya thoda aur batayein."
    )
    return AIRefinement(
        intent="clarify",
        confidence=0.40,
        raw_text=raw,
        clarification_question=clarify,
        conversational_reply=clarify
    )
