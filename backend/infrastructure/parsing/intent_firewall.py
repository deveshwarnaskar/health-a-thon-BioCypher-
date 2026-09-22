"""Intent Firewall for WhatsApp Inbound Messages.

Intercepts incoming conversational messages and classifies them before domain
processing. Prevents arbitrary queries (e.g. poetry, coding, weather, general QA)
from creating invalid clinical state or wasting compute resources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .hinglish_parser import (
    _is_cancel,
    _is_confirm,
    ambiguous_reading_values,
    parse_inbound,
)
from .nutrition_taxonomy import classify_text


class IntentType(str, Enum):
    GLUCOSE_LOG = "GLUCOSE_LOG"
    MEAL_LOG = "MEAL_LOG"
    CONFIRM = "CONFIRM"
    CORRECT = "CORRECT"
    CANCEL = "CANCEL"
    STATUS = "STATUS"
    HELP = "HELP"
    CONVERSATIONAL = "CONVERSATIONAL"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class IntentVerdict:
    intent: IntentType
    is_supported: bool
    guidance_message: str | None = None
    extracted_text: str = ""


# Guidance messages for non-intake intents (zero PHI)
HELP_MESSAGE = (
    "Namaste! THALI × P.L.A.T.E. WhatsApp Assistant:\n"
    "• Sugar darz karein: '120 fasting' ya '160 pp'\n"
    "• Khana darz karein: '2 roti dal'\n"
    "• Confirm karein: 'haan' ya 'theek hai'\n"
    "• Cancel karein: 'cancel'\n\n"
    "Medical emergency ke liye turant apne doctor ya hospital se sampark karein."
)

CANCEL_MESSAGE = "Aapka pending meal record cancel kar diya gaya hai."

UNSUPPORTED_MESSAGE = (
    "Main aapka THALI × P.L.A.T.E. health assistant hoon. "
    "Main kewal aapke blood sugar (glucose) aur meals record karne mein madad kar sakta hoon.\n\n"
    "Udaharan:\n"
    "• Glucose: '140 fasting' ya '180'\n"
    "• Meal: '2 roti aur dal'\n"
    "• Help: 'help' type karein."
)


class IntentFirewall:
    """Classifies inbound channel text and blocks non-clinical intents safely."""

    _HELP_EXACT = {
        "help",
        "madad",
        "kaise use karein",
        "commands",
        "menu",
        "info",
        "hi",
        "hello",
        "namaste",
        "pranam",
        "start",
    }

    _CANCEL_EXACT = {
        "cancel",
        "radd",
        "chhod do",
        "mat karo",
        "delete",
        "stop",
        "dismiss",
        "nahi chahiye",
        "abort",
        "confirm_cancel",
        "btn_cancel",
        "cancel / radd",
        "cancel/radd",
        "radd / cancel",
        "radd/cancel",
        "galat",
        "no",
        "nahi",
        "nhi",
        "na",
    }

    _STATUS_PATTERNS = (
        r"\b(status|summary|report|readings?)\b",
        r"\b(aaj\s+ka\s+(summary|report|sugar))\b",
        r"\b(mera\s+(sugar|status|record))\b",
    )

    _UNSUPPORTED_PATTERNS = (
        r"\b(poem|poetry|joke|jokes|shayari|story|kahani|song|lyrics|essay)\b",
        r"\b(weather|temperature|mausam|barish|forecast|climate)\b",
        r"\b(python|javascript|coding|code|function|debug|algorithm|def\s+|import\s+|class\s+|console\.log|print\(|select\s+.*\s+from)\b",
        r"\b(bitcoin|crypto|stock\s*market|invest|trading|shares?)\b",
        r"\b(who\s+is|who\s+won|capital\s+of|president|prime\s+minister|match\s+score|ipl\s+score|cricket\s+score)\b",
        r"\b(write\s+a\s+|tell\s+me\s+a\s+|generate\s+a\s+|can\s+you\s+write)\b",
    )

    @classmethod
    def evaluate(cls, text: str, interactive_reply_id: str | None = None) -> IntentVerdict:
        stripped = (text or "").strip()
        if interactive_reply_id in ("confirm_yes", "btn_confirm"):
            return IntentVerdict(
                intent=IntentType.CONFIRM,
                is_supported=True,
                extracted_text=stripped,
            )
        if interactive_reply_id in ("confirm_cancel", "btn_cancel"):
            return IntentVerdict(
                intent=IntentType.CANCEL,
                is_supported=True,
                guidance_message=CANCEL_MESSAGE,
                extracted_text=stripped,
            )

        if not stripped:
            return IntentVerdict(
                intent=IntentType.UNSUPPORTED,
                is_supported=False,
                guidance_message=UNSUPPORTED_MESSAGE,
                extracted_text="",
            )

        low = stripped.lower()

        # 1. Cancel check
        if _is_cancel(stripped) or low in cls._CANCEL_EXACT or any(low == f"cancel {x}" for x in ("meal", "draft", "entry")):
            return IntentVerdict(
                intent=IntentType.CANCEL,
                is_supported=True,
                guidance_message=CANCEL_MESSAGE,
                extracted_text=stripped,
            )

        # 2. Exact help / greetings
        if low in cls._HELP_EXACT or low.startswith("help "):
            return IntentVerdict(
                intent=IntentType.HELP,
                is_supported=True,
                guidance_message=HELP_MESSAGE,
                extracted_text=stripped,
            )

        # 3. Status check
        has_advice_or_number = bool(re.search(r"\b\d{2,3}\b", stripped) or re.search(r"\b(kya\s+karu|advice|madad|kya\s+karein)\b", low))
        if not has_advice_or_number and any(re.search(pat, low) for pat in cls._STATUS_PATTERNS):
            return IntentVerdict(
                intent=IntentType.STATUS,
                is_supported=True,
                guidance_message=None,
                extracted_text=stripped,
            )

        # 4. Check for overt unsupported patterns (poetry, coding, weather, general QA)
        if any(re.search(pat, low) for pat in cls._UNSUPPORTED_PATTERNS):
            return IntentVerdict(
                intent=IntentType.UNSUPPORTED,
                is_supported=False,
                guidance_message=UNSUPPORTED_MESSAGE,
                extracted_text=stripped,
            )

        # 4b. Conversational healthcare, onboarding how-to, symptoms, and dietary guidance
        from backend.infrastructure.channel.conversational_assistant import match_conversational_query
        conv_reply = match_conversational_query(stripped)
        if conv_reply is not None:
            return IntentVerdict(
                intent=IntentType.CONVERSATIONAL,
                is_supported=True,
                guidance_message=conv_reply,
                extracted_text=stripped,
            )

        # 5. Check if it's a glucose reading (including ambiguous)
        if ambiguous_reading_values(stripped):
            return IntentVerdict(
                intent=IntentType.GLUCOSE_LOG,
                is_supported=True,
                extracted_text=stripped,
            )

        parsed = parse_inbound(stripped)
        if parsed.is_reading:
            return IntentVerdict(
                intent=IntentType.GLUCOSE_LOG,
                is_supported=True,
                extracted_text=stripped,
            )

        # 6. Confirm or correct
        if parsed.is_confirm or _is_confirm(stripped):
            return IntentVerdict(
                intent=IntentType.CONFIRM,
                is_supported=True,
                extracted_text=stripped,
            )

        if parsed.kind == "cancel" or _is_cancel(stripped):
            return IntentVerdict(
                intent=IntentType.CANCEL,
                is_supported=True,
                guidance_message=CANCEL_MESSAGE,
                extracted_text=stripped,
            )

        if parsed.kind == "correct":
            return IntentVerdict(
                intent=IntentType.CORRECT,
                is_supported=True,
                extracted_text=stripped,
            )

        # 7. Meal candidate: check if recognizable food items or meal context exists
        # If the text is asking a question (contains ? or question phrasing), it is a conversational query, NOT a meal log
        is_question = bool(
            "?" in stripped
            or re.search(r"\b(kya|can|should|how|what|why|kab|kaise|batao|tell|is\s+it|hai\s+kya)\b", low)
        )

        food_items = classify_text(stripped)
        meal_context_words = {
            "khana", "lunch", "dinner", "breakfast", "nashta", "roti", "chapati",
            "dal", "rice", "chawal", "sabzi", "curry", "bread", "milk", "doodh",
            "chai", "tea", "coffee", "egg", "anda", "paneer", "salad", "fruit",
            "ate", "had", "eating", "food", "diet", "meal", "katori", "plate",
        }
        words = set(re.findall(r"\w+", low))
        if not is_question and (food_items or (words & meal_context_words)):
            return IntentVerdict(
                intent=IntentType.MEAL_LOG,
                is_supported=True,
                extracted_text=stripped,
            )

        # 8. Conversational / Indic AI companion query
        # Patient queries, questions, greetings, feedback, or health discussions
        return IntentVerdict(
            intent=IntentType.CONVERSATIONAL,
            is_supported=True,
            extracted_text=stripped,
        )


__all__ = [
    "IntentType",
    "IntentVerdict",
    "IntentFirewall",
    "HELP_MESSAGE",
    "CANCEL_MESSAGE",
    "UNSUPPORTED_MESSAGE",
]
