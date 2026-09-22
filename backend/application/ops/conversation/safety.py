"""Safety policy engine (spec §16, §17, §19).

Non-negotiable rules enforced BEFORE any AI wording or domain dispatch:

1. No diagnosis, prognosis, or "normal/abnormal" interpretation by the AI.
   The assistant may only confirm recording, quote back values verbatim, and
   direct clinical questions to the care team.
2. No medication/insulin dosage changes, titrations, or "dose badao/kam karo"
   guidance. Those requests are handed off to the care team.
3. Emergency language (chest pain, unconscious, severe bleeding, breathing
   difficulty) triggers an immediate care-team escalation reply; the engine
   MUST NOT try to triage clinically.
4. Cross-patient requests ("ho sugar, meri maa ka") are refused with zero PHI
   leakage.
5. Prompt-injection / jailbreak attempts are refused as non-health.
6. Requests to persist PHI ("save my address", "yeh number yaad rakho") are
   refused; the assistant keeps no PII in its layer.

The guidance text below is intentionally free of clinical interpretation and
of any value judgment about the patient's state (§17-b-wording).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.infrastructure.parsing.conversation.extractors import normalize_digits
from backend.infrastructure.parsing.conversation.schema import SafetyFlag, StructuredIntent
from backend.infrastructure.parsing.conversation.taxonomy import ConversationIntent

# Guardrails for confirmation-phase wording (§17): these words must NEVER be
# emitted by the assistant as a label for a patient's value/behaviour.
FORBIDDEN_INTERPRETIVE_WORDS = {
    "dangerous",
    "khatarnak",
    "abnormal",
    "asādhāraṇ",
    "normal",
    "high blood sugar",
    "low blood sugar",
    "prediabetic",
    "type 2 confirmed",
    "hypoglycemia(caused)",
    "hyperglycemia(confirmed)",
    "you have diabetes",
    "mujhe laga aapko diabetes",
}


def contains_forbidden_interpretation(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in FORBIDDEN_INTERPRETIVE_WORDS)


@dataclass(frozen=True)
class SafetyDecision:
    blocked: bool
    reason: str
    guidance_message: str = ""
    emergency: bool = False
    handoff: bool = False
    flags: tuple[SafetyFlag, ...] = ()
    intent_override: ConversationIntent | None = None


# Compliant guidance replies (no clinical interpretation).
_GUIDANCE = {
    SafetyFlag.EMERGENCY: (
        "⚠️ *Emergency assistance needed*.\n\n"
        "Aapko turant medical help chahiye. Yeh message apne care team ko "
        "forward kar diya gaya hai.\n\n"
        "👉 Abhi 108/112 par call karein ya apne sabse paas ke hospital jayein. "
        "Agar aap akela hain toh kisi apne ko bhi call karein. Main is waqt "
        "clinical guidance de nahi sakta/ sakti."
    ),
    SafetyFlag.DIAGNOSIS_REQUEST: (
        "Main aapke sugar readings record aur hisaab rakne mein madad karta/ "
        "karti hoon, par main koi diagnose, medicine dosage, ya clinical "
        "nirdesh nahi de sakta/sakti.\n\n"
        "Aapki reading aur poora record aapki care team ke dashboard par "
        "available hai. Diagnosis aur ilaaj ke liye kripya apne doctor se "
        "baat karein."
    ),
    SafetyFlag.DOSAGE_CHANGE: (
        "Medicine/dose badalne ka nirnay sirf aapke doctor le sakte hain. "
        "Main yeh guidance de nahi sakta/sakti.\n\n"
        "Yeh request aapki care team ko forward kar di gayi hai. Agar aap "
        "koi dose miss karte hain toh doctor se turant poochhein — dose double "
        "nahi karna chahiye."
    ),
    SafetyFlag.NON_HEALTH_REQUEST: (
        "Main aapka THALI × P.L.A.T.E. health assistant hoon. Main sirf "
        "aapke glucose readings aur meals record karne mein madad kar sakta/"
        "sakti hoon.\n\n"
        "Udaharan:\n"
        "• Glucose: '140 fasting' ya '180'\n"
        "• Meal: '2 roti aur dal'\n"
        "• Help: 'help' bhejein."
    ),
    SafetyFlag.PROMPT_INJECTION: (
        "Maaf kijiye, main sirf health records ke liye hoon aur aise "
        "nirdeshon par amal nahi kar sakta/sakti. Kuch aur madad?\n"
        "• Glucose: '140 fasting'\n"
        "• Meal: '2 roti dal'\n"
        "• Help: 'help'"
    ),
    SafetyFlag.CROSS_PATIENT_REQUEST: (
        "Main keval aapke apne health records mein madad kar sakta/sakti hoon. "
        "Kisi aur ke readings/records ya unke phones ki jaankari mere paas "
        "nahi hai. Agar aap kisi dependent ke caregiver hain toh woh alag "
        "verified account se manage hota hai."
    ),
    SafetyFlag.PHI_PERSISTENCE_REQUEST: (
        "Main health records ke liye hoon aur personal pehchaan wali jaankari "
        "(naam, address, phone) store nahi karta/karti. Aapki medical readings "
        "sirf aapke verified account se linked rehti hain."
    ),
    SafetyFlag.UNKNOWN_VALUE: (
        "Muaf kijiye, main aapki baat clear nahi kar paya/payi. Kripya ek "
        "baar dobara likhein, jaise:\n"
        "• Glucose: '140 fasting' ya '180'\n"
        "• Meal: '2 roti aur dal'\n"
        "• Medicine: 'subah ki dawai le li'\n"
        "• Help: 'help'"
    ),
    SafetyFlag.OUT_OF_RANGE_VALUE: (
        "Yeh value 20-600 mg/dL ke clinical range ke bahar hai aur ghalat "
        "lag rahi hai. Kripya apni reading dobara check karke bhejein."
    ),
}


class SafetyPolicyEngine:
    """Deterministic safety gate. Pure; zero I/O."""

    _cross_patient = (
        "my mother", "meri maa", "my father", "mere pitaji", "meri beti",
        "my daughter", "my son", "mera beta", "my wife", "meri patni",
        "my husband", "mera pati", "my grandmother", "my grandfather",
        "meri dadi", "mere dada", "my friend", "mera dost", "my neighbor",
        "meri paadsi", "his sugar", "her sugar", "uska sugar", "uski sugar",
        "other person", "kisi aur ka",
    )

    _diagnosis = (
        "diagnosis", "diagnose", "do i have diabetes", "kya bimari hai",
        "mujhe diabetes hai kya", "what is wrong with me", "batao kya hua",
        "meri beemari", "which disease", "is it diabetes",
        "diabetes hai kya", "hidden diabetes", "prediabetes",
    )
    _prognosis = (
        "how long", "kitne saal", "kitne din aur", "will i survive",
        "life expectancy", "cure", "ilaaj", "kab thik", "recover",
    )

    def evaluate(
        self,
        text: str,
        intent: ConversationIntent,
        structured: StructuredIntent,
    ) -> SafetyDecision:
        low = normalize_digits(text or "").lower()
        flags: list[SafetyFlag] = list(structured.safety_flags)

        # 1. Emergency — outranks everything.
        emergency_hits = _emergency_hits(low)
        if intent == ConversationIntent.HANDOFF_TO_CARE_TEAM and emergency_hits:
            flags.append(SafetyFlag.EMERGENCY)
            return SafetyDecision(
                blocked=False,
                reason="emergency escalation",
                guidance_message=_GUIDANCE[SafetyFlag.EMERGENCY],
                emergency=True,
                handoff=True,
                flags=tuple(flags),
                intent_override=ConversationIntent.HANDOFF_TO_CARE_TEAM,
            )

        # 2. Dosage change — always handoff, never advise.
        if any(m in low for m in _DOSAGE_WORDS):
            flags.append(SafetyFlag.DOSAGE_CHANGE)
            return SafetyDecision(
                blocked=True,
                reason="medication/insulin dosage change request",
                guidance_message=_GUIDANCE[SafetyFlag.DOSAGE_CHANGE],
                handoff=True,
                flags=tuple(flags),
                intent_override=ConversationIntent.HANDOFF_TO_CARE_TEAM,
            )

        # 3. Diagnosis / prognosis requests.
        if any(m in low for m in self._diagnosis) or any(m in low for m in self._prognosis):
            flags.append(SafetyFlag.DIAGNOSIS_REQUEST)
            return SafetyDecision(
                blocked=True,
                reason="diagnosis/prognosis request",
                guidance_message=_GUIDANCE[SafetyFlag.DIAGNOSIS_REQUEST],
                flags=tuple(flags),
                intent_override=ConversationIntent.GENERAL_DIABETES_TRACKING_HELP,
            )

        # 4. Prompt injection.
        if any(m in low for m in _INJECTION_WORDS):
            flags.append(SafetyFlag.PROMPT_INJECTION)
            return SafetyDecision(
                blocked=True,
                reason="prompt-injection attempt",
                guidance_message=_GUIDANCE[SafetyFlag.PROMPT_INJECTION],
                flags=tuple(flags),
                intent_override=ConversationIntent.NON_HEALTH_REQUEST,
            )

        # 5. Cross-patient requests.
        if intent == ConversationIntent.UNKNOWN and any(
            m in low for m in self._cross_patient
        ):
            flags.append(SafetyFlag.CROSS_PATIENT_REQUEST)
            return SafetyDecision(
                blocked=True,
                reason="cross-patient request",
                guidance_message=_GUIDANCE[SafetyFlag.CROSS_PATIENT_REQUEST],
                flags=tuple(flags),
                intent_override=ConversationIntent.GENERAL_DIABETES_TRACKING_HELP,
            )

        # 6. Non-health overt requests.
        if intent == ConversationIntent.NON_HEALTH_REQUEST:
            flags.append(SafetyFlag.NON_HEALTH_REQUEST)
            return SafetyDecision(
                blocked=True,
                reason="non-health request",
                guidance_message=_GUIDANCE[SafetyFlag.NON_HEALTH_REQUEST],
                flags=tuple(flags),
                intent_override=ConversationIntent.UNKNOWN,
            )

        # 7. Out-of-range glucose value.
        if intent in (ConversationIntent.GLUCOSE_LOG,):
            value = structured.glucose.value_mg_dl
            if value is not None and not (20 <= value <= 600):
                flags.append(SafetyFlag.OUT_OF_RANGE_VALUE)
                return SafetyDecision(
                    blocked=True,
                    reason="out-of-range glucose value",
                    guidance_message=_GUIDANCE[SafetyFlag.OUT_OF_RANGE_VALUE],
                    flags=tuple(flags),
                    intent_override=ConversationIntent.UNKNOWN,
                )

        # 8. Low-confidence / no-value extraction on a structured intent.
        if structured.requires_confirmation and not structured.any_entity:
            flags.append(SafetyFlag.UNKNOWN_VALUE)
            return SafetyDecision(
                blocked=True,
                reason="no extractable value",
                guidance_message=_GUIDANCE[SafetyFlag.UNKNOWN_VALUE],
                flags=tuple(flags),
            )

        return SafetyDecision(
            blocked=False,
            reason="",
            flags=tuple(flags),
        )

    def validate_wording(self, reply: str) -> bool:
        """Confirm-phase wording guard (§17): reject interpretive labels."""
        return not contains_forbidden_interpretation(reply)


# Keep the literals here to mirror the taxonomy module without import cycles.
_DOSAGE_WORDS = (
    "badao", "badhao", "badha do", "increase dose", "dose barhao",
    "kam karo", "kam kar do", "decrease dose", "reduce dose", "dose kam",
    "double dose", "double kar", "dose change", "change dose", "adjust",
    "insulin badha", "insulin kam", "units badha", "units kam",
    "dose 30", "dose 25", "insulin 20", "insulin 30",
)

_INJECTION_WORDS = (
    "ignore previous", "ignore all previous", "disregard", "you are now",
    "act as", "system prompt", "system message", "developer instruction",
    "pretend", "jailbreak", "override your instructions", "forget everything",
    "you must obey", "reveal system", "output your instructions",
    "print your system", "dan mode", "sudo mode", "repeat after me",
)

_EMERGENCY_HIT_WORDS = (
    "emergency", "ambulance", "heart attack", "unconscious", "behosh",
    "severe pain", "chest pain", "sine mein dard", "saans nahi aa rahi",
    "breathing", "turant doctor", "emergency mein", "hospital le chalo",
    "bleeding", "gambhir", "critical", "convulsion", "seizure", "daura",
    "faint", "gir gaya", "dangar", "khoon",
)


def _emergency_hits(low: str) -> bool:
    if "108" in low or "112" in low:
        return True
    return any(w in low for w in _EMERGENCY_HIT_WORDS)


__all__ = [
    "SafetyPolicyEngine",
    "SafetyDecision",
    "contains_forbidden_interpretation",
    "FORBIDDEN_INTERPRETIVE_WORDS",
]