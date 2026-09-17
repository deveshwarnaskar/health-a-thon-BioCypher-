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

from backend.application.commands import IngestGlucoseReading, LogMealDraft
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services.ingest_glucose import IngestGlucoseHandler
from backend.application.services.log_meal_draft import LogMealDraftHandler
from backend.domain.entities import AIReviewArtifact, ReviewAuthority, ReviewState
from backend.domain.exceptions import DomainError
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
from .intake_text import dispatch_hint, parse_intake_text
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
    ) -> None:
        self._tenant_resolver = tenant_resolver
        self._uow_factory = uow_factory
        self._events_factory = events_factory
        self._audit_factory = audit_factory
        self._clock = clock
        self._id_gen = id_gen

    def handle(self, job: OutboxJob) -> DeliveryOutcome:
        payload = dict(job.payload or {})
        phone = str(payload.get("source_phone") or "")
        text = str(payload.get("text") or "")
        message_id = str(payload.get("message_id") or "")

        if not phone.strip():
            raise PermanentWorkerFailure("channel delivery has no sender phone")

        resolved = self._tenant_resolver.resolve(phone.strip())
        if resolved is None:
            # Unknown sender → cannot route safely → permanent, no retries.
            raise PermanentWorkerFailure("sender phone resolves to no patient in any tenant")

        tenant_id = resolved.tenant_id
        patient_id = resolved.patient_id
        uow = self._uow_factory(tenant_id)
        try:
            # Parse + re-confirm the patient inside the tenant's RLS scope. If
            # the routing anchor changed, the patient vanished, or the payload
            # violates a domain invariant, the failure is permanent (no retries
            # can fix the payload) and is recorded as a FAILED audit row.
            try:
                cmd = parse_intake_text(
                    text,
                    patient_id=patient_id,
                    correlation_id=job.correlation_id,
                    recorded_at=self._clock.now(),
                )
                patient = uow.patients.get(patient_id)
                if not getattr(patient, "active", True):
                    raise DomainError(f"patient {patient_id} is deactivated; channel intake denied")
            except DomainError as exc:
                self._write_failure_audit(
                    uow, job, tenant_id,
                    reason=exc,
                    resource_type="CHANNEL_MESSAGE",
                    resource_id=str(patient_id),
                )
                raise PermanentWorkerFailure(f"channel intake rejected by domain: {exc}") from exc

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

            try:
                if isinstance(cmd, IngestGlucoseReading):
                    IngestGlucoseHandler(uow, self._events_factory(uow), self._clock, self._id_gen).handle(cmd)
                else:
                    LogMealDraftHandler(uow, self._events_factory(uow), self._clock, self._id_gen).handle(cmd)
            except DomainError as exc:
                # in_transaction already rolled the business+audit rows back.
                self._write_failure_audit(
                    uow, job, tenant_id,
                    reason=exc,
                    resource_type=dispatch_hint(cmd),
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