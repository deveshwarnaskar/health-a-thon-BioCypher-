"""ConversationEngine orchestrator (spec §33 hybrid architecture).

The engine is the seam the ``WhatsAppIntakeHandler`` calls AFTER tenant/patient
resolution and the deferred-welcome delivery, and BEFORE the legacy intent
branches. It:

1. Defers every message the legacy worker already handles correctly
   (glucose/meal/confirm/cancel/status/help/conversational) → returns ``None``,
   so the existing branches and all existing tests are untouched.
2. Owns the NEW intents (medication confirmation, care-task/self-reminders,
   timeline, language change, document upload, voice, handoff/emergency) plus
   non-health refusals.
3. Runs deterministic resolution → extraction → safety policy → optional AI
   corroboration → deterministic action. AI never mutates state and never
   overrides safety.

All clinical writes go through existing Gate 04 domain handlers with the uow
the caller commits.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from backend.application.ops.contracts import AuditAction
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.infrastructure.parsing.conversation.extractors import (
    extract_glucose,
    extract_language,
    extract_meal,
    extract_medication,
    extract_task,
    normalize_digits,
)
from backend.infrastructure.parsing.conversation.schema import (
    Confidence,
    SafetyFlag,
    StructuredIntent,
)
from backend.infrastructure.parsing.conversation.taxonomy import (
    ConversationIntent,
    DidResolvedIntent,
    to_legacy,
)
from . import confirm as confirm_builders
from .fallback import EMPTY_TRANSCRIPT_REPLY, fallback_reply
from .providers import (
    ConversationAIProvider,
    DeterministicConversationProvider,
    ai_extract_intent,
)
from .reminders import ReminderPolicy
from .safety import SafetyDecision, SafetyPolicyEngine
from .state import (
    ConversationSession,
    ConversationState,
    DraftKind,
    fingerprint_medication,
    fingerprint_task,
)
from .telemetry import ConversationTelemetry

logger = logging.getLogger(__name__)

# The session store is a thin port; an in-memory default keeps the layer
# self-contained and testable. Production wiring may inject a durable store.
class SessionStore:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], ConversationSession] = {}

    def get(self, tenant_id, patient_id) -> ConversationSession:
        key = (str(tenant_id), str(patient_id))
        row = self._rows.get(key)
        if row is None:
            row = ConversationSession(tenant_id=tenant_id, patient_id=patient_id)
            self._rows[key] = row
        return row

    def save(self, session: ConversationSession) -> None:
        self._rows[(str(session.tenant_id), str(session.patient_id))] = session


@dataclass
class EngineOutcome:
    handled: bool
    reply: str = ""
    interactive: bool = False
    resource_type: str = "CHANNEL_MESSAGE"
    action: str = AuditAction.CREATE.value
    resource_id: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    emergency: bool = False


_ENGINE_OWNED_INTENTS = {
    ConversationIntent.MEDICATION_CONFIRMATION,
    ConversationIntent.CARE_TASK,
    ConversationIntent.TIMELINE_REQUEST,
    ConversationIntent.LANGUAGE_CHANGE,
    ConversationIntent.DOCUMENT_UPLOAD,
    ConversationIntent.VOICE_MESSAGE,
    ConversationIntent.HANDOFF_TO_CARE_TEAM,
}

_BUTTON_CONFIRM = {"confirm_yes", "btn_confirm"}
_BUTTON_CANCEL = {"confirm_cancel", "btn_cancel"}
_VOICE_MEDIA_TYPES = {"audio", "voice", "ptt", "ogg", "amr", "mpeg"}


class ConversationEngine:
    def __init__(
        self,
        *,
        clock: Clock,
        id_gen: IdGenerator,
        ai_provider: ConversationAIProvider | None = None,
        session_store: SessionStore | None = None,
        telemetry: ConversationTelemetry | None = None,
        reminder_policy: ReminderPolicy | None = None,
        wording: Callable[[StructuredIntent, str], str] | None = None,
    ) -> None:
        self._clock = clock
        self._id_gen = id_gen
        self._ai_provider = ai_provider or DeterministicConversationProvider()
        self._store = session_store or SessionStore()
        self._telemetry = telemetry or ConversationTelemetry()
        self._reminder_policy = reminder_policy or ReminderPolicy()
        self._classifier = DidResolvedIntent()
        self._safety = SafetyPolicyEngine()
        self._wording = wording

    @property
    def telemetry(self) -> ConversationTelemetry:
        return self._telemetry

    # ------------------------------------------------------------------ public
    def handle(
        self,
        *,
        text: str,
        patient: Any,
        patient_id: UUID,
        tenant_id: UUID,
        phone: str,
        interactive_reply_id: str | None,
        media_type: str,
        uow: UnitOfWork,
        events_factory: Callable[[UnitOfWork], DomainEventPublisher],
        job_ctx: dict[str, Any] | None = None,
    ) -> EngineOutcome | None:
        """Return an ``EngineOutcome`` if the engine owns the message, else None."""
        self._telemetry.message_seen()
        job_ctx = job_ctx or {}
        correlation_id = job_ctx.get("correlation_id")

        normalized = normalize_digits(text or "")
        raw = (text or "").strip()
        session = self._store.get(tenant_id, patient_id)

        # --- 1. Button confirms/cancels: owner depends on the open draft kind.
        if interactive_reply_id in _BUTTON_CONFIRM and session.is_awaiting(
            DraftKind.MEDICATION
        ):
            return self._complete_medication(
                uow, events_factory, tenant_id, patient_id, phone, session,
                correlation_id, taken=True,
            )
        if interactive_reply_id in _BUTTON_CANCEL and session.is_awaiting(
            DraftKind.MEDICATION
        ):
            return self._cancel_draft(uow, session, tenant_id, patient_id, DraftKind.MEDICATION)
        self._nocommit()

        # --- 2. Deterministic intent + legacy firewall.
        intent = self._classifier.resolve(normalized, media_type=media_type)
        if raw and media_type in _VOICE_MEDIA_TYPES:
            # A transcribed voice note with real text is handled as plain text.
            intent = self._classifier.resolve(normalized, media_type="")

        from backend.infrastructure.parsing.intent_firewall import IntentFirewall

        legacy = IntentFirewall.evaluate(normalized, interactive_reply_id=interactive_reply_id)
        legacy_owned = (
            legacy.intent.value in {
                "GLUCOSE_LOG", "MEAL_LOG", "CONFIRM", "CORRECT", "CANCEL",
                "STATUS", "HELP", "CONVERSATIONAL",
            }
            and legacy.is_supported
        )
        session_awaiting_draft = session.is_awaiting(DraftKind.MEDICATION) or session.is_awaiting(
            DraftKind.CARE_TASK
        )
        is_confirm_reply = intent in {
            ConversationIntent.CONFIRM,
            ConversationIntent.CANCEL,
            ConversationIntent.CORRECTION,
        }

        # --- 3. Empty/voice handling.
        if not raw:
            self._telemetry.record_intent(intent)
            return self._outcome(EMPTY_TRANSCRIPT_REPLY, "VOICE_MESSAGE", "CREATE")

        # --- 4. Structured extraction (deterministic-first).
        structured = self._build_structured(text=normalized, intent=intent)

        # --- 5. Safety gate runs BEFORE any legacy/AI dispatch. The only
        # messages exempt from interception are the legacy-owned clinical logs
        # (glucose/meal/confirm/cancel/status) whose values are validated
        # downstream by the domain. Diagnosis, dosing, emergency, injection,
        # and non-health requests are ALWAYS intercepted here.
        decision = self._safety.evaluate(normalized, intent, structured)
        self._telemetry.record_intent(intent)
        self._telemetry.record_confidence(str(structured.confidence.value))
        _clinical_legacy = {
            ConversationIntent.GLUCOSE_LOG,
            ConversationIntent.MEAL_LOG,
            ConversationIntent.CONFIRM,
            ConversationIntent.CANCEL,
            ConversationIntent.CORRECTION,
            ConversationIntent.STATUS_REQUEST,
        }
        if decision.emergency:
            self._telemetry.record_emergency()
            self._telemetry.record_safety(SafetyFlag.EMERGENCY)
            return self._emergency_outcome(decision)
        if decision.blocked and intent not in _clinical_legacy:
            if decision.flags:
                self._telemetry.record_safety(decision.flags[0])
            session.state = ConversationState.BLOCKED
            self._store.save(session)
            return self._outcome(
                decision.guidance_message,
                "SAFETY_BLOCK",
                "UPDATE",
                resource_id=str(patient_id),
                emergency=decision.emergency,
            )

        self._telemetry.record_safety(None)

        # --- 6. Legacy deferral: the existing worker owns these intents. A
        # pending engine draft bound to confirm/cancel overrides this.
        if (
            legacy_owned
            and intent not in _ENGINE_OWNED_INTENTS
            and not (session_awaiting_draft and is_confirm_reply)
        ):
            self._telemetry.legacy_deferred_message()
            self._store.save(session)
            return None

        # --- 7. Optional AI corroboration of low-confidence values.
        if self._ai_provider.is_configured():
            self._telemetry.record_ai_online()
            ai_extract_intent(self._ai_provider, normalized, structured)
        else:
            self._telemetry.record_ai_fallback()

        # --- 8. Dispatch by owned intent.
        handled = self._route(
            intent=intent,
            structured=structured,
            session=session,
            uow=uow,
            events_factory=events_factory,
            tenant_id=tenant_id,
            patient_id=patient_id,
            patient=patient,
            phone=phone,
            correlation_id=correlation_id,
        )
        if handled is not None:
            self._telemetry.engine_handled_message()
            self._store.save(session)
        return handled

    # ------------------------------------------------------------------ internals
    def _build_structured(self, *, text: str, intent: ConversationIntent) -> StructuredIntent:
        s = StructuredIntent(
            intent=intent,
            raw_text=text,
            normalized_text=text,
            confidence=Confidence.MID,
        )
        if intent == ConversationIntent.GLUCOSE_LOG:
            s.glucose = extract_glucose(text)
            s.requires_confirmation = s.glucose.confidence != Confidence.HIGH
        elif intent == ConversationIntent.MEAL_LOG:
            s.meal = extract_meal(text)
            s.requires_confirmation = not s.meal.description
        elif intent == ConversationIntent.MEDICATION_CONFIRMATION:
            s.medication = extract_medication(text)
            s.requires_confirmation = s.medication.confidence == Confidence.LOW
        elif intent == ConversationIntent.CARE_TASK:
            s.task = extract_task(text)
            s.requires_confirmation = not s.task.description
        elif intent == ConversationIntent.LANGUAGE_CHANGE:
            s.language = extract_language(text) or s.language
        elif intent == ConversationIntent.TIMELINE_REQUEST:
            pass
        return s

    def _route(
        self,
        *,
        intent: ConversationIntent,
        structured: StructuredIntent,
        session: ConversationSession,
        uow: UnitOfWork,
        events_factory: Callable[[UnitOfWork], DomainEventPublisher],
        tenant_id: UUID,
        patient_id: UUID,
        patient: Any,
        phone: str,
        correlation_id,
    ) -> EngineOutcome | None:
        now = self._clock.now()

        # A confirm/cancel meant for a pending engine-owned draft.
        if intent in (ConversationIntent.CONFIRM, ConversationIntent.CORRECTION) and session.is_awaiting(
            DraftKind.MEDICATION
        ):
            return self._complete_medication(
                uow, events_factory, tenant_id, patient_id, phone, session,
                correlation_id, taken=True,
            )
        if intent == ConversationIntent.CANCEL and session.is_awaiting(DraftKind.MEDICATION):
            return self._cancel_draft(uow, session, tenant_id, patient_id, DraftKind.MEDICATION)
        if intent in (ConversationIntent.CONFIRM, ConversationIntent.CORRECTION) and session.is_awaiting(
            DraftKind.CARE_TASK
        ):
            return self._complete_task(
                uow, events_factory, session, tenant_id, patient_id, phone, now, correlation_id
            )
        if intent == ConversationIntent.CANCEL and session.is_awaiting(DraftKind.CARE_TASK):
            return self._cancel_draft(uow, session, tenant_id, patient_id, DraftKind.CARE_TASK)

        if intent == ConversationIntent.MEDICATION_CONFIRMATION:
            return self._begin_medication(
                structured, session, tenant_id, patient_id, phone, correlation_id,
            )

        if intent == ConversationIntent.CARE_TASK:
            return self._begin_task(structured, session, tenant_id, patient_id, now)

        if intent == ConversationIntent.TIMELINE_REQUEST:
            return self._timeline(uow, patient_id, tenant_id)

        if intent == ConversationIntent.LANGUAGE_CHANGE:
            return self._language_change(structured, session, tenant_id, patient_id)

        if intent == ConversationIntent.DOCUMENT_UPLOAD:
            return self._document_upload(session, tenant_id, patient_id)

        if intent == ConversationIntent.HANDOFF_TO_CARE_TEAM:
            return self._handoff(session, tenant_id, patient_id, emergency=False)

        if intent == ConversationIntent.NON_HEALTH_REQUEST or intent == ConversationIntent.UNKNOWN:
            decision = self._safety.evaluate(
                structured.normalized_text, intent, structured
            )
            session.reset()
            return self._outcome(
                decision.guidance_message or fallback_reply(intent),
                "NON_HEALTH_REQUEST",
                "CREATE",
                resource_id=str(patient_id),
            )

        # GENERAL health help is deferred to the legacy conversational branch.
        return None

    # ---- medication ----------------------------------------------------------
    def _begin_medication(self, structured, session, tenant_id, patient_id, phone, correlation_id) -> EngineOutcome | None:
        med = structured.medication
        if med.medication is None and med.taken is None:
            return self._outcome(fallback_reply(ConversationIntent.MEDICATION_CONFIRMATION), "MEDICATION_INTENT", "CREATE")
        if med.taken is not None:
            session.mark_draft(
                DraftKind.MEDICATION,
                fingerprint_medication(medication=med.medication or "", when=med.when),
                {"medication": med.medication, "when": med.when, "dose": med.dose_units, "taken": med.taken},
            )
        else:
            session.mark_draft(
                DraftKind.MEDICATION,
                fingerprint_medication(medication=med.medication or "", when=med.when),
                {"medication": med.medication, "when": med.when, "dose": med.dose_units},
            )
        return self._outcome(
            confirm_builders.build_medication_confirm_prompt(med.medication, med.when, med.dose_units),
            "MEDICATION_DRAFT",
            "CREATE",
            interactive=True,
        )

    def _complete_medication(self, uow, events_factory, tenant_id, patient_id, phone, session, correlation_id, *, taken) -> EngineOutcome:
        ctx = session.context or {}
        medication = ctx.get("medication")
        when = ctx.get("when")
        dose = ctx.get("dose")
        session.reset(self._clock.now())

        # Match an active clinician-authored plan by normalized medication name,
        # then record the PATIENT-side administration fact via the domain handler.
        plan = self._match_active_plan(uow, patient_id, medication)
        if plan is not None and taken is True:
            from backend.application.commands import RecordMedicationAdministration
            from backend.application.services.record_medication_administration import RecordMedicationAdministrationHandler
            from backend.domain.value_objects import PhoneNumber

            RecordMedicationAdministrationHandler(uow, events_factory(uow), self._clock, self._id_gen).handle(
                RecordMedicationAdministration(
                    medication_plan_id=plan.id,
                    administered_at=self._clock.now(),
                    recorded_by=PhoneNumber(phone.strip()),
                    correlation_id=correlation_id,
                )
            )
        display = medication or "dawai"
        if dose:
            display = f"{display} ({dose})"
        reply = confirm_builders.build_confirm_ack(DraftKind.MEDICATION, display)
        return self._outcome(reply, "MEDICATION_CONFIRMED", "UPDATE")

    def _match_active_plan(self, uow, patient_id, medication: str | None):
        if not medication:
            return None
        try:
            plans = uow.medication_plans.list_for_patient(patient_id)
        except Exception:
            return None
        for plan in plans:
            if not getattr(plan, "active", False):
                continue
            norm_plan = (getattr(plan, "medication", "") or "").lower()
            if medication.lower() in norm_plan or norm_plan in medication.lower():
                return plan
        return None

    # ---- care-task self-reminders -------------------------------------------
    def _begin_task(self, structured, session, tenant_id, patient_id, now) -> EngineOutcome | None:
        task = structured.task
        if not task.description:
            return self._outcome(fallback_reply(ConversationIntent.CARE_TASK), "CARE_TASK", "CREATE")
        prompt = confirm_builders.build_task_confirm_prompt(task.description, task.due_label)
        session.mark_draft(
            DraftKind.CARE_TASK,
            fingerprint_task(description=task.description),
            {"description": task.description, "due_label": task.due_label},
        )
        return self._outcome(prompt, "CARE_TASK_DRAFT", "CREATE")

    def _complete_task(self, uow, events_factory, session, tenant_id, patient_id, phone, now, correlation_id) -> EngineOutcome:
        ctx = session.context or {}
        description = ctx.get("description", "")
        due_label = ctx.get("due_label")
        session.reset(now)

        from backend.domain.entities import Notification, NotificationChannel, NotificationStatus, NotificationType
        from backend.domain.events.channel import ChannelMessageQueued

        notif = Notification(
            id=self._id_gen.new_uuid(),
            tenant_id=tenant_id,
            recipient_id=patient_id,
            recipient_phone=phone.strip(),
            patient_id=patient_id,
            notification_type=NotificationType.REMINDER,
            channel=NotificationChannel.WHATSAPP,
            template_name="text",
            template_params={
                "body": f"⏰ Reminder: {description}.",
                "kind": "self_reminder",
                "due_label": due_label or "",
            },
            status=NotificationStatus.QUEUED,
            scheduled_at=now,
            created_at=now,
        )
        uow.notifications.add(notif)
        events_factory(uow).publish(
            ChannelMessageQueued(
                message_id=notif.id,
                channel_type=notif.channel.value,
                recipient_phone=notif.recipient_phone,
                template_name=notif.template_name,
                template_params=notif.template_params,
            )
        )
        reply = confirm_builders.build_confirm_ack(DraftKind.CARE_TASK, description)
        return self._outcome(reply, "CARE_TASK_CONFIRMED", "UPDATE")

    def _cancel_draft(self, uow, session, tenant_id, patient_id, kind) -> EngineOutcome:
        session.reset(self._clock.now())
        return self._outcome(
            confirm_builders.build_cancel_ack(kind),
            f"{kind.value.upper()}_CANCELLED",
            "UPDATE",
        )

    # ---- read-only views ----------------------------------------------------
    def _timeline(self, uow, patient_id, tenant_id) -> EngineOutcome:
        rows = []
        try:
            rows = uow.glucose_observations.list_for_patient(patient_id)
        except Exception:
            rows = []
        if not rows:
            return self._outcome(
                "Aapke koi glucose readings abhi tak darz nahi hui hain.",
                "TIMELINE_REQUEST",
                "CREATE",
            )
        recent = sorted(
            rows,
            key=lambda g: getattr(g, "taken_at", getattr(g, "created_at", None)) or self._clock.now(),
            reverse=True,
        )[:5]
        lines = []
        for g in recent:
            value = getattr(getattr(g, "value", None), "value_mg_dl", None)
            tag = getattr(g, "tag", None)
            taken = getattr(g, "taken_at", None)
            time_str = taken.strftime("%d %b, %I:%M %p") if taken else ""
            tag_str = f" ({tag.value})" if tag and hasattr(tag, "value") else ""
            if value is not None:
                lines.append(f"• {value} mg/dL{tag_str} — {time_str}")
        body = "Aapki aakhri readings:\n" + "\n".join(lines)
        return self._outcome(body, "TIMELINE_REQUEST", "CREATE")

    def _language_change(self, structured, session, tenant_id, patient_id) -> EngineOutcome:
        lang = structured.language
        if not lang.code:
            return self._outcome(
                "Kripya batayein ki aap kis bhasha mein baat karna chahenge"
                " (Hindi, English, Bengali, Tamil, etc.).",
                "LANGUAGE_CHANGE",
                "CREATE",
            )
        session.context["language_code"] = lang.code
        display = lang.display_name or lang.code
        reply = (
            f"Bahut badhiya! Ab main aapse {display} mein baat karne ki koshish "
            "karunga/karungi. Kripya apni sugar readings ya meals bhejte rahein."
        )
        return self._outcome(reply, "LANGUAGE_PREFERENCE", "UPDATE")

    def _document_upload(self, session, tenant_id, patient_id) -> EngineOutcome:
        session.state = ConversationState.AWAITING_DOCUMENT_UPLOAD
        return self._outcome(
            "Aapki file note kar li gayi hai. Report/prescription upload hone par "
            "aapki care team unhe review kar sakti hai.",
            "DOCUMENT_UPLOAD",
            "CREATE",
        )

    def _handoff(self, session, tenant_id, patient_id, *, emergency: bool) -> EngineOutcome:
        session.state = ConversationState.HANDOFF_OPEN
        if emergency:
            self._telemetry.record_emergency()
        reply = (
            "Yeh request aapki care team ko forward kar di gayi hai. Woh aapse "
            "jald hi sampark karenge. Agar yeh emergency hai toh Kripya turant "
            "108/112 par call karein."
        )
        return self._outcome(reply, "HANDOFF_TO_CARE_TEAM", "CREATE", emergency=emergency)

    # ---- helpers ------------------------------------------------------------
    def _outcome(
        self,
        reply: str,
        resource_type: str,
        action: str,
        *,
        resource_id: str = "",
        interactive: bool = False,
        emergency: bool = False,
    ) -> EngineOutcome:
        return EngineOutcome(
            handled=True,
            reply=reply,
            interactive=interactive,
            resource_type=resource_type,
            action=action,
            resource_id=resource_id,
            emergency=emergency,
        )

    def _emergency_outcome(self, decision: SafetyDecision) -> EngineOutcome:
        return self._outcome(
            decision.guidance_message,
            "EMERGENCY_ESCALATION",
            "CREATE",
            emergency=True,
        )

    def _nocommit(self) -> None:
        """Marker: caller retains commit responsibility (aligns with handler)."""
        return


__all__ = ["ConversationEngine", "EngineOutcome", "SessionStore"]