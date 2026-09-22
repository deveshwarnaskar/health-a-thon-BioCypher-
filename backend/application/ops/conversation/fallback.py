"""Safe fallback replies (spec §34).

If AI is unavailable, or a value is uncertain, the engine must degrade
deterministically — it may never silently fail. Every fallback is neutral,
re-asks for the missing value, and avoids any clinical interpretation.
"""

from __future__ import annotations

from backend.infrastructure.parsing.conversation.taxonomy import ConversationIntent

_FALLBACKS: dict[ConversationIntent, str] = {
    ConversationIntent.MEAL_LOG: (
        "Muaf kijiye, main khane ka record clear nahi kar paya/payi. "
        "Kripya dobara likhein jaise: '2 roti aur dal' ya 'dosa aur sambar'."
    ),
    ConversationIntent.GLUCOSE_LOG: (
        "Muaf kijiye, main aapki sugar reading clear nahi kar paya/payi. "
        "Kripya ek value bhejein jaise '140 fasting' ya '180'."
    ),
    ConversationIntent.MEDICATION_CONFIRMATION: (
        "Muaf kijiye, main medicine ka record nahi samajh paya/payi. "
        "Kripya bataayein: kis dawai ki kon si dose li (jaise 'subah insulin le li')."
    ),
    ConversationIntent.DOCUMENT_UPLOAD: (
        "Aapki file/captio ka record note kar liya gaya hai. Report aur "
        "prescription upload karne par aapki care team unhe dekh sakti hai."
    ),
    ConversationIntent.HANDOFF_TO_CARE_TEAM: (
        "Maaf kijiye, main is waqt care team tak pahunch nahi paya. "
        "Kripya apne clinic/dost ko call karein agar yeh zaroori hai."
    ),
}

_FALLBACK_GENERAL = (
    "Muaf kijiye, main abhi kuch technical problem ka samna kar raha hoon. "
    "Kripya thodi der baad dobara try karein, ya 'help' bhejein."
)


def fallback_reply(intent: ConversationIntent, reply_ai: str | None = None) -> str:
    """Deterministic fallback for a failed/unavailable AI reply."""
    if reply_ai and reply_ai.strip():
        return reply_ai.strip()
    return _FALLBACKS.get(intent) or _FALLBACK_GENERAL


EMPTY_TRANSCRIPT_REPLY = (
    "Muaf kijiye, aapki voice message sunai nahi di. Kripya thoda aaram se "
    "dubara bolein, ya likh kar bhejein (jaise '140 fasting')."
)

NO_PENDING_DRAFT_MEAL_REPLY = (
    "Koi pending meal record nahi mila jise confirm kiya ja sake. Naya meal "
    "darz karne ke liye khane ka naam likhein (jaise: '2 roti dal')."
)

NO_PENDING_DRAFT_GLUCOSE_REPLY = (
    "Koi pending sugar reading nahi mili. Nayi reading bhejein jaise '140 fasting'."
)


__all__ = [
    "fallback_reply",
    "EMPTY_TRANSCRIPT_REPLY",
    "NO_PENDING_DRAFT_MEAL_REPLY",
    "NO_PENDING_DRAFT_GLUCOSE_REPLY",
]