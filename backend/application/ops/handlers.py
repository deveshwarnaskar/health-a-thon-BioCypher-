"""Gate 09 — Asynchronous channel handlers.

Two outbox consumers convert leased jobs into real application work WITHOUT
bypassing any layer:

- ``WhatsAppIntakeHandler``  — resolves the sender phone to a (tenant, patient)
  anchor, re-confirms the patient inside the tenant's RLS scope, then dispatches
  ``IngestGlucoseReading`` or ``LogMealDraft`` through the standard Gate 04
  command handlers. All domain invariants are enforced by the domain itself.
- ``ChannelDeliveryHandler`` — dispatches an ``OutboundMessage`` through the
  provider-neutral ``ChannelSender``, translating provider errors into worker
  outcomes (retryable 5xx/timeout vs. permanent 4xx).

Both consumers run under the frozen system-worker identity and write
PHI-minimal ``AuditEvent`` rows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from backend.application.commands import (
    ConfirmMealObservation,
    IngestGlucoseReading,
    LogMealDraft,
)
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services.confirm_meal_observation import ConfirmMealObservationHandler
from backend.application.services.ingest_glucose import IngestGlucoseHandler
from backend.application.services.log_meal_draft import LogMealDraftHandler
from backend.domain.entities import AIReviewArtifact, ReviewAuthority, ReviewState
from backend.domain.exceptions import DomainError
from backend.domain.value_objects import (
    KatoriVolume,
    MealPortion,
    PatientConfirmationState,
    PhoneNumber,
)
from backend.application.ports.ai import (
    AIProvider,
    AITaskDefinition,
    AITaskType,
    DEFAULT_SYSTEM_CONSTRAINTS,
)
from backend.application.services.evidence_builder import EvidenceBuilder

from .contracts import (
    SYSTEM_WORKER_ACTOR_ID,
    SYSTEM_WORKER_ACTOR_TYPE,
    AI_GENERATION_EVENT_TYPE,
    AuditAction,
    AuditEvent,
    DeliveryOutcome,
    DeliveryResult,
    OutboundMessage,
    OutboxJob,
)
from .errors import PermanentWorkerFailure
from .intake_text import (
    IntentFirewall,
    IntentType,
    ambiguous_reading_values,
    dispatch_hint,
    parse_inbound,
    parse_intake_text,
)
from .ports import AuditStore, ChannelSender, ChannelTenantResolver

logger = logging.getLogger(__name__)


def _audit_for_worker(
    *,
    tenant_id,
    action: str,
    resource_type: str,
    resource_id: str,
    job: OutboxJob,
    outcome: str = "SUCCESS",
    reason: str | None = None,
    provenance: dict | None = None,
) -> AuditEvent:
    """Build a PHI-minimal system-worker audit event from a job."""
    return AuditEvent(
        tenant_id=tenant_id,
        actor_id=SYSTEM_WORKER_ACTOR_ID,
        actor_type=SYSTEM_WORKER_ACTOR_TYPE,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        correlation_id=str(job.correlation_id) if job.correlation_id else str(job.event_id),
        request_id=str(job.event_id),
        outcome=outcome,
        reason=reason,
        provenance_metadata=(provenance or {}) | {"outbox_event_id": str(job.event_id)},
    )


class WhatsAppIntakeHandler:
    """Consume verified ``whatsapp.message.received`` outbox jobs."""

    def __init__(
        self,
        *,
        tenant_resolver: ChannelTenantResolver,
        uow_factory: Callable[[object], UnitOfWork],
        events_factory: Callable[[UnitOfWork], DomainEventPublisher],
        audit_factory: Callable[[UnitOfWork], AuditStore],
        clock: Clock,
        id_gen: IdGenerator,
        sender: ChannelSender | None = None,
        transcriber: Any = None,
        ai_completer: Any = None,
    ) -> None:
        self._tenant_resolver = tenant_resolver
        self._uow_factory = uow_factory
        self._events_factory = events_factory
        self._audit_factory = audit_factory
        self._clock = clock
        self._id_gen = id_gen
        self._sender = sender
        self._transcriber = transcriber
        self._ai_completer = ai_completer

    def _deliver_deferred_welcome(
        self,
        uow: UnitOfWork,
        patient,
        phone: str,
        tenant_id: UUID,
        job: OutboxJob,
    ) -> None:
        """Send the personalized welcome if a PENDING WELCOME marker exists.

        The 24h customer-care window is open at this point (the customer just
        messaged the business), so free-form text delivery is permitted even though
        the connect-time attempt was blocked by Meta while no window existed.
        """
        from backend.domain.entities import NotificationStatus, NotificationType

        try:
            pending = [
                n
                for n in uow.notifications.list_for_patient(patient.id, limit=50)
                if n.notification_type == NotificationType.WELCOME
                and n.status != NotificationStatus.DELIVERED
            ]
        except Exception as exc:
            logger.info("deferred welcome lookup skipped: %s", exc)
            return
        if not pending:
            return

        marker = pending[0]
        body = str((marker.template_params or {}).get("body") or "")
        if body.strip():
            self._send_reply(phone, body, tenant_id, job.correlation_id)
        try:
            marker.queue()
            marker.mark_delivered()
            uow.notifications.save(marker)
            uow.commit()
            logger.info("deferred welcome delivered to %s", phone)
        except Exception as exc:
            logger.warning("deferred welcome bookkeeping failed: %s", exc)

    def _send_reply(
        self,
        phone: str,
        body: str,
        tenant_id: UUID,
        correlation_id: UUID | None,
        interactive: bool = False,
        button_1: str = "Yes / Haan",
        button_2: str = "Cancel / Radd",
    ) -> None:
        if self._sender is None:
            return
        try:
            params = {"body": body}
            if interactive:
                params["interactive_type"] = "button"
                params["button_1"] = button_1
                params["button_2"] = button_2
                params["button_1_id"] = "confirm_yes"
                params["button_2_id"] = "confirm_cancel"

            msg = OutboundMessage(
                message_id=self._id_gen.new_uuid(),
                tenant_id=tenant_id,
                recipient_phone=phone.strip(),
                channel_type="WHATSAPP",
                template_name="text",
                template_params=params,
                correlation_id=str(correlation_id) if correlation_id else "",
            )
            self._sender.send(msg)
        except Exception as exc:
            logger.warning("failed to send whatsapp reply: %s", exc)

    def handle(self, job: OutboxJob) -> DeliveryOutcome:
        payload = dict(job.payload or {})
        phone = str(payload.get("source_phone") or "")
        text = str(payload.get("text") or "")
        message_id = str(payload.get("message_id") or "")
        interactive_reply_id = str(payload.get("interactive_reply_id") or "").strip() or None
        media_type = str(payload.get("media_type") or payload.get("message_type") or "")
        media_id = str(payload.get("media_id") or "")

        # Transcribe audio voice note if media present and transcriber injected
        if (media_type == "audio" or not text.strip() or text.strip() == "[audio]") and media_id:
            if self._sender is not None and hasattr(self._sender, "download_media") and self._transcriber is not None:
                media_res = self._sender.download_media(media_id)
                if media_res:
                    audio_bytes, mime_type = media_res
                    try:
                        transcribed = self._transcriber(audio_bytes, mime_type)
                        if transcribed:
                            logger.info("Voice note transcribed: %s", transcribed)
                            text = str(transcribed).strip()
                    except Exception as exc:
                        logger.warning("Voice transcription failed: %s", exc)

        if not phone.strip():
            raise PermanentWorkerFailure("channel delivery has no sender phone")

        resolved = self._tenant_resolver.resolve(phone.strip())
        if resolved is None:
            # Unregistered sender: send polite guidance safe from clinical leakage
            if self._sender is not None:
                try:
                    self._send_reply(
                        phone,
                        "Namaste! Yeh phone number THALI × P.L.A.T.E. mein registered nahi hai. "
                        "Kripya apne registered phone number se message karein ya clinic se sampark karein.",
                        UUID("00000000-0000-0000-0000-000000000000"),
                        job.correlation_id,
                    )
                except Exception:
                    pass
            # Unknown sender → cannot route safely → permanent, no retries.
            raise PermanentWorkerFailure("sender phone resolves to no patient in any tenant")

        tenant_id = resolved.tenant_id
        patient_id = resolved.patient_id
        uow = self._uow_factory(tenant_id)
        try:
            patient = uow.patients.get(patient_id)
            if not getattr(patient, "active", True):
                raise DomainError(f"patient {patient_id} is deactivated; channel intake denied")

            # Deliver any deferred WELCOME greeting now that the 24h window is open
            # (the customer just messaged the business, so free-form text is allowed).
            self._deliver_deferred_welcome(uow, patient, phone, tenant_id, job)

            # Evaluate Intent Firewall
            verdict = IntentFirewall.evaluate(text, interactive_reply_id=interactive_reply_id)

            # 1. Unsupported intent (poetry, code, weather, general QA)
            if not verdict.is_supported or verdict.intent == IntentType.UNSUPPORTED:
                guide_msg = (
                    verdict.guidance_message
                    or "Main aapka health assistant hoon. Aap glucose readings ya meals record kar sakte hain."
                )
                self._send_reply(phone, guide_msg, tenant_id, job.correlation_id)
                self._audit_factory(uow).record(
                    _audit_for_worker(
                        tenant_id=tenant_id,
                        action=AuditAction.CREATE.value,
                        resource_type="UNSUPPORTED_INTENT",
                        resource_id=str(patient_id),
                        job=job,
                        outcome="SUCCESS",
                        provenance={"channel": "whatsapp", "provider_message_id": message_id},
                    )
                )
                uow.commit()
                return DeliveryOutcome.SUCCESS

            # 2. Help / Greeting intent
            if verdict.intent == IntentType.HELP:
                from backend.application.services.welcome_template import build_welcome_message
                help_msg = build_welcome_message(getattr(patient, "name", ""))
                self._send_reply(phone, help_msg, tenant_id, job.correlation_id)
                self._audit_factory(uow).record(
                    _audit_for_worker(
                        tenant_id=tenant_id,
                        action=AuditAction.CREATE.value,
                        resource_type="HELP_REQUEST",
                        resource_id=str(patient_id),
                        job=job,
                        outcome="SUCCESS",
                        provenance={"channel": "whatsapp", "provider_message_id": message_id},
                    )
                )
                uow.commit()
                return DeliveryOutcome.SUCCESS

            # 2b. Conversational Healthcare / Onboarding Queries
            if verdict.intent == IntentType.CONVERSATIONAL:
                from backend.application.services.conversational_assistant import generate_conversational_reply
                patient_name = getattr(patient, "name", "")
                reply = generate_conversational_reply(text, patient_name=patient_name, ai_completer=self._ai_completer)
                self._send_reply(phone, reply, tenant_id, job.correlation_id)
                self._audit_factory(uow).record(
                    _audit_for_worker(
                        tenant_id=tenant_id,
                        action=AuditAction.CREATE.value,
                        resource_type="CONVERSATIONAL_QUERY",
                        resource_id=str(patient_id),
                        job=job,
                        outcome="SUCCESS",
                        provenance={"channel": "whatsapp", "provider_message_id": message_id},
                    )
                )
                uow.commit()
                return DeliveryOutcome.SUCCESS

            # 3. Cancel intent (cancel pending meal drafts)
            if verdict.intent == IntentType.CANCEL:
                meals = uow.meal_observations.list_for_patient(patient_id)
                pending_meals = [
                    m for m in meals
                    if getattr(getattr(m, "confirmation", None), "value", str(getattr(m, "confirmation", ""))) == "pending"
                ]
                pending_meals.sort(
                    key=lambda m: getattr(m, "recorded_at", getattr(m, "created_at", None)),
                    reverse=True,
                )
                if pending_meals:
                    latest = pending_meals[0]
                    latest.confirmation = PatientConfirmationState.REJECTED
                    uow.meal_observations.save(latest)
                    self._audit_factory(uow).record(
                        _audit_for_worker(
                            tenant_id=tenant_id,
                            action=AuditAction.UPDATE.value,
                            resource_type="MEAL_CANCEL",
                            resource_id=str(latest.id),
                            job=job,
                            outcome="SUCCESS",
                            provenance={"channel": "whatsapp", "provider_message_id": message_id},
                        )
                    )
                    uow.commit()
                    self._send_reply(phone, "Aapka pending meal record cancel kar diya gaya hai.", tenant_id, job.correlation_id)
                else:
                    self._send_reply(phone, "Koi pending meal record nahi mila jise cancel kiya ja sake.", tenant_id, job.correlation_id)
                return DeliveryOutcome.SUCCESS

            # 4. Status check intent
            if verdict.intent == IntentType.STATUS:
                glucose_list = uow.glucose_observations.list_for_patient(patient_id)
                if glucose_list:
                    sorted_g = sorted(
                        glucose_list,
                        key=lambda g: getattr(g, "taken_at", getattr(g, "created_at", None)),
                        reverse=True,
                    )
                    last = sorted_g[0]
                    tag_str = f" ({last.tag.value})" if getattr(last, "tag", None) else ""
                    time_str = last.taken_at.strftime("%I:%M %p") if hasattr(last, "taken_at") else ""
                    reply = f"Aapka aakhri glucose reading: {last.value.value_mg_dl} mg/dL{tag_str} (recorded at {time_str})."
                else:
                    reply = "Aapka koi glucose reading abhi tak darz nahi hai."
                self._send_reply(phone, reply, tenant_id, job.correlation_id)
                self._audit_factory(uow).record(
                    _audit_for_worker(
                        tenant_id=tenant_id,
                        action=AuditAction.CREATE.value,
                        resource_type="STATUS_CHECK",
                        resource_id=str(patient_id),
                        job=job,
                        outcome="SUCCESS",
                        provenance={"channel": "whatsapp", "provider_message_id": message_id},
                    )
                )
                uow.commit()
                return DeliveryOutcome.SUCCESS

            # 5. Ambiguity detection
            ambiguous = ambiguous_reading_values(text)
            if ambiguous:
                self._send_reply(
                    phone,
                    "Aapka glucose reading clear nahi hai. Kripya ek reading bhejein (jaise: 140 fasting ya 180).",
                    tenant_id,
                    job.correlation_id,
                )
                self._audit_factory(uow).record(
                    _audit_for_worker(
                        tenant_id=tenant_id,
                        action=AuditAction.CREATE.value,
                        resource_type="AMBIGUOUS_READING",
                        resource_id=str(patient_id),
                        job=job,
                        outcome="SUCCESS",
                        provenance={"channel": "whatsapp", "provider_message_id": message_id},
                    )
                )
                uow.commit()
                return DeliveryOutcome.SUCCESS

            # 6. Confirm / Correct loop for pending meal observations
            parsed = parse_inbound(text)
            if interactive_reply_id in ("confirm_yes", "btn_confirm"):
                parsed.kind = "confirm"
            elif interactive_reply_id in ("confirm_cancel", "btn_cancel"):
                parsed.kind = "cancel"

            if parsed.is_confirm or parsed.kind == "correct" or verdict.intent == IntentType.CONFIRM:
                meals = uow.meal_observations.list_for_patient(patient_id)
                pending_meals = [
                    m for m in meals
                    if getattr(getattr(m, "confirmation", None), "value", str(getattr(m, "confirmation", ""))) == "pending"
                ]
                pending_meals.sort(
                    key=lambda m: getattr(m, "recorded_at", getattr(m, "created_at", None)),
                    reverse=True,
                )
                if pending_meals:
                    latest = pending_meals[0]
                    corrected_desc = parsed.text if parsed.kind == "correct" else None
                    corrected_portion = None
                    portion_label = "Medium (220 ml)"

                    portion_letter = parsed.portion_letter
                    if portion_letter:
                        vol_map = {"s": 150, "m": 220, "l": 350}
                        label_map = {"s": "Small (150 ml)", "m": "Medium (220 ml)", "l": "Large (350 ml)"}
                        vol = vol_map.get(portion_letter.lower(), 220)
                        portion_label = label_map.get(portion_letter.lower(), "Medium (220 ml)")
                        food_key = latest.portion.food_key if latest.portion else "meal"
                        qty = latest.portion.quantity if latest.portion else 1.0
                        corrected_portion = MealPortion(food_key=food_key, katori=KatoriVolume(vol), quantity=qty)
                    elif latest.portion:
                        portion_label = latest.portion.katori.label or "Medium (220 ml)"

                    confirm_cmd = ConfirmMealObservation(
                        meal_observation_id=latest.id,
                        confirmed_by=PhoneNumber(phone.strip()),
                        corrected_description=corrected_desc,
                        corrected_portion=corrected_portion,
                        correlation_id=job.correlation_id,
                    )
                    ConfirmMealObservationHandler(uow, self._events_factory(uow), self._clock, self._id_gen).handle(confirm_cmd)

                    self._audit_factory(uow).record(
                        _audit_for_worker(
                            tenant_id=tenant_id,
                            action=AuditAction.UPDATE.value,
                            resource_type="MEAL",
                            resource_id=str(latest.id),
                            job=job,
                            provenance={"channel": "whatsapp", "provider_message_id": message_id, "kind": parsed.kind},
                        )
                    )
                    meal_desc = corrected_desc or latest.description
                    from backend.application.services.conversational_assistant import build_meal_confirmation_response
                    patient_name = getattr(patient, "name", "")
                    ack_msg = build_meal_confirmation_response(patient_name, meal_desc, portion_label)
                    self._send_reply(
                        phone,
                        ack_msg,
                        tenant_id,
                        job.correlation_id,
                    )
                    return DeliveryOutcome.SUCCESS
                else:
                    self._send_reply(
                        phone,
                        "Koi pending meal record nahi mila jise confirm kiya ja sake. Naya meal darz karne ke liye khane ka naam likhein (jaise: '2 roti dal').",
                        tenant_id,
                        job.correlation_id,
                    )
                    return DeliveryOutcome.SUCCESS

            # 7. Standard parsing (glucose or meal draft)
            cmd = parse_intake_text(
                text,
                patient_id=patient_id,
                correlation_id=job.correlation_id,
                recorded_at=self._clock.now(),
            )

            self._audit_factory(uow).record(
                _audit_for_worker(
                    tenant_id=tenant_id,
                    action=AuditAction.CREATE.value,
                    resource_type=dispatch_hint(cmd),
                    resource_id=str(patient_id),
                    job=job,
                    provenance={"channel": "whatsapp", "provider_message_id": message_id, "command": dispatch_hint(cmd)},
                )
            )

            if isinstance(cmd, IngestGlucoseReading):
                IngestGlucoseHandler(uow, self._events_factory(uow), self._clock, self._id_gen).handle(cmd)
                from backend.application.services.conversational_assistant import build_glucose_clinical_response
                patient_name = getattr(patient, "name", "")
                tag_name = getattr(cmd.tag, "value", str(cmd.tag)) if getattr(cmd, "tag", None) else None
                reply = build_glucose_clinical_response(patient_name, cmd.value.value_mg_dl, tag_name)
                self._send_reply(
                    phone,
                    reply,
                    tenant_id,
                    job.correlation_id,
                )
            else:
                LogMealDraftHandler(uow, self._events_factory(uow), self._clock, self._id_gen).handle(cmd)
                from backend.application.services.conversational_assistant import build_meal_clinical_prompt
                patient_name = getattr(patient, "name", "")
                prompt = build_meal_clinical_prompt(patient_name, cmd.description)
                self._send_reply(
                    phone,
                    prompt,
                    tenant_id,
                    job.correlation_id,
                    interactive=True,
                )

        except DomainError as exc:
            self._write_failure_audit(
                uow, job, tenant_id,
                reason=exc,
                resource_type="CHANNEL_MESSAGE",
                resource_id=str(patient_id),
            )
            raise PermanentWorkerFailure(f"channel payload rejected by domain: {exc}") from exc
        finally:
            uow.close()
        return DeliveryOutcome.SUCCESS

    def _write_failure_audit(self, uow: UnitOfWork, job: OutboxJob, tenant_id, *, reason, resource_type: str, resource_id: str) -> None:
        """Persist a FAILED audit row for a rejected worker operation."""
        self._audit_factory(uow).record(
            _audit_for_worker(
                tenant_id=tenant_id,
                action=AuditAction.CREATE.value,
                resource_type=resource_type,
                resource_id=resource_id,
                job=job,
                outcome="FAILED",
                reason=str(reason) or "domain rejection",
            )
        )
        uow.commit()


class ChannelDeliveryHandler:
    """Consume ``channel.message.send`` outbox jobs through the channel sender."""

    def __init__(
        self,
        *,
        sender: ChannelSender,
        uow_factory: Callable[[object], UnitOfWork],
        audit_factory: Callable[[UnitOfWork], AuditStore],
    ) -> None:
        self._sender = sender
        self._uow_factory = uow_factory
        self._audit_factory = audit_factory

    def handle(self, job: OutboxJob) -> DeliveryOutcome:
        if job.tenant_id is None:
            raise PermanentWorkerFailure("outbound message missing tenant binding")
        message = OutboundMessage.from_payload(dict(job.payload or {}), tenant_id=job.tenant_id)
        result: DeliveryResult = self._sender.send(message)

        if result.success:
            self._write_audit(
                job,
                outcome="SUCCESS",
                provenance={"channel": job.payload.get("channel_type", ""), "provider_delivery_id": result.provider_delivery_id},
            )
            return DeliveryOutcome.SUCCESS

        if result.retryable:
            # Provider 5xx / timeout → worker exponential backoff.
            self._update_notification_retry(job)
            return DeliveryOutcome.RETRYABLE

        self._write_audit(
            job,
            outcome="FAILED",
            reason=result.error_code or "provider rejected outbound message",
            provenance={"channel": job.payload.get("channel_type", ""), "error_code": result.error_code},
        )
        return DeliveryOutcome.PERMANENT

    def _write_audit(self, job: OutboxJob, *, outcome: str, reason: str | None = None, provenance: dict | None = None) -> None:
        uow = self._uow_factory(job.tenant_id)
        try:
            message_id_raw = job.payload.get("message_id")
            if message_id_raw and hasattr(uow, "notifications"):
                try:
                    notif_id = UUID(str(message_id_raw))
                    notif = uow.notifications.get(notif_id)
                    now = datetime.now(timezone.utc)
                    if outcome == "SUCCESS":
                        notif.mark_delivered(delivered_at=now)
                    elif outcome == "FAILED":
                        notif.mark_failed(reason=reason or "delivery failed", failed_at=now)
                    uow.notifications.save(notif)
                except Exception:
                    pass

            self._audit_factory(uow).record(
                _audit_for_worker(
                    tenant_id=job.tenant_id,
                    action=AuditAction.SEND.value,
                    resource_type="NOTIFICATION",
                    resource_id=str(job.payload.get("message_id") or job.event_id),
                    job=job,
                    outcome=outcome,
                    reason=reason,
                    provenance=provenance,
                )
            )
            uow.commit()
        finally:
            uow.close()

    def _update_notification_retry(self, job: OutboxJob) -> None:
        if not job.tenant_id:
            return
        uow = self._uow_factory(job.tenant_id)
        try:
            message_id_raw = job.payload.get("message_id")
            if message_id_raw and hasattr(uow, "notifications"):
                try:
                    notif_id = UUID(str(message_id_raw))
                    notif = uow.notifications.get(notif_id)
                    notif.requeue_for_retry()
                    uow.notifications.save(notif)
                    uow.commit()
                except Exception:
                    pass
        finally:
            uow.close()


class AIGenerationJobHandler:
    """Asynchronous worker handler for processing outbox AI generation requests."""

    def __init__(
        self,
        *,
        provider: AIProvider,
        evidence_builder: EvidenceBuilder,
        uow_factory: Callable[[UUID], UnitOfWork],
        audit_factory: Callable[[UnitOfWork], AuditStore],
    ) -> None:
        self._provider = provider
        self._evidence_builder = evidence_builder
        self._uow_factory = uow_factory
        self._audit_factory = audit_factory

    def handle(self, job: OutboxJob) -> DeliveryOutcome:
        tenant_id = job.tenant_id
        if not tenant_id:
            logger.error("outbox job missing tenant_id — discarding")
            return DeliveryOutcome.PERMANENT

        uow = self._uow_factory(tenant_id)
        try:
            patient_id_raw = job.payload.get("patient_id")
            artifact_id_raw = job.payload.get("artifact_id")
            if not patient_id_raw:
                logger.error("outbox job missing patient_id — discarding")
                return DeliveryOutcome.PERMANENT

            patient_id = UUID(str(patient_id_raw))
            user_notes = job.payload.get("context", "")

            # Build evidence
            try:
                evidence = self._evidence_builder.build(
                    patient_id=patient_id,
                    tenant_id=tenant_id,
                    uow=uow,
                    user_notes=user_notes,
                )
            except Exception:
                logger.exception("failed to build evidence for AI generation")
                return DeliveryOutcome.PERMANENT

            task = AITaskDefinition(
                task_type=AITaskType.CLINICAL_SUMMARY,
                system_constraints=DEFAULT_SYSTEM_CONSTRAINTS,
                patient_id=patient_id,
                tenant_id=tenant_id,
                correlation_id=str(job.correlation_id) if job.correlation_id else None,
            )

            result = self._provider.generate(task, evidence)
            if result.success:
                if artifact_id_raw:
                    artifact_id = UUID(str(artifact_id_raw))
                    try:
                        artifact = uow.ai_artifacts.get(artifact_id)
                        artifact.summary = result.summary
                        artifact.model_name = result.model
                        artifact.evidence_hash = evidence.evidence_hash
                        if artifact.state == ReviewState.GENERATED:
                            artifact.submit_for_review()
                        uow.ai_artifacts.save(artifact)
                    except Exception:
                        pass
                else:
                    artifact = AIReviewArtifact(
                        patient_id=patient_id,
                        tenant_id=tenant_id,
                        artifact_kind="clinical_summary",
                        authority=ReviewAuthority.CLINICIAN_REVIEW,
                        state=ReviewState.GENERATED,
                        generated_by=f"ai:{result.model}",
                        summary=result.summary,
                        model_name=result.model,
                        evidence_hash=evidence.evidence_hash,
                        correlation_id=str(job.correlation_id) if job.correlation_id else None,
                    )
                    artifact.submit_for_review()
                    uow.ai_artifacts.add(artifact)

                self._audit_factory(uow).record(
                    _audit_for_worker(
                        tenant_id=tenant_id,
                        action=AuditAction.CREATE.value,
                        resource_type="AI_ARTIFACT",
                        resource_id=str(artifact_id_raw or job.event_id),
                        job=job,
                        outcome="SUCCESS",
                        provenance={"model": result.model, "evidence_hash": evidence.evidence_hash},
                    )
                )
                uow.commit()
                return DeliveryOutcome.SUCCESS

            # Provider failed
            if result.retryable:
                logger.warning("AI provider retryable error: %s", result.error_code)
                return DeliveryOutcome.RETRYABLE

            logger.error("AI provider permanent failure: %s", result.error_code)
            self._audit_factory(uow).record(
                _audit_for_worker(
                    tenant_id=tenant_id,
                    action=AuditAction.CREATE.value,
                    resource_type="AI_ARTIFACT",
                    resource_id=str(artifact_id_raw or job.event_id),
                    job=job,
                    outcome="FAILED",
                    reason=result.error_code,
                )
            )
            uow.commit()
            return DeliveryOutcome.PERMANENT
        finally:
            uow.close()