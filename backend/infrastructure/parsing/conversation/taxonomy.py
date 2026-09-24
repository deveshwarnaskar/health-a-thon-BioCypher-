"""Full conversational intent taxonomy (spec §6) with multilingual vocab.

This is the conversation-layer superset. The legacy ``IntentType`` from
``backend.infrastructure.parsing.intent_firewall`` remains the outside contract
of the existing worker; this layer derives the same road as a bridge and adds
the intents the legacy firewall cannot express:

- MEDICATION_CONFIRMATION, CARE_TASK, REMINDER_RESPONSE, TIMELINE_REQUEST,
  PROFILE_HELP, LANGUAGE_CHANGE, DOCUMENT_UPLOAD, VOICE_MESSAGE,
  HANDOFF_TO_CARE_TEAM, GENERAL_DIABETES_TRACKING_HELP, NON_HEALTH_REQUEST.

Every classifier below is deterministic (regex + keyword sets). AI providers
may corroborate intent at higher confidence, but they may never overrule a
safety-blocking classification.
"""

from __future__ import annotations

import re
from enum import Enum

from ..intent_firewall import IntentType as LegacyIntentType


class ConversationIntent(str, Enum):
    """Spec §6 intent taxonomy (superset of the legacy firewall)."""

    GLUCOSE_LOG = "GLUCOSE_LOG"
    MEAL_LOG = "MEAL_LOG"
    MEDICATION_CONFIRMATION = "MEDICATION_CONFIRMATION"
    CARE_TASK = "CARE_TASK"
    CORRECTION = "CORRECTION"
    CONFIRM = "CONFIRM"
    CANCEL = "CANCEL"
    REMINDER_RESPONSE = "REMINDER_RESPONSE"
    STATUS_REQUEST = "STATUS_REQUEST"
    TIMELINE_REQUEST = "TIMELINE_REQUEST"
    PROFILE_HELP = "PROFILE_HELP"
    WHATSAPP_HELP = "WHATSAPP_HELP"
    LANGUAGE_CHANGE = "LANGUAGE_CHANGE"
    GENERAL_DIABETES_TRACKING_HELP = "GENERAL_DIABETES_TRACKING_HELP"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    VOICE_MESSAGE = "VOICE_MESSAGE"
    HANDOFF_TO_CARE_TEAM = "HANDOFF_TO_CARE_TEAM"
    NON_HEALTH_REQUEST = "NON_HEALTH_REQUEST"
    UNKNOWN = "UNKNOWN"


# Bridge: which legacy intent our engine lets the existing worker handle as-is.
LEGACY_HANDLED = {
    ConversationIntent.GLUCOSE_LOG,
    ConversationIntent.MEAL_LOG,
    ConversationIntent.CONFIRM,
    ConversationIntent.CANCEL,
    ConversationIntent.CORRECTION,
    ConversationIntent.STATUS_REQUEST,
    ConversationIntent.WHATSAPP_HELP,
}


def to_legacy(intent: ConversationIntent) -> LegacyIntentType | None:
    """Map a conversation intent back onto the legacy firewall enum (if any)."""
    mapping: dict[ConversationIntent, LegacyIntentType] = {
        ConversationIntent.GLUCOSE_LOG: LegacyIntentType.GLUCOSE_LOG,
        ConversationIntent.MEAL_LOG: LegacyIntentType.MEAL_LOG,
        ConversationIntent.CONFIRM: LegacyIntentType.CONFIRM,
        ConversationIntent.CANCEL: LegacyIntentType.CANCEL,
        ConversationIntent.CORRECTION: LegacyIntentType.CORRECT,
        ConversationIntent.STATUS_REQUEST: LegacyIntentType.STATUS,
        ConversationIntent.WHATSAPP_HELP: LegacyIntentType.HELP,
    }
    return mapping.get(intent)


# ---------------- Multilingual keyword vocabularies (deterministic) ---------
# Cover the primary code-switched dialect (Hinglish) plus common words in
# Bengali, Tamil, Telugu, Marathi, Gujarati, Odia, Assamese where they differ.

_LANG_NAME_HINTS: dict[str, set[str]] = {
    "hi": {"hindi", "hinglish", "hindwi"},
    "en": {"english"},
    "bn": {"bengali", "bangla", "bengoli"},
    "ta": {"tamil", "tamizh"},
    "te": {"telugu", "telugu"},
    "mr": {"marathi"},
    "gu": {"gujarati", "gujrati"},
    "or": {"odia", "oriya"},
    "as": {"assamese", "asamiya"},
    "ml": {"malayalam"},
    "kn": {"kannada"},
    "pa": {"punjabi", "panjabi"},
}

_LANG_CHANGE_MARKERS = {
    "language change",
    "change language",
    "language badal",
    "bhasha badlo",
    "bhasha change",
    "language",
    "bhasha",
    "map bhasha",
    "bhasha badal",
    "boli badlo",
    "language set",
    "in language",
    "mein baat karna",
    "me baat karu",
    "mein baat karu",
}

_EMERGENCY_MARKERS = {
    "emergency",
    "ambulance",
    "heart attack",
    "unconscious",
    "behosh",
    "bahut takleef",
    "severe pain",
    "chest pain",
    "sine mein dard",
    "saans nahi aa rahi",
    "breathing",
    "108",
    "112",
    "turant doctor",
    "emergency mein",
    "hospital le chalo",
    "khoon",
    "bleeding",
    "gambhir",
    "critical",
    "dangar",
    "convulsion",
    "seizure",
    "daura",
    "faint",
    "gir gaya",
}

_HANDOFF_MARKERS = {
    "speak to doctor",
    "talk to doctor",
    "doctor se baat",
    "care team",
    "care team se",
    "nurse",
    "clinic call",
    "call clinic",
    "contact doctor",
    "doctor se baat karni hai",
    "human",
    "real person",
    "insaan se baat",
    "agent",
    "caregiver se baat",
    "caregiver",
    "care coordinator",
    "call kare",
    "habib jabab",
    "doctor ko bulao",
}

_MEDICATION_MARKERS = set(
    {
        "medicine",
        "dawai",
        "dava",
        "goli",
        "tablet",
        "pill",
        "insulin",
        "dose",
        "does",
        "dosage",
        "matra",
        "khuraak",
        "medication",
        "injection",
        "needle",
        "sui",
        "meter",
        "mater",
        "syrup",
        "sharbat",
        "tonic",
        "metformin",
        "glimepiride",
        "gliclazide",
        "sitagliptin",
        "teneligliptin",
        "vildagliptin",
        "empagliflozin",
        "dapagliflozin",
        "glipizide",
        "pioglitazone",
        "glycomet",
        "januvia",
    }
)

_MED_STATUS_MARKERS = {
    "le li",
    "le liya",
    "li",
    "kha li",
    "took",
    "taken",
    "had",
    "ho gaya",
    "ho gya",
    "done",
    "complete",
    "ho chuka",
    "leni hai",
    "leni h",
    "le sakta",
    "losona",
    "missed",
    "nahi li",
    "chhut gaya",
    "chhoot gaya",
    "skip",
    "skipped",
    "forgot",
    "bhool gaya",
    "bhool gayi",
}

_DOSAGE_CHANGE_MARKERS = {
    "badao",
    "badha do",
    "badhao",
    "kam karo",
    "kam kar do",
    "bada lene",
    "kam lene",
    "increase dose",
    "decrease dose",
    "reduce",
    "increase",
    "double",
    "adjust",
    "adjust karo",
    "change dose",
    "dose change",
    "dose barhao",
    "dose kam",
    "units badha",
    "units kam",
}

_TASK_MARKERS = {
    "task",
    "kaam",
    "kar lo",
    "karna hai",
    "remind me",
    "yaad dilao",
    "yaad dila",
    "reminder",
    "yaad",
    "todo",
    "to-do",
    "kal",
    "tomorrow",
    "subah",
    "shaam",
    "raat",
    "6 baje",
    "baje",
    "at 8",
    "at 9",
    "by 10",
    "remember",
    "note down",
    "likh lo",
    "note kar",
}

_DOCUMENT_MARKERS = set(
    {
        "report",
        "lab",
        "lab report",
        "prescription",
        "parchi",
        "discharge",
        "summary",
        "sugar book",
        "diary",
        "photo",
        "photo bhej",
        "report bhej",
        "bhej raha hoon",
        "send file",
        "upload",
        "upload karo",
        "prescription photo",
        "document",
        "file",
        "attachment",
        "scan",
        "pdf",
        "image",
    }
)

_INSULIN_MARKERS = {"insulin", "sui", "needle", "diabetic injection"}

_DIAGNOSIS_MARKERS = {
    "diagnosis",
    "diagnose",
    "kya bimari hai",
    "which disease",
    "do i have",
    "diabetes hai kya",
    "mujhe diabetes hai",
    "my diagnosis",
    "what is wrong",
    "kia masla hai",
    "kya beemari",
    "batao kya hua hai",
}

_PROGNOSIS_MARKERS = {
    "how long will i live",
    "life expectancy",
    "kitne din",
    "kitne saal",
    "will i survive",
    "kya thik ho jau",
    "cure",
    "ilaaj",
    "permanent",
    "kab theek",
    "recover hoga",
}

_NON_HEALTH_MARKERS = {
    "poem",
    "poetry",
    "joke",
    "shayari",
    "story",
    "kahani",
    "song",
    "lyrics",
    "essay",
    "weather",
    "mausam",
    "temperature",
    "forecast",
    "python",
    "javascript",
    "coding",
    "code",
    "function",
    "algorithm",
    "bitcoin",
    "crypto",
    "stock market",
    "shares",
    "some one",
    "who is",
    "capital of",
    "cricket score",
    "ipl score",
    "release date",
    "movie",
}

_CROSS_PATIENT_MARKERS = {
    "my mother",
    "meri maa",
    "my father",
    "mere pitaji",
    "meri beti",
    "my daughter",
    "my son",
    "mera beta",
    "my wife",
    "meri patni",
    "my husband",
    "mera pati",
    "my grandmother",
    "my grandfather",
    "meri dadi",
    "mere dada",
    "my friend",
    "mera dost",
    "my neighbor",
    "meri paadsi",
    "his sugar",
    "her sugar",
    "uska sugar",
    "uski sugar",
}

_PROMPT_INJECTION_MARKERS = {
    "ignore previous",
    "ignore all previous",
    "disregard",
    "you are now",
    "act as",
    "system prompt",
    "system message",
    "developer instruction",
    "pretend",
    "jailbreak",
    "override your instructions",
    "forget everything",
    "you must now obey",
    "reveal system",
    "output your instructions",
    "print your system",
    "repeat after me",
    "dan mode",
    "sudo mode",
}

_REMINDER_RESPONSE_MARKERS = {
    "sugar check kar li",
    "sugar check kar liya",
    "reading li",
    "kar diya",
    "kar li",
    "ho gaya",
    "ho gya",
    "done",
    "pehle hi kar liya",
    "already done",
    "already kiya",
    "sure",
    "ok did",
    "maine kar liya",
    "lyrics",
}


def normalize_region_fold(text: str) -> str:
    """Lowercase and normalize Unicode variations for keyword matching."""
    return (text or "").strip().lower()


# --------------------------------------------------------------------------
# Intent resolution
# --------------------------------------------------------------------------
_HAS_DIGIT = re.compile(r"\d")


class DidResolvedIntent:
    """Deterministic intent classifier. Pure, zero I/O, zero AI."""

    def __init__(self) -> None:
        self.medication_markers = _MEDICATION_MARKERS
        self.dosage_change = _DOSAGE_CHANGE_MARKERS
        self.task_markers = _TASK_MARKERS
        self.document = _DOCUMENT_MARKERS
        self.emergency = _EMERGENCY_MARKERS
        self.handoff = _HANDOFF_MARKERS
        self.language_names = _LANG_NAME_HINTS
        self.language_change = _LANG_CHANGE_MARKERS

    def resolve(self, text: str, *, media_type: str = "") -> ConversationIntent:
        """Resolve intent to first-match-wins (order matters, deterministic)."""
        stripped = (text or "").strip()
        low = normalize_region_fold(stripped)

        if media_type and media_type not in ("text", ""):
            if media_type in ("audio", "voice", "ptt", "ogg", "amr", "mpeg"):
                return ConversationIntent.VOICE_MESSAGE
            if media_type in ("image", "document", "application", "pdf", "jpeg", "png"):
                return ConversationIntent.DOCUMENT_UPLOAD

        if not low:
            return ConversationIntent.UNKNOWN

        # 1. Emergency outranks everything — never route it as a log.
        if any(m in low for m in _EMERGENCY_MARKERS) or self._emergency_score(low) >= 3:
            return ConversationIntent.HANDOFF_TO_CARE_TEAM

        # 2. Prompt injection → non-health (blocked by the safety engine).
        if any(m in low for m in _PROMPT_INJECTION_MARKERS):
            return ConversationIntent.NON_HEALTH_REQUEST

        # 3. Non-health overt requests.
        if any(m in low for m in _NON_HEALTH_MARKERS):
            return ConversationIntent.NON_HEALTH_REQUEST

        # 4. Language change.
        if any(m in low for m in self.language_change) and any(
            name in low for name in set().union(*self.language_names.values())
        ):
            return ConversationIntent.LANGUAGE_CHANGE

        # 5. Handoff / care team.
        if any(m in low for m in self.handoff):
            return ConversationIntent.HANDOFF_TO_CARE_TEAM

        # 6. Medication confirmation & dosage adjustments.
        medication_hit = any(m in low for m in self.medication_markers)
        if medication_hit:
            if any(m in low for m in _DOSAGE_CHANGE_MARKERS) or any(
                m in low for m in _INSULIN_MARKERS
            ):
                return ConversationIntent.HANDOFF_TO_CARE_TEAM
            return ConversationIntent.MEDICATION_CONFIRMATION

        # 7. Document upload.
        if any(m in low for m in self.document):
            return ConversationIntent.DOCUMENT_UPLOAD

        # 8. Care task / self-reminder ("remind me to X at Y").
        if any(m in low for m in self.task_markers) and _HAS_DIGIT.search(stripped):
            return ConversationIntent.CARE_TASK
        if any(m in low for m in self.task_markers) and any(
            m in low for m in ("kal", "tomorrow", "subah", "shaam", "raat")
        ):
            return ConversationIntent.CARE_TASK

        # 9. Timeline request ("tell me my readings this week").
        if any(m in low for m in ("timeline", "this week", "last week", "iss hafte", "pichle hafte", "list of readings", "sab readings", "all readings")):
            return ConversationIntent.TIMELINE_REQUEST

        # 10. Reminder response ("sugar check kar li", "kar diya", "done").
        if low in self._short_responses() or (
            any(m in low for m in _REMINDER_RESPONSE_MARKERS)
            and any(m in low for m in ("kar li", "kar diya", "ho gaya", "ho gya", "done"))
        ):
            return ConversationIntent.REMINDER_RESPONSE

        # 11. Cross-patient requests must reach safety, not the log parsers.
        if any(m in low for m in _CROSS_PATIENT_MARKERS):
            return ConversationIntent.UNKNOWN

        # 12. Legacy-bridge: glucose / meal / confirm / cancel / status / help.
        from ..intent_firewall import IntentFirewall

        legacy = IntentFirewall.evaluate(stripped)
        if legacy.intent in {
            LegacyIntentType.GLUCOSE_LOG,
            LegacyIntentType.MEAL_LOG,
            LegacyIntentType.CONFIRM,
            LegacyIntentType.CORRECT,
            LegacyIntentType.CANCEL,
            LegacyIntentType.STATUS,
            LegacyIntentType.HELP,
        }:
            return _LEGACY_TO_CONVERSATION[legacy.intent]

        if legacy.intent == LegacyIntentType.UNSUPPORTED or (
            legacy.is_supported is False
        ):
            return ConversationIntent.NON_HEALTH_REQUEST

        # 13. Everything else is general diabetes-tracking help or unknown.
        return ConversationIntent.GENERAL_DIABETES_TRACKING_HELP

    def _short_responses(self) -> set[str]:
        return {"done", "kar diya", "kar li", "ho gaya", "ho gya", "ok", "okay"}

    def _emergency_score(self, low: str) -> int:
        score = 0
        for m in _EMERGENCY_MARKERS:
            if m in low:
                score += 1
        return score


_LEGACY_TO_CONVERSATION = {
    LegacyIntentType.GLUCOSE_LOG: ConversationIntent.GLUCOSE_LOG,
    LegacyIntentType.MEAL_LOG: ConversationIntent.MEAL_LOG,
    LegacyIntentType.CONFIRM: ConversationIntent.CONFIRM,
    LegacyIntentType.CORRECT: ConversationIntent.CORRECTION,
    LegacyIntentType.CANCEL: ConversationIntent.CANCEL,
    LegacyIntentType.STATUS: ConversationIntent.STATUS_REQUEST,
    LegacyIntentType.HELP: ConversationIntent.WHATSAPP_HELP,
    LegacyIntentType.CONVERSATIONAL: ConversationIntent.GENERAL_DIABETES_TRACKING_HELP,
}


__all__ = [
    "ConversationIntent",
    "DidResolvedIntent",
    "LEGACY_HANDLED",
    "to_legacy",
    "normalize_region_fold",
]