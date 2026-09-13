"""Gate 03 — Domain event identity and basic invariants."""

from uuid import UUID

import pytest

from backend.domain import events as ev
from backend.domain.events import base as event_base
from backend.domain.exceptions import DomainValidationError


def test_event_requires_non_empty_event_type():
    with pytest.raises(DomainValidationError):
        event_base.DomainEvent()


def test_base_event_has_identity_and_timestamp():
    e = event_base.DomainEvent(event_type="test.event")
    assert isinstance(e.event_id, UUID)
    assert e.occurred_at is not None
    assert e.event_type == "test.event"


def test_concrete_events_expose_distinct_types():
    concrete = [
        ev.GlucoseObservationRecorded(),
        ev.MealObservationRecorded(),
        ev.MealObservationConfirmed(),
        ev.MedicationAdministrationRecorded(),
        ev.CareTaskCreated(),
        ev.CareTaskCompleted(),
        ev.AIArtifactGenerated(),
        ev.AIArtifactReviewed(),
    ]
    types = {e.event_type for e in concrete}
    assert len(types) == len(concrete)
    for e in concrete:
        assert e.event_type.startswith(("glucose", "meal", "medication", "care_task", "ai_artifact"))


def test_events_are_canonical_domain_events_not_telemetry():
    for cls in (
        ev.GlucoseObservationRecorded,
        ev.MealObservationConfirmed,
        ev.MedicationAdministrationRecorded,
        ev.CareTaskCompleted,
        ev.AIArtifactReviewed,
    ):
        e = cls()
        assert isinstance(e, event_base.DomainEvent)
        assert not hasattr(e, "raw_payload")
        assert not hasattr(e, "level")


def test_event_carries_patient_provenance():
    pid = UUID("12345678-1234-5678-1234-567812345678")
    e = ev.GlucoseObservationRecorded(patient_id=pid)
    assert e.patient_id == pid


def test_event_carries_correlation_id():
    cid = UUID("87654321-4321-8765-4321-876543210987")
    e = ev.MealObservationRecorded(correlation_id=cid)
    assert e.correlation_id == cid